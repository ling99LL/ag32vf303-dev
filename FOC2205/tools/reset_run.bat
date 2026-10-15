@echo off
rem FOC2205 — 让芯片退出 halt 开始运行
rem pio 的 -t logic / -t upload 收尾都是 "reset halt"，烧完 CPU 停在断点上，
rem 串口不会有输出。跑这个脚本（或重新上电）才会真正执行固件。
"C:\Users\Administrator\.platformio\packages\tool-agrv_openocd\bin\openocd_cmd.bat" -s "C:\Users\Administrator\.platformio\platforms\AgRV\etc" -c "variable ADAPTER_SPEED 10000" -c "variable ADAPTER cmsis-dap" -f agrv2k.cfg -c "reset run" -c "shutdown"
