@echo off
rem Verify the UART0 pads are muxed to the UART peripheral.
rem   UARTTXD(PIN_20) -> GPIO7 bit6 : GPIO7_BASE=0x4001B000, AFSEL=0x420, DIR=0x400, DATA[6]=0x018
rem   UARTRXD(PIN_21) -> GPIO6 bit1 : GPIO6_BASE=0x4001A000, AFSEL=0x420, DATA[1]=0x004
rem
rem IMPORTANT: GPIO7's APB clock is left OFF by the SDK. With the clock gated,
rem JTAG reads of ANY GPIO7 register return 0x00 (bus artifact, not the real
rem content) -- that is how "TX_AFSEL=0" was once misread as "AF write lost".
rem This script ORs APB_MASK_GPIO7 (1<<11) into SYS->APB_CLKENABLE (0x03000060)
rem itself before reading, so no firmware change is needed to debug this.
rem Expect: TX_AFSEL=0x00000040, RX_AFSEL=0x00000002.
set OCD="C:\Users\Administrator\.platformio\packages\tool-agrv_openocd\bin\openocd_cmd.bat"
%OCD% -s "C:\Users\Administrator\.platformio\platforms\AgRV\etc" -c "variable ADAPTER_SPEED 10000" -c "variable ADAPTER cmsis-dap" -f agrv2k.cfg -c "halt" -c "mem2array K 32 0x03000060 1" -c "mww 0x03000060 [expr {$K(0) | 0x800}]" -c "puts \"APB_CLKEN_BEFORE=0x[format %%08x $K(0)]\"" -c "mem2array A 32 0x4001B420 1" -c "puts \"TX_AFSEL=0x[format %%08x $A(0)]\"" -c "mem2array B 32 0x4001A420 1" -c "puts \"RX_AFSEL=0x[format %%08x $B(0)]\"" -c "resume" -c "shutdown"
