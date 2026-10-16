@echo off
rem FOC2205 - runtime probe without UART.
rem   PC              0x8000xxxx = running from flash, 0x0001xxxx = stuck in ROM (bad logic)
rem   GPIO2 bit1      nSLEEP (PIN_5),   non-zero = driver awake
rem   GPIO2 bit2      INL_ALL (PIN_28), non-zero = SPI self-test passed, 3x enabled
rem   SPIW_RXDATA0    0x60007000, last 16-bit DRV8316 frame (0x0000 = no response)
rem   SPIW_STATUS     0x60007008, bit0 = bridge0 frame done
"C:\Users\Administrator\.platformio\packages\tool-agrv_openocd\bin\openocd_cmd.bat" -s "C:\Users\Administrator\.platformio\platforms\AgRV\etc" -c "variable ADAPTER_SPEED 10000" -c "variable ADAPTER cmsis-dap" -f agrv2k.cfg -c "halt" -c "reg pc" -c "mem2array NSLP 32 0x40016008 1" -c "puts \"nSLEEP_PIN5=0x[format %%x $NSLP(0)]\"" -c "mem2array INL 32 0x40016010 1" -c "puts \"INL_ALL_PIN28=0x[format %%x $INL(0)]\"" -c "mem2array RX0 32 0x60007000 1" -c "puts \"SPIW_RXDATA0=0x[format %%x $RX0(0)]\"" -c "mem2array ST 32 0x60007008 1" -c "puts \"SPIW_STATUS=0x[format %%x $ST(0)]\"" -c "resume" -c "shutdown"
