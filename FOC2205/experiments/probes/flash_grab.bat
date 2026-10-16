@echo off
rem 抓"上电窗口"烧录：目标上电后到 drv_inl_high() 之前 PIN_28 未被驱动，
rem 此时 DAP 的 nTRST 不与之冲突，SWD 才连得上。连上后立刻 halt 冻结 CPU，
rem 再烧写。收尾 reset halt（不是 reset run）—— 芯片不跑固件，下次还能烧。
"C:/Users/Administrator/.platformio/packages/tool-agrv_openocd/bin/openocd_cmd.bat" -s "C:/Users/Administrator/.platformio/platforms/AgRV/etc" -c "variable ADAPTER_SPEED 4000" -c "variable ADAPTER cmsis-dap" -f agrv2k.cfg -c "init" -c "halt" -c "program {C:/Users/Administrator/Documents/AG32/FOC2205/.pio/build/foc2205/foc2205.elf} verify" -c "reset halt" -c "shutdown"
