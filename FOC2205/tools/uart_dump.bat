@echo off
rem Read UART0 registers over JTAG to verify the console is really configured.
rem UART0_BASE = 0x40025000 ; DR=0x00 FR=0x18 IBRD=0x24 FBRD=0x28 LCR_H=0x2C CR=0x30
set OCD="C:\Users\Administrator\.platformio\packages\tool-agrv_openocd\bin\openocd_cmd.bat"
%OCD% -s "C:\Users\Administrator\.platformio\platforms\AgRV\etc" -c "variable ADAPTER_SPEED 10000" -c "variable ADAPTER cmsis-dap" -f agrv2k.cfg -c "halt" -c "mem2array U 32 0x40025018 1" -c "puts \"FR=0x[format %%08x $U(0)]\"" -c "mem2array I 32 0x40025024 1" -c "puts \"IBRD=[format %%d $I(0)]\"" -c "mem2array F 32 0x40025028 1" -c "puts \"FBRD=[format %%d $F(0)]\"" -c "mem2array L 32 0x4002502c 1" -c "puts \"LCR_H=0x[format %%08x $L(0)]\"" -c "mem2array C 32 0x40025030 1" -c "puts \"CR=0x[format %%08x $C(0)]\"" -c "mem2array M 32 0x20000f2c 1" -c "puts \"MSG_UART=0x[format %%08x $M(0)]\"" -c "resume" -c "shutdown"
