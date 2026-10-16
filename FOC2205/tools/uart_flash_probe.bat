@echo off
rem FOC2205 - UART ISP probe (READ ONLY, safe to run).
rem
rem Verifies the ROM UART boot loader is reachable without touching flash.
rem
rem PREREQUISITE (hardware, must be done first):
rem   1. Tie BOOT0 to 3V3. On this board BOOT0 (PIN_30) is hard-strapped to GND
rem      with a 10k pulldown, so the header is the only access point:
rem         U2.1 (BOOT0)  --->  3V3   (U2.5 or header pins 15/16)
rem      BOOT1 (PIN_15) stays at 0 via its own 10k pulldown -> {BOOT1,BOOT0}=01b
rem   2. POWER CYCLE the board. The boot loader only samples BOOT0 at reset, and
rem      the DAPLink has no nRST line, so a power cycle is the only way in.
rem
rem Why this works when JTAG cannot halt the core: with BOOT0=1 the ROM does NOT
rem load the CPLD bit stream, so the CPU never touches the CPLD peripheral that
rem is hanging the AHB bus. UART0 sits on the die-fixed PIN_20/21 pads.
rem
rem Expected: prints device/flash info. Timeouts mean the chip is not in the
rem boot loader (check the BOOT0 strap and that you really power cycled).
set TOOL=C:\Users\Administrator\.platformio\packages\tool-agrv_flashloader\bin\agrv32flash.exe
"%TOOL%" -b 57600 COM26
echo.
echo exit code = %ERRORLEVEL%
pause
