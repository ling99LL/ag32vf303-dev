set ALTA_SUPRA true
set sh_continue_on_error false
set sh_echo_on_source  true
set sh_quiet_on_source true
set cc_critical_as_fatal true
set rt_incremental_route true
set ta_report_auto 1
set ta_report_auto_constraints $ta_report_auto

if { ! [info exists RESULT_DIR] } {
  set RESULT_DIR "."
} elseif { ! [info exists alta_work] } {
  set alta_work [file join ${RESULT_DIR} alta_db]
}
if { ! [info exists DEVICE] } {
  set DEVICE "AGRV2KL100"
}
if { [info exists DESIGN] && ! [info exists TOP_MODULE] } {
  set TOP_MODULE "$DESIGN"
}
if { ! [info exists DESIGN] } {
  set DESIGN "cpld_board"
}
if { ! [info exists TOP_MODULE] } {
  set TOP_MODULE "cpld_board"
}
if { ! [info exists IP_FILES] } {
  set IP_FILES {}
}
if { ! [info exists SDC_FILE] } {
  set SDC_FILE ""
}
if { ! [info exists VE_FILE] } {
  set VE_FILE ""
}
if { ! [info exists ATF_FILE] } {
  set ATF_FILE ""
}
if { ! [info exists VEX_FILE] } {
  set VEX_FILE "cpld_board.vex"
}
if { $VEX_FILE == "" && $VE_FILE != "" } {
  set VEX_FILE $VE_FILE
}
if { ! [info exists TIMING_DERATE] } {
  set TIMING_DERATE {1.000000 1.000000}
}
if { [info exists NO_ROUTE] && $NO_ROUTE } {
  set no_route "-no_route"
} else {
  set no_route ""
}
if { [info exist NON_USER_IO] && $NON_USER_IO } {
  set user_io ""
} else {
  set user_io "-user_io"
}
if { ! [info exists RETRY] } { set RETRY 0 }
if { ! [info exists SEED ] } { set SEED 666 }
set seed_rand ""
if { $SEED == 0 } { set seed_rand "-seed_rand" }
if { [info exists QUARTUS_SDC] } {
  set sdc_remove_quartus_column_name $QUARTUS_SDC
}
if { ! [info exists ORG_PLACE] } { set ORG_PLACE false }
if { ! [info exists MODE] } { set MODE "QUARTUS" }
if { ! [info exists FLOW] } { set FLOW "ALL"    }
if { $FLOW == "PROBE" } {
  if { ! [info exists PROBE_FORCE] } { set PROBE_FORCE false }
  if { ! [info exists PREFIX] } { set PREFIX "probe_" }
}
if { ! [info exists PREFIX] } {
  set RESULT $DESIGN
} else {
  set RESULT $PREFIX$DESIGN
}
if { $FLOW == "GEN" || $FLOW == "FLATTEN" || $FLOW == "PACK" || $FLOW == "PP" || $FLOW == "LOAD" } { set no_route "-no_route" }
set RUN "run"
if { $FLOW == "CHECK" } {
  set RUN "check"
} elseif { $FLOW == "PROBE" } {
  set RUN "probe"
} elseif { $FLOW == "GEN" } {
  set RUN "gen"
}
set flat_only [expr {$FLOW == "FLATTEN"}]

if { ! [info exists alta_logs] } {
  set alta_logs [file join ${RESULT_DIR} alta_logs]
}
file mkdir $alta_logs
alta::begin_log_cmd [file join $alta_logs ${RUN}.log] [file join $alta_logs ${RUN}.err]
alta::tcl_whisper "Cmd : [alta::prog_path] [alta::prog_version]([alta::prog_subversion])\n"
alta::tcl_whisper "Args : [string map {\{ \" \} \"} $tcl_cmd_args]\n"

set_seed_rand $SEED
set ar_timing_derate ${TIMING_DERATE}

date_time
if { [file exists [file join . ${DESIGN}.pre.asf]] } {
  alta::tcl_highlight "Using pre-ASF file ${DESIGN}.pre.asf.\n"
  source [file join . ${DESIGN}.pre.asf]
}

