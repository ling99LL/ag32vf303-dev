@echo off
rem FOC2205 nFAULT test helper - run from the FOC2205 project root.
"C:\Users\Administrator\.platformio\packages\tool-agrv_openocd\bin\openocd_cmd.bat" -s "C:\Users\Administrator\.platformio\platforms\AgRV\etc" -c "variable ADAPTER_SPEED 10000" -c "variable ADAPTER cmsis-dap" -f agrv2k.cfg -f experiments/tests/nfault/nfault_inject.tcl
