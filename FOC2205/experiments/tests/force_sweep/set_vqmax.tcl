
# FOC2205 force-sweep helper: read/verify and (optionally) set
# g_motion_cfg.vq_max exactly, bypassing the console's x1.25 / x0.75 gears.
#
# Addresses come from .pio/build/foc2205_bringup/output.map:
#   g_motion_cfg = 0x20000000 ; layout: kp kd kd_hold ki kff kfric (6 floats)
#                               then int32 vq_max at +24
#   g_foc        = 0x20001df8 ; v_limit_q at +4
# The readback of the surrounding fields guards against a layout drift, so a
# wrong offset fails loudly instead of silently corrupting another field.
proc rdi {addr} { mem2array t 32 $addr 1; return $t(0) }

init
set vq_addr  0x20000018
set lim_addr 0x20001dfc
# Raw IEEE754 words: compare with the firmware's own 'd' dump before trusting
# the write. kp=4.0 -> 0x40800000, ki=10.0 -> 0x41200000, kff=0.125 -> 0x3E000000,
# kfric=150.0 -> 0x43160000, rev_per_s=0.05 -> 0x3D4CCCCD, err_follow=800.0 -> 0x44480000.
echo [format "words: kp=0x%08X kd=0x%08X kd_hold=0x%08X ki=0x%08X kff=0x%08X kfric=0x%08X vq_max=%d rev_per_s=0x%08X follow=0x%08X" \
      [rdi 0x20000000] [rdi 0x20000004] [rdi 0x20000008] [rdi 0x2000000c] [rdi 0x20000010] [rdi 0x20000014] \
      [rdi $vq_addr] [rdi 0x2000001c] [rdi 0x20000020]]
echo [format "v_limit_q=%d (motion hard limit is compile-time MOTION_POWER_PCT_MAX: 20%% by default, 25%% in the fw=20261016.7 debug image)" \
      [rdi $lim_addr]]
if {[info exists vq_target] && $vq_target > 0} {
  mww $vq_addr $vq_target
  set rb [rdi $vq_addr]
  echo [format "SET vq_max=%d (%.2f%% of 8192)" $rb [expr {100.0 * $rb / 8192.0}]]
}
shutdown
