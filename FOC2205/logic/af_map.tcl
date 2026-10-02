#yosys -TQd -v 1 -L map.log -c map.tcl

yosys -import

set libdirs {}
set verilogs {}
foreach arg $argv {
  set arg [string trim $arg "\"\{\'\t \n"]
  if { [string index $arg 0] == "@" } {
    set cmd [string range $arg 1 1000]
    eval $cmd
  } elseif {[file isdirectory $arg]}  {
    lappend libdirs $arg
  } else {
    lappend verilogs $arg
  }
}

#set MINCE {5 10 10}
#set MINSRST {5 10 10}
set mince 5
set mince_cnt 10
set maxce_ratio 10
set minsrst 5
set minsrst_cnt 10
set maxsrst_ratio 10
if { [info exists MINCE] } {
  if { [llength $MINCE] >= 1 } {
    set mince [lindex $MINCE 0]
  }
  if { [llength $MINCE] >= 2 } {
    set mince_cnt [lindex $MINCE 1]
  }
  if { [llength $MINCE] >= 3 } {
    set maxce_ratio [lindex $MINCE 2]
  }
}
if { [info exists MINSRST] } {
  if { [llength $MINSRST] >= 1 } {
    set minsrst [lindex $MINSRST 0]
  }
  if { [llength $MINSRST] >= 2 } {
    set minsrst_cnt [lindex $MINSRST 1]
  }
  if { [llength $MINSRST] >= 3 } {
    set maxsrst_ratio [lindex $MINSRST 2]
  }
}

if { ! [info exists RETIMING] } {
  set RETIMING "100"
}
if { $RETIMING == "true" } {
  set RETIMING "100"
} elseif { $RETIMING == "false" } {
  set RETIMING "None"
}
if { ! [info exists IOPAD] } {
  set IOPAD true
}
if { [info exists DESIGN] && ! [info exists TOP_MODULE] } {
  set TOP_MODULE "$DESIGN"
}
if { ! [info exists DESIGN] } {
  set DESIGN "foc2205"
}
if { ! [info exists TOP_MODULE] } {
  set TOP_MODULE "foc2205"
}

puts [clock format [clock seconds] -format "%a %b %d %T %Y"]
if { [file exists [file join . ${DESIGN}.pre_map.asf]] } {
  puts "Using pre_map-ASF file ${DESIGN}.pre_map.asf."
  source [file join . ${DESIGN}.pre_map.asf]
}

set dash_libdirs {}
foreach libdir $libdirs {
  lappend dash_libdirs "-libdir" $libdir
}
if { [ llength $verilogs ] == 0 } {
  set verilogs { "foc2205.v" "analog_ip.v" }
}
if { [ llength $verilogs ] == 0 } {
  set verilogs [list ./${DESIGN}.v]
}
foreach verilog $verilogs {
  read_verilog -sv -overwrite -DALTA_SYN "$verilog"
}


#family:
    read_verilog -DALTA_LIB -sv -lib +/agm/rodina/cells_sim.v
    read_verilog -DALTA_SYN -sv +/agm/common/m9k_bb.v
    read_verilog -DALTA_SYN -sv +/agm/common/altpll_bb.v
    read_verilog -DALTA_LIB -sv -lib +/agm/rodina/alta_sim.v
    read_verilog -DALTA_SYN -sv +/agm/rodina/alta_sim.v
    read_verilog -DALTA_SYN -sv +/agm/common/alta_bb.v
    hierarchy -check -top $TOP_MODULE -DALTA_SYN -libdir "analog_ip" -libdir . {*}$dash_libdirs

#begin:
    flatten -separator |
    set alta_ips {alta_bram alta_bram9k alta_sram alta_wram alta_pll alta_pllx alta_pllv alta_pllve alta_boot alta_osc alta_mult alta_multm alta_ufm alta_ufms alta_ufml alta_i2c alta_spi alta_irda alta_mcu alta_mcu_m3 alta_saradc alta_adc alta_dac alta_cmp}
    select -none
    foreach alta_ip $alta_ips {
      select -add */t:$alta_ip
    }
    select -set keep_cells %
    select -clear
    setattr -set keep 1 @keep_cells

#coarse:
    yosys proc
    tribuf -logic
    deminout
    opt_expr
    opt_clean
    check
    opt -nodffe -nosdff
    fsm
    opt
    wreduce
    peepopt
    opt_clean
    alumacc
    share
    opt
    memory -nomap
    opt_clean
    for {set nn 0} {$nn < 10} {incr nn} {
      proc_dff
    }

#map_bram:
    memory_libmap -lib +/agm/common/brams_m9k.txt
    techmap -autoproc -map +/agm/common/brams_map_m9k.v
    yosys proc
    read_verilog -DALTA_SYN -sv +/agm/rodina/alta_sim.v
    hierarchy -check -top $TOP_MODULE -DALTA_SYN -libdir "analog_ip" -libdir . {*}$dash_libdirs
    flatten -separator |

#map_ffram:
    opt -fast -mux_undef -fine
    memory_map
    opt -fine
    techmap -autoproc -map +/agm/rodina/arith_map.v
    techmap -autoproc -map +/techmap.v
    yosys proc
    opt -undriven -fine
    yosys rename -wire -suffix _reg t:$*DFF*
    clean -purge
    setundef -undriven -zero
    if { $RETIMING != "None" } {
      abc -markgroups -dff -D $RETIMING
    }

#map_ffs:
    dfflegalize -mince $mince -minsrst $minsrst -mince_cnt $mince_cnt -minsrst_cnt $minsrst_cnt -maxce_ratio $maxce_ratio -maxsrst_ratio $maxsrst_ratio -cell \$_DFFE_????_ 0 -cell \$_SDFFCE_????_ 0 -cell \$_DLATCH_?_ x -cell \$_ALDFFE_???_ 0
    techmap -autoproc -map +/agm/common/ff_map.v
    yosys proc
    opt -fine
    clean -purge
    setundef -undriven -zero
    abc -markgroups -dff -D 1
    agm_dffeas

##opts:
    opt_expr -mux_undef -undriven -full
    opt_merge
    opt_clean
    autoname
 
#map_luts:
    abc -lut 4
    clean

#map_cells:
    if { $IOPAD } {
      iopadmap -bits -outpad \$__outpad I:O -inpad \$__inpad O:I -toutpad \$__toutpad E:I:O -tinoutpad \$__tinoutpad E:O:I:IO $TOP_MODULE
    }
    techmap -autoproc -map +/agm/rodina/cells_map.v
    clean -purge
    autoname

#check:
    hierarchy -check -top $TOP_MODULE -DALTA_SYN -libdir "analog_ip" -libdir . {*}$dash_libdirs
    stat
    check -noinit
    blackbox =A:whitebox

#vqm:
    attrmap -remove !*_attribute
    attrmap -remove !*_attribute -modattr
    write_verilog -simple-lhs -bitblasted -defparam -decimal -renameprefix syn_ ${DESIGN}.vqm

if { [file exists [file join . ${DESIGN}.post_map.asf]] } {
   puts "Using post_map-ASF file ${DESIGN}.post_map.asf."
   source [file join . ${DESIGN}.post_map.asf]
}
puts [clock format [clock seconds] -format "%a %b %d %T %Y"]

