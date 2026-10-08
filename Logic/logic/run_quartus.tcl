load_package flow
project_open logic_board
set code [catch {execute_flow -compile} msg]
if { $code != 0 } { puts "COMPILE FAILED: $msg"; exit -1 }
puts "COMPILE OK"