set new_work "-new_work"
set LOAD_DB    false
set LOAD_PLACE false
set LOAD_ROUTE false
set LOAD_PACK  false
if { $FLOW == "LOAD" || $FLOW == "CHECK" || $FLOW == "PROBE" } {
  set new_work ""
  set LOAD_DB    true
  set LOAD_PLACE true
  set LOAD_ROUTE true
} elseif { $FLOW == "R" || $FLOW == "ROUTE" } {
  set new_work ""
  set LOAD_DB    true
  set LOAD_PLACE true
} elseif { $FLOW == "PP" || $FLOW == "PR" || $FLOW == "PLACE_AND_ROUTE" } {
  set new_work ""
  set LOAD_PACK  true
}

#################################################################################

# The default SDC file is ${DESIGN}.sdc 
set sdc_file $SDC_FILE
if { $sdc_file == "" } {
  set sdc_file [file join . ${DESIGN}.adc]
  if { ! [file exists $sdc_file] } { set sdc_file [file join . ${DESIGN}.sdc]; }
}
# No default VE file is not specified
set ve_file $VEX_FILE

while (1) {

if { $FLOW == "SKIP" } { break }

if { [info exists CORNER] } { set_mode -corner $CORNER; }

eval "load_architect ${no_route} ${new_work} -type ${DEVICE} 1 1 1000 1000"
foreach ip_file $IP_FILES { read_ip $ip_file; }


if { $FLOW == "GEN" } {
  if { ! [info exists CONFIG_BITS] } {
    set CONFIG_BITS [file join ${RESULT_DIR} ${DESIGN}.bin]
  }
  if { [llength $CONFIG_BITS] > 1 } {
    if { ! [info exists BOOT_BINARY] } {
      set BOOT_BINARY [file join ${RESULT_DIR} ${DESIGN}_boot.bin]
    }
    if { ! [info exists CONFIG_ADDRESSES] } {
      set CONFIG_ADDRESSES ""
    }
    generate_binary -master $BOOT_BINARY -inputs $CONFIG_BITS -address $CONFIG_ADDRESSES
  } else {
    set CONFIG_ROOT   [file rootname [lindex $CONFIG_BITS 0]]
    set SLAVE_RBF     "${CONFIG_ROOT}_slave.rbf"
    set MASTER_BINARY "${CONFIG_ROOT}_master.bin"
    if { [file exists [lindex $CONFIG_BITS 0]] } {
      generate_binary -slave  $SLAVE_RBF     -inputs [lindex $CONFIG_BITS 0] -reverse
      generate_binary -master $MASTER_BINARY -inputs [lindex $CONFIG_BITS 0]
    }
    if { ! [info exists BOOT_BINARY] } {
      set BOOT_BINARY $MASTER_BINARY
    }
  }
  set PRG_FILE [file rootname $BOOT_BINARY].prg
  set AS_FILE  [file rootname $BOOT_BINARY]_as.prg
  generate_programming_file $BOOT_BINARY -erase $ERASE \
                            -program $PROGRAM -verify $VERIFY -offset $OFFSET \
                            -prg $PRG_FILE -as $AS_FILE
  break
}

if { $LOAD_DB } {
  load_db -top ${TOP_MODULE}
  if { [file exists $sdc_file] } { read_sdc $sdc_file; }

} elseif { $MODE == "QUARTUS" } {
  set verilog ${DESIGN}.vo
  set is_migrated false
  if { ! [file exists $verilog] } {
    set verilog [file join . simulation modelsim ${DESIGN}.vo]
    set is_migrated true
  }

  if { true } {
    set ORIGINAL_QSF "cpld_board.qsf"
    set ORIGINAL_PIN ""

    if { $ORIGINAL_PIN != "" } {
      if { [file exists $VE_FILE] } {
        set ORIGINAL_PIN ""
      } elseif { $ORIGINAL_PIN == "-" } {
        set ORIGINAL_PIN ""
      } elseif { ! [file exists $ORIGINAL_PIN] } {
        if { $is_migrated } {
          error "Can not find design PIN file $ORIGINAL_PIN, please compile design first"
        }
        set ORIGINAL_PIN ""
      }
    }
    if { $ORIGINAL_QSF != "" } {
      if { $ORIGINAL_QSF == "-" } {
        set ORIGINAL_QSF ""
      } elseif { ! [file exists $ORIGINAL_QSF] } {
        if { $is_migrated } {
          error "Can not find design exported QSF file $ORIGINAL_QSF, please export assigments first"
        }
      }
    }
    if { $ORIGINAL_QSF != "" || $ORIGINAL_PIN != "" } {
      set alta_aqf [file join $::alta_work alta.aqf]
      alta::convert_quartus_settings_cmd $ORIGINAL_QSF $ORIGINAL_PIN $alta_aqf
    }
  }

  if { ! [file exists $verilog] } {
    error "Can not find design VERILOG file $verilog"
  } else {
    alta::tcl_highlight "Using design VERILOG file $verilog.\n"
  }
  if { $ve_file != "" && ! [file exists $ve_file] } {
    alta::tcl_warn "Can not find design VE file $ve_file"
    set ve_file ""
  } else {
    alta::tcl_highlight "Using design VE file $ve_file.\n"
  }

  set ret [read_design -top ${TOP_MODULE} -ve $ve_file -qsf $ORIGINAL_QSF $verilog -hierachy 1 -flat_only $flat_only]
  if { !$ret } { exit -1; }
  if { $flat_only } { break }

  if { $sdc_file != "" && ! [file exists $sdc_file] } {
    alta::tcl_warn "Can not find design SDC file $sdc_file"
    set sdc_file ""
  } else {
    alta::tcl_highlight "Using design SDC file $sdc_file.\n"
    read_sdc $sdc_file
  }

} elseif { $MODE == "SYNPLICITY" || $MODE == "NATIVE" } {
  set db_gclk_assignment_level 2
  set verilog ${DESIGN}.vqm
  set is_migrated false
  if { ! [file exists $verilog] } {
    error "Can not find design VERILOG file $verilog"
  }

  if { $VEX_FILE != "" } {
    if { $VEX_FILE == "-" } {
      set VEX_FILE ""
    } elseif { ! [file exists $VEX_FILE] } {
      error "Can not find design VEX file $VEX_FILE"
    } else {
      alta::tcl_highlight "Using design VEX file $VEX_FILE.\n"
    }
  } else {
    set VEX_FILE ${DESIGN}.vex
    if { ! [file exists $VEX_FILE] } {
      set VEX_FILE ""
    } else {
      alta::tcl_highlight "Using design VEX file $VEX_FILE.\n"
    }
  }
  if { $ATF_FILE != "" } {
    if { $ATF_FILE == "-" } {
      set ATF_FILE ""
    } elseif { ! [file exists $ATF_FILE] } {
      error "Can not find design ATF file $ATF_FILE"
    } else {
      alta::tcl_highlight "Using design ATF file $ATF_FILE.\n"
    }
  } else {
    set ATF_FILE ${DESIGN}.atf
    if { ! [file exists $ATF_FILE] } {
      set ATF_FILE ""
    } else {
      alta::tcl_highlight "Using design ATF file $ATF_FILE.\n"
    }
  }

  alta::tcl_highlight "Using design VERILOG file $verilog.\n"
  if { $sdc_file != "" && ! [file exists $sdc_file] } {
    alta::tcl_warn "Can not find design SDC file $sdc_file"
    set sdc_file ""
  } else {
    alta::tcl_highlight "Using design SDC file $sdc_file.\n"
  }
  set load_pack ""
  if { $LOAD_PACK  } { set load_pack  "-load_pack"; }
  if { $ve_file != "" && ! [file exists $ve_file] } {
    alta::tcl_warn "Can not find design VE file $ve_file"
    set ve_file ""
  } else {
    alta::tcl_highlight "Using design VE file $ve_file.\n"
  }

  if { $ATF_FILE != "" || $VEX_FILE != "" } {
    set alta0_asf [file join $::alta_work alta0.asf]
    set alta0_apf [file join $::alta_work alta0.apf]
    set alta0_aqf [file join $::alta_work alta0.aqf]
    alta::convert_pio_settings_cmd $VEX_FILE $ATF_FILE $alta0_asf $alta0_apf $alta0_aqf
  }

  set ret [eval "read_design_and_pack $load_pack -sdc {$sdc_file} -top ${TOP_MODULE} -type vqm -ve {$ve_file} -gclk_level 2 $verilog" -flat_only $flat_only]
  if { !$ret } { exit -1; }
  if { $flat_only } { break }

  set FITTER "full"

} else {
  error "Unsupported mode $MODE"
}

if { $FLOW == "PACK" || $FLOW == "PP" } { break }

if { [info exists FITTING] } {
  if { $FITTING == "Auto" } { set FITTING auto; }
  set_mode -fitting $FITTING
}
if { [info exists FITTER] } {
  if { $FITTER == "Auto" } {
    if { $MODE == "QUARTUS" } { set FITTER hybrid; } else { set FITTER full; }
  }
  if { $MODE == "SYNPLICITY" || $MODE == "NATIVE" } { set FITTER full; }
  set_mode -fitter $FITTER
}
if { [info exists EFFORT] } { set_mode -effort $EFFORT; }
if { [info exists SKEW  ] } { set_mode -skew   $SKEW  ; }
if { [info exists SKOPE ] } { set_mode -skope  $SKOPE ; }
if { [info exists HOLDX ] } { set_mode -holdx  $HOLDX; }
if { [info exists TUNING] } { set_mode -tuning $TUNING; }
if { [info exists TARGET] } { set_mode -target $TARGET; }
if { [info exists PRESET] } { set_mode -preset $PRESET; }
if { [info exists ADJUST] } { set pl_criticality_wadjust $ADJUST; }

if { [file exists [file join . ${DESIGN}.asf]] } {
  alta::tcl_highlight "Using ASF file ${DESIGN}.asf.\n"
  source [file join . ${DESIGN}.asf]
}

if { $FLOW == "PROBE" } {
  set ret [eval "place_pseudo ${user_io} -place_io -place_pll -place_gclk"]
  if { !$ret } { exit -1 }

  set force ""
  if { [info exists PROBE_FORCE] && $PROBE_FORCE } { set force "-force" }
  eval "probe_design -froms {${PROBE_FROMS}} -tos {${PROBE_TOS}} ${force}"

} elseif { $FLOW == "CHECK" } {
  set ret [eval "place_pseudo ${user_io} -place_io -place_pll -place_gclk"]
  if { !$ret } { exit -1 }

  if { [file exists [file join . ${DESIGN}.chk]] } {
    alta::tcl_highlight "Using CHK file ${DESIGN}.chk.\n"
    source [file join . ${DESIGN}.chk]
    place_design -dry
    check_design -rule led_guide
  } else {
    error "Can not find design CHECK file ${DESIGN}.chk"
  }

} else {
  set ret [eval "place_pseudo ${user_io} -place_io -place_pll -place_gclk -warn_io"]
  if { !$ret } { exit -1 }

  set org_place ""
  set load_place ""
  set load_route ""
  set quiet ""
  if {  $ORG_PLACE } { set  org_place "-org_place" ; }
  if { $LOAD_PLACE } { set load_place "-load_place"; }
  if { $LOAD_ROUTE } { set load_route "-load_route"; }
  eval "place_and_route_design $org_place $load_place $load_route \
                               -retry $RETRY $seed_rand $quiet"
}

date_time
if { $FLOW != "CHECK" } {
if { $FLOW != "PROBE" } {
report_timing -verbose 2 -setup -file $::alta_work/setup.rpt.gz
report_timing -verbose 1 -setup -file $::alta_work/setup_summary.rpt
report_timing -verbose 2 -hold -file $::alta_work/hold.rpt.gz
report_timing -verbose 1 -hold -file $::alta_work/hold_summary.rpt

set ta_report_auto_constraints 0
report_timing -fmax -file $::alta_work/fmax.rpt
report_timing -xfer -file $::alta_work/xfer.rpt
set ta_report_auto_constraints $ta_report_auto

set ta_dump_uncovered 1
report_timing -verbose 1 -coverage >! $::alta_work/coverage.rpt.gz
set ta_dump_uncovered -1


if { ! [info exists rt_report_timing_fast] } {
  set rt_report_timing_fast false
}
if { $rt_report_timing_fast } {
  set_timing_corner fast
  route_delay -quiet
  report_timing -verbose 2 -setup -file $::alta_work/setup_fast.rpt.gz
  report_timing -verbose 1 -setup -file $::alta_work/setup_fast_summary.rpt
  report_timing -verbose 2 -hold -file $::alta_work/hold_fast.rpt.gz
  report_timing -verbose 1 -hold -file $::alta_work/hold_fast_summary.rpt
  set ta_report_auto_constraints 0
  report_timing -fmax -file $::alta_work/fmax_fast.rpt
  report_timing -xfer -file $::alta_work/xfer_fast.rpt
  set ta_report_auto_constraints $ta_report_auto
}

write_routed_design "${RESULT_DIR}/${RESULT}_routed.v"
}

bitgen normal -prg "${RESULT_DIR}/${RESULT}.prg" -bin "${RESULT_DIR}/${RESULT}.bin"
if { true } {
alta::bin_to_asc "${RESULT_DIR}/${RESULT}.bin" "${RESULT_DIR}/${RESULT}.inc"
set python_exe [expr {$tcl_platform(platform) eq "unix" ? "python3" : "python.exe"}]
if { ! [ info exist BATCH_ARG ] } {
  set BATCH_ARG ""
}
set LOGIC_COMPRESS [alta::get_global_assignment_cmd ON_CHIP_BITSTREAM_DECOMPRESSION false]
if { [string toupper $LOGIC_COMPRESS] != "OFF" } {
  set BATCH_ARG "$BATCH_ARG --logic-compress"
}
set BATCH_MCU 0xbff5105000730062aa234371030002b7
if { [info exists BATCH_HSE] } {
  set BATCH_MCU 0xbff5105000730062a62343110062aa234371030002b7
}
set GEN_BATCH "{[alta::prog_home]/python_dist/$python_exe} {[alta::prog_home]/pio/gen_batch}\
  -d [[alta::get_device_info_cmd $DEVICE] device_id]\
  -i $BATCH_MCU\
  -o ${RESULT_DIR}/${RESULT}_batch.bin\
  --logic-config ${RESULT_DIR}/${RESULT}.bin\
  --logic-address 0x80007000\
  $BATCH_ARG"
alta::tcl_highlight "Generating batch file: $GEN_BATCH\n"
eval "exec $GEN_BATCH"
} else {
bitgen sram -prg "${RESULT_DIR}/${RESULT}_sram.prg"
bitgen download -bin "${RESULT_DIR}/${RESULT}.bin" -svf "${RESULT_DIR}/${RESULT}_download.svf"
generate_binary -slave "${RESULT_DIR}/${RESULT}_slave.rbf" \
                -inputs "${RESULT_DIR}/${RESULT}.bin" -reverse
generate_binary -master "${RESULT_DIR}/${RESULT}_master.bin" \
                -inputs "${RESULT_DIR}/${RESULT}.bin"
generate_programming_file "${RESULT_DIR}/${RESULT}_master.bin" -prg "${RESULT_DIR}/${RESULT}_master.prg" \
  -as "${RESULT_DIR}/${RESULT}_master_as.prg" -hybrid "${RESULT_DIR}/${RESULT}_hybrid.prg"
}
}
break
}

if { [file exists "./${DESIGN}.post.asf"] } {
  alta::tcl_highlight "Using post-ASF file ${DESIGN}.post.asf.\n"
  source "./${DESIGN}.post.asf"
}
date_time
exit

