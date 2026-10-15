@echo off
setlocal
rem ===========================================================================
rem  抓"上电窗口"烧录 —— 给板子断电再上电，本脚本会自动完成烧写
rem
rem  为什么需要这一步：
rem    PIN_28 既是 JNTRST 焊盘又是 DRV8316 的 INL_ALL。DAPLink 把 nTRST 恒
rem    驱动为低；固件一上电就把这个 pad 释放成 GPIO 并驱动为高，两个驱动源
rem    在同一根线上顶牛，SWD 线上只剩 JUNK，openocd 报
rem    "Error connecting DP: cannot read IDR"，从此再也烧不进去。
rem    只有在上电后、固件把 INL 拉高之前的那个窗口里 SWD 才是通的。
rem
rem  用法：
rem    1) 给板子断电（断 VM 或断 3V3 都行；拔 DAPLink 没用，板子是独立供电）
rem    2) 重新上电
rem    3) 双击本文件。烧录成功会自动停下，失败就一直重试，Ctrl+C 退出。
rem
rem  烧进去的新固件里 INL 只在运动期间拉高，空闲保持低 —— 以后随时能烧，
rem  不用再断电。
rem ===========================================================================

set OCD=C:\Users\Administrator\.platformio\packages\tool-agrv_openocd\bin\openocd_cmd.bat
set ETC=C:\Users\Administrator\.platformio\platforms\AgRV\etc
set ELF=C:\Users\Administrator\Documents\AG32\FOC2205\.pio\build\foc2205\foc2205.elf
set LOG=%TEMP%\ag32_grab.log

echo.
echo 等待上电窗口 ... (Ctrl+C 退出)
echo.

:loop
"%OCD%" -s "%ETC%" -c "variable ADAPTER_SPEED 4000" -c "variable ADAPTER cmsis-dap" ^
  -f agrv2k.cfg -c "init" -c "halt" -c "program {%ELF%} verify" -c "reset halt" -c "shutdown" ^
  > "%LOG%" 2>&1

findstr /C:"Verified OK" /C:"verified OK" /C:"** Verified" "%LOG%" >nul
if errorlevel 1 (
  goto loop
)

echo.
echo ****************************************
echo   烧录并校验成功
echo ****************************************
type "%LOG%"
echo.
echo 芯片已停在 reset halt 状态。要运行固件请执行 tools\reset_run.bat，
echo 或由我这边继续（复位 + 跑 r 转一圈测抖动）。
