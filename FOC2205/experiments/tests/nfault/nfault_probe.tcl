
# ---- helpers -------------------------------------------------------------
# Debugger-side SPI0 frame, same sequence as src/app_io.c app_spi_send():
# single phase, 2 bytes (16 clocks). The CPLD (logic/spi_mode_wrap.v) shapes
# nSCS and latches SDO into SPIW_RXDATA0 (0x60007000).
proc rd {addr} {
  mem2array t 32 $addr 1
  return $t(0)
}
proc wr {addr val} { mww $addr $val }

proc spif {tx} {
  set _ [rd 0x60007000]                 ;# clear CPLD sticky done/error flags
  wr 0x40012010 0x200                   ;# PHASE_CTRL[0] = TX, single, 2 bytes
  wr 0x40012030 $tx                     ;# PHASE_DATA[0]
  set c [rd 0x40012000]
  set c [expr {($c & ~0x00100070) | 1}] ;# SPI_Start: keep DIV/ENDIAN/WP_EN, set START
  wr 0x40012000 $c
  set n 0
  while {$n < 1000} {
    if {[expr {[rd 0x40012000] & 2}]} { break }
    incr n
  }
  sleep 1                               ;# bridge latch trails SPI DONE by <=250ns
  set rx [rd 0x60007000]
  set st [rd 0x60007008]
  echo [format "  spi tx=0x%04X -> rx=0x%04X stat=0x%02X poll=%d ctrl=0x%08X" $tx $rx $st $n [rd 0x40012000]]
  return $rx
}

# 8-clock frame (PHASE_CTRL byte count = 1): nSCS is released before 16 clocks.
proc spif8 {tx} {
  set _ [rd 0x60007000]
  wr 0x40012010 0x100
  wr 0x40012030 $tx
  set c [rd 0x40012000]
  wr 0x40012000 [expr {($c & ~0x00100070) | 1}]
  set n 0
  while {$n < 1000} { if {[expr {[rd 0x40012000] & 2}]} { break } ; incr n }
  sleep 1
  echo [format "  spi8 tx=0x%04X -> rx=0x%04X stat=0x%02X poll=%d" $tx [rd 0x60007000] [rd 0x60007008] $n]
}

# BDTR=0x40020044 SR=0x40020010 GPIO4 data[0xFF]=0x400183FC GPIO2 data[0xFF]=0x400163FC
proc snapshot {tag} {
  echo [format "%s BDTR=0x%08X SR=0x%08X GPIO4=0x%02X GPIO2=0x%02X" $tag \
        [rd 0x40020044] [rd 0x40020010] \
        [expr {[rd 0x400183FC] & 0xFF}] [expr {[rd 0x400163FC] & 0xFF}]]
}
proc report {tag} {
  echo [format "%s GPIO4=0x%02X nFAULT_pin=%d MOE=%d BIF=%d IC_STAT=0x%02X STAT2=0x%02X" $tag \
        [expr {[rd 0x400183FC] & 0xFF}] [expr {([rd 0x400183FC] >> 1) & 1}] \
        [expr {([rd 0x40020044] >> 15) & 1}] [expr {([rd 0x40020010] >> 7) & 1}] \
        [expr {[spif 0x0081] & 0xFF}] [expr {[spif 0x0084] & 0xFF}]]
}
# Clear the CPLD-side race: if the firmware was mid-SPI0-frame when the core
# halted, reset the block (preserving DIV/ENDIAN/WP_EN) so nSCS is released.
proc spi0_stabilise {} {
  set ctrl [rd 0x40012000]
  if {[expr {$ctrl & 1}]} {
    echo "SPI0 busy at halt -> resetting the SPI block"
    wr 0x40012000 0x80000000
    wr 0x40012000 [expr {$ctrl & 0x000FF600}]
    sleep 5
  }
}

# Probe which DRV8316C SPI condition actually asserts nFAULT.
# Result 2026-10-16: only the frame-length error (3) works; an out-of-range
# address is NOT flagged on this sample, read or write.
proc clear_drv {} { spif 0x7D09 ; sleep 2 }
proc clear_bif {} { wr 0x40020010 0xFFFFFF7F ; sleep 1 }
init
halt
spi0_stabilise
report "start    "
clear_drv ; clear_bif
echo "--- (1) invalid-address WRITE (addr 0x3F) ---"
spif 0x007E ; sleep 2
report "addr-wr  "
clear_drv ; clear_bif
echo "--- (2) invalid-address READ (addr 0x3F) ---"
spif 0x00FF ; sleep 2
report "addr-rd  "
clear_drv ; clear_bif
echo "--- (3) truncated 8-clock frame ---"
spif8 0x0081 ; sleep 2
report "trunc    "
echo "--- restore ---"
spif 0x460B ; sleep 1
clear_drv
wr 0x40020044 [expr {[rd 0x40020044] & ~0x8000}]
clear_bif
snapshot "restored :"
resume
shutdown
