@echo off
"C:/Users/Administrator/.platformio/packages/tool-agrv_openocd/bin/openocd_cmd.bat" -s "C:/Users/Administrator/.platformio/platforms/AgRV/etc" -c "variable ADAPTER_SPEED 50" -c "variable ADAPTER cmsis-dap" -c "transport select jtag" -f agrv2k.cfg -c "init" -c "scan_chain" -c "shutdown"
