@echo off
rem FOC2205 - Supra place and route: simulation\modelsim\foc2205.vo -> foc2205.bin
rem Run from FOC2205\logic after build_steps.bat.
cd /d "%~dp0"
"C:\Users\Administrator\.platformio\packages\tool-agrv_logic\bin\af_cmd.bat" -f af_run.tcl
