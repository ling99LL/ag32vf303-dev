# FOC2205 驱动未供电联调记录

日期：2026-10-16。用户确认 DRV8316 未供电，并授权烧录、调试和完善上位机。使用 AGM CMSIS-DAP v2、COM26（115200 8N1），芯片 ID `0x40200001`。本记录承接同日的 `refactor-audit-2026-10-16.md`，覆盖其“尚未烧录”的阶段性结论。修改保留在工作区，未提交或推送。

## 新发现与修复

1. **MCU 外设时钟实际翻倍。** VE 的 `BUSCLK 100` 只配置逻辑侧，SDK 的 `board_init()` 不设置 MCU `PBUS_DIVIDER`。首次上板读到分频寄存器为 0、PCLK=200MHz；ARR=2499 的谷底 ISR 实测 40,015Hz，SPI DIV32 对应 6.25MHz，超过 DRV8316 的 5MHz 上限。现于 `board_init()` 前设置 `SYS_SetPclkDivider(1)`，让 UART 也按正确 PCLK 初始化。复测 PCLK=100MHz、寄存器=1，ISR=20,008Hz；SPI 配置频率为 3.125MHz。SPI 和 PWM 的引脚波形尚未仪器测量。
2. **驱动故障会跳过其他传感器自检。** 现分别执行驱动、编码器及 ADC 检查，驱动未就绪时继续提供采样和诊断，保持故障锁存并禁止通电对齐。
3. **原状态帧缺少有效性、故障及启动信息。** 在 proto=2 上增加 diag=1 扩展，报告固件版本、启动阶段、实测 ISR、uptime、驱动配置/状态、编码器当前帧有效性、磁场/按压、ADC 转换与标定状态、BRK、MOE 以及锁存原因。驱动轮询也检查关键配置读回，发现配置丢失即锁存故障。
4. **上位机误把命令发出当成执行成功。** 手动、幅度和掩码现以设备回传为准；未就绪、过期、缺失或不兼容状态帧禁止运动操作。连接时先发送释放，断开时尝试释放，重连清理旧接收队列；状态 2 秒未更新尝试发送释放、隐藏失效角度并标记上次状态。该机制不代替固件通信心跳，链路中断时无法保证释放命令送达。
5. **无效 ADC 数据和旧角度可能被当作有效值。** 面板区分原始 ADC LSB、校零后 LSB 和无有效采样；未供电时不换算成安培或宣称电流有效。角度累计在数据中断处停止跨段累加，检测重启后清零。手动面板取消后台自动保活，保留固件最后一次手动操作后 30 秒释放的行为。

## 上位机交付

- `tools/foc_panel.py`：中文诊断面板、角度表盘、连接/超时/故障提示、条件控制、故障寄存器和配置读取、Esc 释放、日志保存和 CSV 导出。
- `tools/foc_protocol.py`：独立状态解析和可操作条件，严格检查必需字段；缺字段不会填零后当作健康。
- 每次连接自动记录 CSV 到 `experiments/logs/panel-*.csv`；可导出最近 5000 帧，包含主机时间和设备状态。日志窗口限制 800 行，历史缓冲 2000 行。
- 启动方式：双击 `tools/run_foc_panel.bat`，或用带 pyserial、tkinter 的 Python 执行 `tools/foc_panel.py`。当前宿主要求 `proto=2,diag=1`；旧固件仅能诊断连接，动作按钮保持禁用。
- 用户偏好：日志采集、轮询、断言及CSV检查直接用串口脚本；桌面自动化只做必要界面验收，不用来获取日志。最后一次5秒脚本检查获得41帧有效状态，全部CRC=0、输出关闭，保存在 `experiments/logs/script-final-20261016.txt`。

## 编译与烧录

| 产物 | 大小 | SHA256 |
|---|---:|---|
| `.pio/build/foc2205/foc2205.bin`，版本 20261016.3 | 37,016B | `631d1c97a354ff0575dde5262990d23b0e50bbb588f4b5ca1a572ef1a4c69710` |
| `logic/foc2205.bin` | 23,940B | `db22f353ef50f3012ca9d29e76fd1419a67712be17c74692423d56ea81602001` |

