# Headless Quartus compile (functional subset of af_quartus.tcl):
# af_ip.tcl only sets partition hint assignments and fails headless, skip it.
load_package flow
project_open cpld_board
set code [catch {execute_flow -compile} msg]
if { $code != 0 } { puts "COMPILE FAILED: $msg"; exit -1 }
puts "COMPILE OK"
