@echo off
rem Clock-tree evidence: SYS->CLK_CNTL (0x0300000C) and SYS->PBUS_DIVIDER (0x03000038)
set OCD="C:\Users\Administrator\.platformio\packages\tool-agrv_openocd\bin\openocd_cmd.bat"
%OCD% -s "C:\Users\Administrator\.platformio\platforms\AgRV\etc" -c "variable ADAPTER_SPEED 10000" -c "variable ADAPTER cmsis-dap" -f agrv2k.cfg -c "halt" -c "mem2array K 32 0x0300000c 1" -c "puts \"CLK_CNTL=0x[format %%08x $K(0)]\"" -c "mem2array P 32 0x03000038 1" -c "puts \"PBUS_DIVIDER=[format %%d $P(0)]\"" -c "mem2array E 32 0x03000060 1" -c "puts \"APB_CLKEN=0x[format %%08x $E(0)]\"" -c "resume" -c "shutdown"
