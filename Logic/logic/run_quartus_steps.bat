@echo off
rem ============================================================================
rem AG32 Logic Analyzer - Step-wise Quartus Compilation (revision: logic_board)
rem ============================================================================
rem WHY THIS SCRIPT EXISTS
rem   On this machine the Quartus II 13 one-shot flow (run_quartus.tcl via
rem   execute_flow) aborts right after quartus_map with:
rem       Error (293007): Current module quartus_map ended unexpectedly
rem   Root cause verified 2026-10-12: every Quartus tool completes its work and
rem   writes a "Successful" summary report, but its process exit path raises a
rem   Windows fast-fail (exit code 0xC0000409, STATUS_STACK_BUFFER_OVERRUN).
rem   execute_flow treats the non-zero exit code as a hard failure and stops;
rem   the very same steps, run one by one outside execute_flow, build fine.
rem   This is an environment/tool issue and is independent of the design source.
rem
rem WHAT IT DOES
rem   Runs the same seven steps as the standard flow, tolerating the spurious
rem   exit codes, and validates each step's official summary report:
rem     [1/7] quartus_sh -t af_ip.tcl (IP/macro partition scan; regenerates
rem           the alta_auto PARTITION lines in logic_board.qsf - keeps the
rem           alta_dac/alta_adc analog hard macros alive through synthesis)
rem     [2/7] quartus_map            -> quartus_logs\logic_board.map.summary
rem     [3/7] quartus_cdb --merge=on -> quartus_logs\logic_board.merge.summary
rem     [4/7] quartus_fit --check_ios (I/O allocation check)
rem     [5/7] quartus_fit            -> quartus_logs\logic_board.fit.summary
rem     [6/7] quartus_sta            (timing analysis)
rem     [7/7] quartus_eda            (EDA/Verilog netlist writer refresh)
rem   Build product for Supra: simulation\modelsim\logic_board.vo
rem   Step logs: quartus_step*.log (git-ignored)
rem
rem USAGE (from Logic\logic)
rem     run_quartus_steps.bat
rem     run_supra.bat            (Supra place & route -> logic_board.bin)
rem   then from Logic:
rem     pio run -e logic_analyzer -t logic     (flash the new bitstream)
rem     pio run -e logic_analyzer -t upload    (flash the MCU firmware)
rem ============================================================================

setlocal
cd /d "%~dp0"

set "QBIN=C:\altera\13.0sp1\quartus\bin64"
set "QLOG=quartus_logs"

if not exist "%QBIN%\quartus_map.exe" (
  echo [ERROR] Quartus II 13 not found at %QBIN%
  exit /b 1
)

echo [1/7] quartus_sh -t af_ip.tcl - IP/macro partition scan ...
"%QBIN%\quartus_sh.exe" -t af_ip.tcl > quartus_step0_af_ip.log 2>&1
echo       exit code %ERRORLEVEL% - spurious fast-fail is expected
rem af_ip.tcl removes ALL alta_auto lines first and then re-creates them for
rem every IP instance found in the mapped netlist - so a line here proves the
rem alta_dac hard macro survived synthesis (the exact bug fixed on 2026-10-12).
findstr /c:"macro_inst_gen_per" logic_board.qsf >nul 2>&1
if errorlevel 1 (
  echo       [ERROR] alta_dac macro partition missing in logic_board.qsf.
  echo               The DAC hard macro was removed by synthesis. Check the keep-guard
  echo               in analog_ip.v and quartus_step0_af_ip.log. Do not flash this build.
  exit /b 2
) else (
  echo       alta_dac macro partition present in logic_board.qsf
)

echo [2/7] quartus_map - analysis and synthesis ...
"%QBIN%\quartus_map.exe" --read_settings_files=on --write_settings_files=off logic_board -c logic_board > quartus_step1_map.log 2>&1
echo       exit code %ERRORLEVEL% - spurious fast-fail is expected
findstr /c:"Analysis & Synthesis Status : Successful" "%QLOG%\logic_board.map.summary" >nul 2>&1
if errorlevel 1 (
  echo       [ERROR] Synthesis FAILED. See %QLOG%\logic_board.map.rpt
  exit /b 2
)
echo       map.summary reports: Successful

echo [3/7] quartus_cdb - partition merge ...
"%QBIN%\quartus_cdb.exe" --read_settings_files=off --write_settings_files=off logic_board -c logic_board --merge=on > quartus_step2_merge.log 2>&1
echo       exit code %ERRORLEVEL% - spurious fast-fail is expected
findstr /c:"Partition Merge Status : Successful" "%QLOG%\logic_board.merge.summary" >nul 2>&1
if errorlevel 1 (
  echo       [ERROR] Partition merge FAILED. See %QLOG%\logic_board.merge.rpt
  exit /b 2
)
echo       merge.summary reports: Successful

echo [4/7] quartus_fit --check_ios - I/O allocation check ...
"%QBIN%\quartus_fit.exe" --read_settings_files=off --write_settings_files=off logic_board -c logic_board --check_ios > quartus_step3_fit_check.log 2>&1
echo       exit code %ERRORLEVEL% - spurious fast-fail is expected

echo [5/7] quartus_fit - fitting ...
"%QBIN%\quartus_fit.exe" --read_settings_files=off --write_settings_files=off logic_board -c logic_board > quartus_step4_fit.log 2>&1
echo       exit code %ERRORLEVEL% - spurious fast-fail is expected
findstr /c:"Fitter Status : Successful" "%QLOG%\logic_board.fit.summary" >nul 2>&1
if errorlevel 1 (
  echo       [ERROR] Fitting FAILED. See %QLOG%\logic_board.fit.rpt
  exit /b 2
)
echo       fit.summary reports: Successful

echo [6/7] quartus_sta - timing analysis ...
"%QBIN%\quartus_sta.exe" logic_board -c logic_board > quartus_step5_sta.log 2>&1
echo       exit code %ERRORLEVEL% - spurious fast-fail is expected

echo [7/7] quartus_eda - EDA netlist writer ...
"%QBIN%\quartus_eda.exe" --read_settings_files=off --write_settings_files=off logic_board -c logic_board > quartus_step6_eda.log 2>&1
echo       exit code %ERRORLEVEL% - spurious fast-fail is expected

if not exist "simulation\modelsim\logic_board.vo" (
  echo [ERROR] Netlist simulation\modelsim\logic_board.vo not found - build incomplete.
  exit /b 2
)

rem Final guard: the DAC hard macro must be instantiated in the written netlist.
rem (2026-10-12 post-mortem: a dangling dout let Quartus delete alta_dac as dead
rem logic, which silently disabled the PIN_11 analog output AND the Supra
rem FIXED_COORD binding of DAC0 to pad "22 11". The keep-guard in analog_ip.v
rem prevents it; this check makes sure a regression never reaches the board.)
findstr /c:"alta_dac" "simulation\modelsim\logic_board.vo" >nul 2>&1
if errorlevel 1 (
  echo [ERROR] alta_dac hard macro missing from the netlist - PIN_11 analog output would be dead.
  echo         Check the dac_dout keep-guard in analog_ip.v. Do not flash this build.
  exit /b 2
)
echo       netlist contains alta_dac hard macro

echo.
echo BUILD OK - netlist ready: simulation\modelsim\logic_board.vo
echo Next step: run_supra.bat  (Supra place and route -^> logic_board.bin)
exit /b 0
