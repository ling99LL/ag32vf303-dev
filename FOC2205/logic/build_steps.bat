@echo off
rem FOC2205 bitstream rebuild (step-wise)
rem ---------------------------------------------------------------------------
rem WHY: on this machine the one-shot flow (af_quartus.tcl via execute_flow)
rem aborts with "Error (293007): Current module quartus_map ended unexpectedly".
rem Every Quartus tool finishes its work and writes a Successful summary but its
rem exit path raises a Windows fast-fail (0xC0000409); execute_flow treats that
rem exit code as fatal and stops. Run separately, the same steps build fine.
rem Two extra fixes were needed here:
rem   * PARALLEL_SYNTHESIS OFF in foc2205.qsf - the parallel-synthesis child
rem     processes fast-fail, so quartus_map never commits its db.
rem   * quartus_eda must run AFTER quartus_fit (it emits the post-fit netlist);
rem     running it right after merge makes it die with no output at all.
rem Build product for Supra: simulation\modelsim\foc2205.vo
rem ---------------------------------------------------------------------------
setlocal
cd /d "%~dp0"
set "QBIN=C:\altera\13.0sp1\quartus\bin64"

echo [1/6] af_ip.tcl - macro partition scan
"%QBIN%\quartus_sh.exe" -t af_ip.tcl > step1_af_ip.log 2>&1
echo       exit %ERRORLEVEL% (spurious fast-fail is expected)

echo [2/6] quartus_map - analysis and synthesis
"%QBIN%\quartus_map.exe" foc2205 > step2_map.log 2>&1
echo       exit %ERRORLEVEL%
findstr /c:"Analysis & Synthesis Status" quartus_logs\foc2205.map.summary

echo [3/6] quartus_cdb --merge - partition merge
"%QBIN%\quartus_cdb.exe" foc2205 --merge > step3_merge.log 2>&1
echo       exit %ERRORLEVEL%
findstr /c:"Partition Merge Status" quartus_logs\foc2205.merge.summary

echo [4/6] quartus_fit - place and route (cyclone shell)
"%QBIN%\quartus_fit.exe" foc2205 > step4_fit.log 2>&1
echo       exit %ERRORLEVEL%
findstr /c:"Fitter Status" quartus_logs\foc2205.fit.summary

echo [5/6] quartus_sta - timing analysis
"%QBIN%\quartus_sta.exe" foc2205 > step5_sta.log 2>&1
echo       exit %ERRORLEVEL%

echo [6/6] quartus_eda - verilog netlist writer
"%QBIN%\quartus_eda.exe" foc2205 --simulation --tool=modelsim --format=verilog > step6_eda.log 2>&1
echo       exit %ERRORLEVEL%
findstr /c:"Status" quartus_logs\foc2205.eda.summary 2>nul
echo === done ===
