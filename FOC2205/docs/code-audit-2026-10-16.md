# FOC2205 代码审查补充记录

日期：2026-10-16。审查对象是当前工作区 `FOC2205` 的 MCU 固件、CPLD SPI 桥和 Python 上位机。此前的重构与归档记录见 [refactor-audit-2026-10-16.md](refactor-audit-2026-10-16.md)。本记录只写本次烧录复测和复查后仍需处理的问题，不把编译或桩测试当作电机验收。

## 烧录复测

在目标板保持 9V 供电、空载且没有发送运动/校准命令的条件下运行：

```text
pio run -e foc2205 -t upload
```

结果失败，发生在擦除和写入之前：

```text
SWD DPIDR 0x2ba01477
Unable to halt. dmstatus=0x00030ca2
Fatal: Hart 0 failed to halt during examine
Unsupported DTM version: -1
```

因此本次没有改写 Flash。SWD 探针可识别，但目标核处于 running，当前不能证明烧录链路正常。结合探针报告没有可用 SRST，需真实断开 9V、等待数秒再上电后重试；在此之前不点击校准。

## 仍存在的风险

### P1：普通运动没有主机通信失联保护

`motion_step_isr()` 在 [motion.c](../src/motion.c) 中只按动作时长、位置误差和传感器故障退出。位置、开环和扭矩动作没有主机心跳；串口在动作开始后断开时，固件仍可能继续输出，直到动作完成或内部超时。手动模式的 30 秒释放和校准的 5 秒看门狗不能覆盖这些模式。

建议下一轮实现带序号的命令/应答协议，并让所有功率动作在超过明确的通信超时后释放输出。该项需要先确定“纯串口命令是否也必须保持心跳”的产品语义，不能只在上位机里补一个定时器。

### P1：调制百分比和软件电流阈值都不是实测限流

`MOTION_POWER_PCT_MAX=20`、`g_foc.v_limit_q` 和 `CURRENT_TRIP_LSB=200` 只限制归一化调制或 ADC 原始码。代码没有母线电压采样、相电流闭环或经过仪器验证的电流上限；9V 无限流电源下，负载、采样偏置和 DRV 保护决定的实际电流仍未知。校准阶段的 2% 也只是调制幅度比例，不能写成“2% 电流”。

在完成示波器/电流探头验证前，只允许空载、低速、短时人工操作，并把 DRV 硬件故障和 ADC 超阈值当作故障释放条件。

### P1：PIN_28 同时承担 INL_ALL 和 JNTRST

当前 VE 将 `GPIO2_2` 映射到 `PIN_28`，启动时调用 `SYS_DisableNJTRST()`，运动时 `pwm3ph_arm()` 拉高 INL。若连接的调试器仍驱动 nTRST 为低，INL 与探针会发生电气争用，并可能使再次 halt/烧录失败。此次 OpenOCD 能读 DPIDR 但不能 halt，发生在写 Flash 之前，不能排除该复用冲突；也不能据此断言就是唯一原因。

建议硬件上将 INL_ALL 改到纯 GPIO，或确认探针在该板上完全释放 nTRST；在确认前，运动期间不要连接会主动驱动 nTRST 的探针。

### P2：字符协议没有命令序号和执行确认

`console.c` 与 `foc_panel.py` 仍使用单字节/双字节字符命令。上位机通过后续状态帧推断结果，没有命令 ID、应答状态或重复命令抑制；断线重连、缓存字节和延迟字节可能造成旧命令在新会话执行。当前面板的状态门控只能降低概率，不能替代协议层确认。

### P2：运行时调参字段与 ISR 并发读写

串口处理在 [console.c](../src/console.c) 直接修改 `g_motion_cfg` 和 `g_foc.angle_filt_alpha`，而 PWM ISR 在 [motion.c](../src/motion.c) / [foc.c](../src/foc.c) 同时读取。当前 RV32 上单个 32 位写通常是原子的，但 C 语言层面没有同步保证，浮点调参可能在动作中读取到未定义的中间状态。应把调参封装为短临界区 API，并禁止动作运行中修改会改变换向和功率的字段。

### P2：CPLD SPI 桥依赖隐含帧长度

`logic/spi_mode_wrap.v` 以硬 SPI 的 CSN、SCK 边沿产生接收移位和 DONE，没有在逻辑侧校验 16/24 个时钟。固件已加入完成位和超时检查，但错误的硬 SPI 配置仍可能产生“完成且长度错误”的帧。建议在桥内增加计数器，长度不符时 DONE 置错并让固件拒绝该帧。

另外，DONE 是 sticky 位，只能通过读取对应 RXDATA 清除。现已在 DRV8316 和 MT6701 发起新帧前先读 RXDATA，避免上一次超时/错误传输留下的 DONE 让下一帧误用旧数据。

## 本次修复

校准看门狗原来在 `console_poll()` 收到任何字符时续期，串口乱码或噪声也可以无限延长校准输出。现只对 `?`、`a/A`、释放命令续期；改动位于 [console.c](../src/console.c)。同时修复 SPI 桥 sticky DONE 的旧帧清除，改动位于 [drv8316.c](../src/drv8316.c) 和 [mt6701.c](../src/mt6701.c)。

## 验证

- `pio run -e foc2205 -t clean` 后完整 `pio run -e foc2205`：通过；Flash 38,252 B，RAM 8,872 B。
- `python experiments/tests/run_tests.py`：通过，6 项 Python 测试、C 控制回归和 Python 语法检查全部通过。
- 本次 `pio run -e foc2205 -t upload`：失败于 OpenOCD halt，未进入擦除/写入。
- 当前未执行校准、运动、功率波形、电流/温升或真实电机转速验收。

## 用户重新上电后的再次状态与复位尝试（2026-10-16 14:06）

用户重新接通 9V 后，脚本仅发送 `s?`，COM26 在 3 秒内仍无串口字节；设备管理器仍枚举 `USB 串行设备 (COM26)`。随后再次执行 `pio run -e foc2205 -t upload`，结果与前次一致：SWD DPIDR=`0x2ba01477`，`dmstatus=0x00030ca2`，OpenOCD 在擦除/写入前无法 halt，故 Flash 未改写。只读 DMI 状态为 `ABSTRACTCS=0x10000001`、`SBCS=0x20040407`（busy），目标未进入可调试停机态。

尝试通过 SYS 软件复位寄存器复位时，OpenOCD 先报告 `Target not examined yet`，说明当前调试模块无法执行 AHB 写入；没有发送任何校准、运动或手动输出命令。`tools/soft_reset.bat` 已改为 ASCII 注释以消除 cmd 编码噪声，但不改变硬件复位能力。当前仍需真实断开 9V、等待数秒并重新上电；在获得状态帧和成功 halt/校验前，不进行校准或运动。
