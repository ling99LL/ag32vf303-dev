@echo off
rem ============================================================
rem  AG32 wave generator GUI launcher
rem  Requires Python with tkinter + pyserial (system Python 3.11
rem  on this machine already has both).
rem ============================================================
setlocal
set "PYW=C:\Users\Administrator\AppData\Local\Programs\Python\Python311\pythonw.exe"
if not exist "%PYW%" set "PYW=C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe"
if not exist "%PYW%" set "PYW=pythonw.exe"
start "" "%PYW%" "%~dp0wavegen_gui.py"
endlocal
