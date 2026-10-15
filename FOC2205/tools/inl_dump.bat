@echo off
rem Dump the DRV8316 control pads on GPIO2 (nSLEEP / INL_ALL).
rem The openocd commands live in inl_probe.cfg so cmd.exe never has to escape
rem TCL operators ('>>' and '&' break inside a -c "..." argument: "missing quote").
set OCD="C:\Users\Administrator\.platformio\packages\tool-agrv_openocd\bin\openocd_cmd.bat"
set HERE=%~dp0
%OCD% -s "C:\Users\Administrator\.platformio\platforms\AgRV\etc" -c "variable ADAPTER_SPEED 10000" -c "variable ADAPTER cmsis-dap" -f agrv2k.cfg -f "%HERE%inl_probe.cfg"
