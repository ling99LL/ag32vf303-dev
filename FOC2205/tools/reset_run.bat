@echo off
rem FOC2205: resume the MCU after upload (upload leaves it halted).
rem If the debug probe cannot halt the target, power-cycle the target board.
"C:\Users\Administrator\.platformio\packages\tool-agrv_openocd\bin\openocd_cmd.bat" -s "C:\Users\Administrator\.platformio\platforms\AgRV\etc" -c "variable ADAPTER_SPEED 10000" -c "variable ADAPTER cmsis-dap" -f agrv2k.cfg -c "reset run" -c "shutdown"

