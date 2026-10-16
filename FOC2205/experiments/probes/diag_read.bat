@echo off
rem FOC2205 - read the SPI diagnostic buffer over JTAG (no UART needed)
rem g_diag @ 0x20000eb8 : [0] IC_STAT [1] CTRL1 [2] CTRL2 [3] CTRL5 [4] CTRL6 [5] CTRL10
rem g_diag_done @ 0x20000ef8
"C:\Users\Administrator\.platformio\packages\tool-agrv_openocd\bin\openocd_cmd.bat" -s "C:\Users\Administrator\.platformio\platforms\AgRV\etc" -c "variable ADAPTER_SPEED 10000" -c "variable ADAPTER cmsis-dap" -f agrv2k.cfg -c "halt" -c "mem2array D 32 0x20000eb8 8" -c "puts \"IC_STAT=0x[format %%08x $D(0)]\"" -c "puts \"CTRL1 =0x[format %%08x $D(1)]\"" -c "puts \"CTRL2 =0x[format %%08x $D(2)]\"" -c "puts \"CTRL5 =0x[format %%08x $D(3)]\"" -c "puts \"CTRL6 =0x[format %%08x $D(4)]\"" -c "puts \"CTRL10=0x[format %%08x $D(5)]\"" -c "mem2array DD 32 0x20000ef8 1" -c "puts \"DONE=%d\"" -c "resume" -c "shutdown"
