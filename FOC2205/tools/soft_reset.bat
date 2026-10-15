@echo off
rem FOC2205 — 软复位（SYS->RST_CNTL bit0 = SYS_RST_SFT）
rem DAPLink 只接了 TCK/TMS，没有 nRST，openocd 的 "reset run" 对已经在跑的
rem 芯片不起作用。写软件复位位可以真正重启，用于抓完整 boot 日志。
"C:\Users\Administrator\.platformio\packages\tool-agrv_openocd\bin\openocd_cmd.bat" -s "C:\Users\Administrator\.platformio\platforms\AgRV\etc" -c "variable ADAPTER_SPEED 10000" -c "variable ADAPTER cmsis-dap" -f agrv2k.cfg -c "mww 0x03000004 0x00000001" -c "shutdown"
