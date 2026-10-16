@echo off
rem FOC2205 - dump RISC-V trap CSRs to find why the firmware lands in exception_handler
"C:\Users\Administrator\.platformio\packages\tool-agrv_openocd\bin\openocd_cmd.bat" -s "C:\Users\Administrator\.platformio\platforms\AgRV\etc" -c "variable ADAPTER_SPEED 10000" -c "variable ADAPTER cmsis-dap" -f agrv2k.cfg -c "halt" -c "reg pc" -c "reg mcause" -c "reg mepc" -c "reg mtval" -c "reg mstatus" -c "reg mhartid" -c "shutdown"
