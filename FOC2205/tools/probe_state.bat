@echo off
rem FOC2205 - read current chip state via OpenOCD when the hart refuses to halt.
rem
rem Why this exists: when the AHB bus hangs (CPU stuck on a load to an
rem unresponsive CPLD peripheral) the normal "init; halt; reg" flow dies at
rem examine. This script bypasses examine and pokes the Debug Module directly:
rem   DMI 0x10 dmcontrol   0x11 dmstatus   0x12 hartinfo
rem       0x16 abstractcs  0x38 sbcs       0x39 sbaddress0  0x3c sbdata0
rem
rem Reading key:
rem   dmstatus 0x00030ca2 -> version=2 authenticated=1 anyrunning/allrunning=1
rem                          anyhalted/allhalted=0  => hart running, won't halt
rem   sbcs bit29          -> sbbusy=1  => system bus transaction never completed
rem Usage: tools\probe_state.bat
"C:\Users\Administrator\.platformio\packages\tool-agrv_openocd\bin\openocd_cmd.bat" -s "C:\Users\Administrator\.platformio\platforms\AgRV\etc" -c "variable ADAPTER_SPEED 10000" -c "variable ADAPTER cmsis-dap" -f agrv2k.cfg -c "init" -c "echo DMSTATUS" -c "riscv dmi_read 0x11" -c "echo DMCONTROL" -c "riscv dmi_read 0x10" -c "echo ABSTRACTCS" -c "riscv dmi_read 0x16" -c "echo HARTINFO" -c "riscv dmi_read 0x12" -c "echo SBCS_busy_check" -c "riscv dmi_read 0x38" -c "shutdown"
