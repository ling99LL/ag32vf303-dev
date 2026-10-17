@echo off
rem FOC2205 - UART ISP full reflash: CPLD bit stream first, then MCU program.
rem
rem PREREQUISITE (hardware, must be done first):
rem   1. Tie BOOT0 (PIN_30 / header U2.1) to 3V3 (U2.5 or header pins 15/16).
rem      It is otherwise hard-strapped to GND by a 10k pulldown.
rem   2. POWER CYCLE the board (DAPLink has no nRST; boot loader samples BOOT0
rem      only at reset).
rem
rem AFTER THIS SCRIPT: remove the BOOT0 jumper and power cycle again, otherwise
rem the board will keep entering the boot loader instead of running the firmware.
rem
rem Order matters: program first, logic LAST.  The program write erases the
rem whole flash, so writing logic first would silently delete the bit stream.
set TOOL=C:\Users\Administrator\.platformio\packages\tool-agrv_flashloader\bin\agrv32flash.exe
set PROJ=C:\Users\Administrator\Documents\AG32\FOC2205

echo ==== 1/2 writing MCU program ====
"%TOOL%" -b 57600 -S 0x80000000 -w "%PROJ%\.pio\build\foc2205\foc2205.bin" -v COM26
if errorlevel 1 goto fail

echo ==== 2/2 writing CPLD bit stream ====
"%TOOL%" -b 57600 -S 0x80034000 -l "%PROJ%\logic\foc2205.bin" -v COM26
if errorlevel 1 goto fail

rem Do not use -K/-M here: it compares the raw file against the generated
rem 0x1100-byte decompressor + compressed layout and reports a false mismatch.

echo ==== DONE: remove the BOOT0 jumper, then power cycle ====
pause
exit /b 0

:fail
echo ==== FAILED (exit %ERRORLEVEL%) ====
pause
exit /b 1
