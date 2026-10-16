@echo off
"C:/Users/Administrator/.platformio/packages/tool-agrv_openocd/bin/openocd_cmd.bat" -d3 -s "C:/Users/Administrator/.platformio/platforms/AgRV/etc" -c "variable ADAPTER_SPEED 100" -c "variable ADAPTER cmsis-dap" -f agrv2k.cfg -c "init" -c "shutdown"
