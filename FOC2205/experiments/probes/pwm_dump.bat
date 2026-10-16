@echo off
rem Read GPTIMER0 (0x40020000) live state over JTAG -- answers "is the PWM actually
rem switching, and did the hardware brake (nFAULT) kill the outputs?"
rem   CR1   bit0 = CEN (counter running)
rem   SR    bit7 = BIF (break interrupt: nFAULT asserted at some point)
rem   BDTR  bit15 = MOE (main output enable), bit12 = BKE (break enable)
rem   CCR0/1/2 = the three phase duties; center = 1249 (ARR/2). 0 or 2499 = no modulation.
set OCD="C:/Users/Administrator/.platformio/packages/tool-agrv_openocd/bin/openocd_cmd.bat"
%OCD% -s "C:/Users/Administrator/.platformio/platforms/AgRV/etc" -c "variable ADAPTER_SPEED 10000" -c "variable ADAPTER cmsis-dap" -f agrv2k.cfg -c "halt" -c "mem2array T 32 0x40020000 18" -c "puts \"CR1=0x[format %%08x $T(0)]\"" -c "puts \"CR2=0x[format %%08x $T(1)]\"" -c "puts \"SR=0x[format %%08x $T(4)]\"" -c "puts \"CCMR0=0x[format %%08x $T(6)]\"" -c "puts \"CCER=0x[format %%08x $T(8)]\"" -c "puts \"CNT=0x[format %%08x $T(9)]\"" -c "puts \"ARR=0x[format %%08x $T(11)]\"" -c "puts \"CCR0=0x[format %%08x $T(13)]\"" -c "puts \"CCR1=0x[format %%08x $T(14)]\"" -c "puts \"CCR2=0x[format %%08x $T(15)]\"" -c "puts \"BDTR=0x[format %%08x $T(17)]\"" -c "resume" -c "shutdown"
