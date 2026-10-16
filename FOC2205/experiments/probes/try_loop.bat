@echo off
"C:/Users/Administrator/.platformio/packages/tool-agrv_openocd/bin/openocd_cmd.bat" -s "C:/Users/Administrator/.platformio/platforms/AgRV/etc" -c "variable ADAPTER_SPEED 4000" -c "variable ADAPTER cmsis-dap" -f agrv2k.cfg -c "for {set i 0} {$i < 20} {incr i} { if {[catch {init} err] == 0} { echo GOT_IT; break }; sleep 50 }" -c "shutdown"
