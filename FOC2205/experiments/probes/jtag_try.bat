@echo off
"C:/Users/Administrator/.platformio/packages/tool-agrv_openocd/bin/openocd_cmd.bat" -s "C:/Users/Administrator/.platformio/platforms/AgRV/etc" -c "variable ADAPTER_SPEED 2000" -c "variable ADAPTER cmsis-dap" -c "variable TRANSPORT jtag" -f agrv2k.cfg -c "reset run" -c "shutdown"
