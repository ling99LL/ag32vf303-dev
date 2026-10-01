@echo off
set PATH=C:\Users\Administrator\.platformio\packages\tool-agrv_logic\bin;%PATH%
af.exe --batch -X "set QUARTUS_SDC true" -X "set FITTING Auto" -X "set FITTER full" -X "set EFFORT high" -X "set HOLDX default" -X "set SKEW basic" -X "set MODE QUARTUS" -X "set FLOW ALL" -F ./af_run.tcl
