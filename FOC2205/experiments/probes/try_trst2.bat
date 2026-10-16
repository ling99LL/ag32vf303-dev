@echo off
"C:/Users/Administrator/.platformio/packages/tool-agrv_openocd/bin/openocd_cmd.bat" -s "C:/Users/Administrator/.platformio/platforms/AgRV/etc" -c "variable ADAPTER_SPEED 1000" -c "variable ADAPTER cmsis-dap" -f agrv2k.cfg -c "reset_config trst_only" -c "init" -c "shutdown"