RAM 8,540B（6.5%），Flash 37,016B（14.1%）。`-t logic` 和 `-t upload` 均写入并通过 OpenOCD 字节校验；压缩逻辑地址保持 `0x80034000`。逻辑沿用前阶段完成 Quartus/Supra 验证的位流，本阶段未修改逻辑设计。SDK 烧录结束会停机，本次额外执行 `tools/reset_run.bat` 后抓取启动日志。

## 实测结果

| 项目 | 本次证据 |
|---|---|
| 启动 | Flash 启动；SYSCLK=200MHz，PCLK=100MHz，LOGIC_BUSCLK=100MHz；stage=4、FAULT 锁存 |
| 驱动 | 关键寄存器读回 0，drvok=0；原因 `driver unavailable/config`，与用户声明未供电的条件一致；不能据此单独判定 SPI 布线好坏 |
| 编码器 | 启动 CRC 16/16；持续查询 215/215 帧有效、CRC 累计 0，静止角度 raw=11578（约254.4°）、磁场状态正常 |
| ADC | 转换完成、无超时；原始值约3396/3496/3513 LSB；零点不在1500..2600范围，cal=0，不能作为相电流 |
| 拒绝通电命令 | r/R/o/O/b/B/t/T/m/x7/w4/z 均未解除故障或使能输出；s 释放后仍保留故障；f 查询正常 |
| 持续通信 | 200轮约10Hz查询及前置检查，共215帧；关闭串口后重新打开、释放和查询通过 |
| 输出寄存器 | JTAG 读 GPTIMER0 BDTR=`0x61400`，MOE bit15=0；GPIO2 DATA bit2=0，INL低。仅为寄存器证据，未测物理输出波形 |
| 界面 | 实际启动并连接COM26；核对角度、故障、原始ADC提示及禁用按钮；读故障、断开清空、重连均正常 |
| 通信中断 | 通过JTAG暂停CPU约20秒；面板2秒后切换超时，隐藏指针并发送一次s；恢复CPU后自动恢复诊断显示 |
| 自动记录 | 已检查CSV数百帧有效，CRC=0、out=0；窗口stderr为空 |
| CSV导出 | 直接调用面板导出函数、用脚本读回比对，数据逐行一致；输出 `experiments/logs/panel-export-20261016.csv` |
| 软件回归 | C控制回归通过，包含新增传感器有效性及驱动配置丢失检查；5项Python宿主测试通过，覆盖缺帧/坏帧、就绪条件、确认前不更新手动状态、跨圈/重启/超时 |

运行日志在忽略目录 `experiments/logs/`：`flash-logic-20261016.txt`、`flash-mcu-final-20261016.txt`、`unpowered-20261016-094815.txt`、`unpowered-registers-final-20261016.txt`、`panel-timeout-final-20261016.txt`、`tests-final-20261016.txt` 及 `panel-*.csv`。

复现命令在项目目录执行：

```powershell
python experiments/tests/run_tests.py
python experiments/tests/hardware_unpowered.py COM26 --reset
python tools/foc_panel.py
```

硬件负向测试会先检查未对齐、驱动不可用、故障锁存、输出关闭，条件不符就停止；不要与面板同时占用串口。

## 后续物理验收

后续固件（20261016.4）已将启动策略改为无动作待命：开机不再自动通电对齐，校准必须由上位机按钮或串口 `a` 显式触发；`A` 或 `s` 可取消，校准幅度为归一化调制的 2%，并持续检查编码器、ADC 和电流阈值。该阈值是软件故障保护，不是经过仪器验证的限流器。

本次未给驱动供电，未验证驱动有电时的SPI读写、功率波形、真实电流、转子对齐和正反向运动。恢复VM供电后需要重启，完成驱动/ADC自检与通电对齐；当前启动故障不能用z绕过。重新启动时对齐会产生转子动作。基础运动的3/6/15rpm正反向各5圈仍待验收；电流闭环、实测限流、母线电压和固件通信心跳仍未实现。

