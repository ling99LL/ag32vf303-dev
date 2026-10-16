@echo off
rem FOC2205 software reset through SYS reset register.
rem DAPLink has no nRESET signal on this board, so this is only a best effort.
"C:\Users\Administrator\.platformio\packages\tool-agrv_openocd\bin\openocd_cmd.bat" -s "C:\Users\Administrator\.platformio\platforms\AgRV\etc" -c "variable ADAPTER_SPEED 10000" -c "variable ADAPTER cmsis-dap" -f agrv2k.cfg -c "mww 0x03000004 0x00000001" -c "shutdown"
