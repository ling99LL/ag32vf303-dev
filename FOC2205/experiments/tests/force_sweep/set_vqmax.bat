@echo off
rem FOC2205 force-sweep helper - run from the FOC2205 project root.
rem usage: experiments\tests\force_sweep\set_vqmax.bat [vq_value]
setlocal
set VQT=%1
if "%VQT%"=="" set VQT=0
"C:\Users\Administrator\.platformio\packages\tool-agrv_openocd\bin\openocd_cmd.bat" -s "C:\Users\Administrator\.platformio\platforms\AgRV\etc" -c "variable ADAPTER_SPEED 10000" -c "variable ADAPTER cmsis-dap" -c "set vq_target %VQT%" -f agrv2k.cfg -f experiments/tests/force_sweep/set_vqmax.tcl
endlocal
