@echo off
rem FOC loop health over JTAG (no UART needed). Prints RAW words to dodge Tcl/bat quoting.
rem Addresses drift on every rebuild -- regenerate with:
rem   nm -n <elf> | grep -wE "g_stage|s_isr_count|g_cur_cal"
rem Decode:
rem   STAGE   = 11 means the FOC loop is running
rem   ISR     = loop rate; take two reads ~1s apart, delta / dt ~= 40000/s
rem   CAL_W0  = {off_b:off_a} packed int16, CAL_W1 low half = off_c (expect ~2048 = 1.65V)
set OCD="C:/Users/Administrator/.platformio/packages/tool-agrv_openocd/bin/openocd_cmd.bat"
%OCD% -s "C:/Users/Administrator/.platformio/platforms/AgRV/etc" -c "variable ADAPTER_SPEED 10000" -c "variable ADAPTER cmsis-dap" -f agrv2k.cfg -c "halt" -c "mem2array W 32 0x20000f00 2" -c "puts \"CAL_W0=0x[format %%08x $W(0)]\"" -c "puts \"CAL_W1=0x[format %%08x $W(1)]\"" -c "mem2array V 32 0x20000f28 2" -c "puts \"STAGE=0x[format %%08x $V(0)]\"" -c "puts \"ISR=0x[format %%08x $V(1)]\"" -c "resume" -c "shutdown"