## 重启后的有电探测（2026-10-16）

用户接通 9V 后，先执行了只读串口检查并发送 `s?f`（`s` 仅释放输出）。COM26 可枚举，但 4 秒内收到 0 字节；随后以 9600、19200、38400、57600、115200、230400、460800、1000000 波特率逐一查询，仍全部为 0 字节。期间没有发送校准、运动或手动通电命令。

DAPLink 仍能读到 SWD DPIDR `0x2ba01477`，但 OpenOCD 在 1000/10000 kHz 都报告目标核 `dmstatus=0x00030ca2`（running）且 `Unable to halt`；该探针报告没有可用的 SRST 信号，因此 `reset_run.bat` 和标准 `pio run -t upload` 都不能复位/重烧当前运行态。已将 `tools/reset_run.bat` 改为 ASCII 注释和 CRLF，消除了 cmd 把中文注释当命令的脚本错误；这不改变硬件状态。

当前结论是目标板需要一次真实的 9V 断电再上电，之后才能继续脚本状态读取、确认 `out=0`/MOE/DRV/编码器/ADC，再决定是否点击手动校准。物理复位完成前不执行校准和运动。

## 再次复测（2026-10-16 13:30）

用户重启后，在没有发送校准、运动或手动输出命令的情况下再次运行：

```powershell
python experiments/tests/hardware_unpowered.py COM26
pio run -e foc2205 -t upload
```

串口脚本仍未收到兼容的 `proto=2,diag=1` 状态帧。上传仍在擦除/写入前失败：SWD DPIDR 为 `0x2ba01477`，但目标核 `dmstatus=0x00030ca2`，OpenOCD 报 `Unable to halt`、`Fatal: Hart 0 failed to halt during examine` 和 `Unsupported DTM version: -1`。因此本次没有改写 Flash，不能把它记为烧录成功。随后只读的 1000 kHz OpenOCD 探测结果相同。

本次代码改动后的本地验证通过：`pio run -e foc2205 -t clean` + `pio run -e foc2205`，Flash 38,236 B、RAM 8,872 B；`python experiments/tests/run_tests.py` 通过。校准看门狗已改为只有有效查询/启动/取消/释放字符才续期，串口噪声不能无限延长带电校准。

## 串口 ROM loader 烧录复测

芯片进入 UART loader 后，使用 `AGM_PIO_UPLOAD_PROTOCOL=serial` 强制 PlatformIO 走串口下载：

```powershell
$env:AGM_PIO_UPLOAD_PROTOCOL = 'serial'
pio run -e foc2205 -t upload -p COM26
```

2026-10-16 实测成功：`agrv32flash` 以 `460800 8E1` 连接 COM26，识别 `0x40200001 (AGM32RV40xxx)`，检查逻辑地址 `0x80034000`，完成擦除、写入、校验和复位。复位后脚本收到 `fw=20261016.4,stage=90,out=0`，说明安全固件正常运行且未启动 CPLD SPI/ADC、校准或电机动作。该次操作只重写 MCU 固件；逻辑位流未被串口固件上传命令重写。

## SWD 下载恢复复测

串口烧录后切回 CMSIS-DAP/OpenOCD，执行 `pio run -e foc2205 -t upload -p COM26`。10 MHz SWD 实测恢复正常：DPIDR=`0x2ba01477`，RISC-V core examination 成功，CPU 成功 halt；随后完成 Flash 擦除、写入 27,660 B、校验和 `reset halt`，全流程返回成功。执行 `tools/reset_run.bat` 后，COM26 持续收到安全镜像状态 `fw=20261016.4,stage=90,out=0`。因此 SWD 链路和芯片 Flash 当前均可用；之前的失败属于运行态/系统总线挂死导致的 halt 失败，不是 SWD 物理链路永久损坏。
