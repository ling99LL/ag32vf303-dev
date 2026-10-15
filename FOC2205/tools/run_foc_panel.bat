@echo off
rem FOC2205 上位机：角度显示 + 三相手动强制
rem 需要带 tkinter + pyserial 的 Python（本机为系统 Python 3.11）
"C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe" "%~dp0foc_panel.py"
pause
