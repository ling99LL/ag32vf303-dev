# FOC2205

AG32VF303KCU6 (QFN32) + MT6701QT-STD + DRV8316C 三芯片 FOC 驱动板 —— 力反馈旋钮（2205 电机）。

**完全独立工程**，与 `foc\foc_knob` 零交叉（不包含、不引用其任何文件）。

## 首版模块边界（已确认）

首版交付目标是经过完整测试、可嵌入其他设备的机电力反馈旋钮模块：控制 PCB、2205 电机、MT6701 磁编码器/磁铁、宿主连接器和安装基准。模块本地运行位置环、手感逻辑与安全保护，通过 UART TTL 115200 正式数据包协议与宿主通信，并提供电脑上位机；独立外壳、显示和最终应用语义不属于首版边界。

当前先验收空载稳定正反连续转圈，按开环通过后再闭环的顺序推进；正常停止后释放电机、允许自由转动，第一种具体手感模式暂不定案。成品要求在心跳超时、驱动故障或编码器 CRC 异常时立即释放力矩并关闭功率级，保留串口通信。收到恢复命令并确认故障已消除后，仅进入无输出待命，必须等待新的运动命令。首轮开环按 3、6、15 rpm 正反各实际连续转满 5 圈、每个组合先通过 1 次执行；方向正确且无失步、反抽或异常中止才通过，停止位置暂不考核，速度波动先记录。六项通过后进入闭环，重复性后续验收。详见 [基础运动验收](docs/basic-motion-acceptance.md)。

| 项 | 值 |
|---|---|
| MCU | AG32VF303KCU6，QFN32，`logic_device = AGRV2KQ32` |
| 电机 | 2205（型号 2804）：12N14P **极对数 7**，8V/2.5A/20W/6000RPM，0.03N·m，适用 7.4~16V（供电取 8~16V）→ [docs/电机参数.md](docs/电机参数.md) |
| 磁编码器 | MT6701QT-STD，SSI 24clk @3.125MHz，CRC6 每帧校验，Mg[2]=按压 |
| 电机驱动 | **DRV8316CRRGFR**（CR = SPI 变体），3x PWM 模式，SPI 配置 @3.125MHz，三电阻（内建 CSA）电流采样 |
| 控制环 | GPTIMER0 中心对齐 20kHz，更新中断里准同时采电流+读角度 |
| 调试串口 | UART0 @115200（PIN_20=TX / PIN_21=RX，不占 15 个可分配脚） |

## 目录

**逐文件用途与关键词 → [FILE_INDEX.md](FILE_INDEX.md)**（全文件索引：306 个文件全覆盖，含 logic 编译产物与按任务反查表）

```
FOC2205/
├── platformio.ini     构建配置（foc2205 env）
├── foc2205.ve         引脚映射（改它必须 buildlogic + logic + upload）
├── docs/              硬件接线设计、QFN32 引脚规范、审查交付记录
├── logic/             CPLD 逻辑：analog_ip（ADC×3）+ spi_mode_wrap（mode-1 桥×2）
└── src/               固件：board / pwm3ph / drv8316 / mt6701 / current / foc / main
```

**SSI/SPI 速率是实测定的，不要调高**：MT6701 在 12.5MHz 下半周期仅 40ns，扣掉 DO 输出延迟与 CPLD 桥的
2 级同步后无裕量，帧会位错、CRC6 不过；3.125MHz 下干净通过（CRC 误码 0）。DRV8316C 本身是 5MHz 器件。

## 构建（全部实测通过）

```bash
pio="C:/Users/Administrator/.platformio/penv/Scripts/pio.exe"
$pio run -e foc2205                 # 编译固件
$pio run -e foc2205 -t prelogic     # 生成 logic 工程（改 .ve 后必跑）
cd logic
cmd //c build_steps.bat             # Quartus 分步综合（勿用 af_quartus.tcl，见下）
cmd //c run_supra.bat               # Supra P&R -> foc2205.bin
cd ..
$pio run -e foc2205 -t buildlogic   # 位流校验
$pio run -e foc2205 -t logic        # 烧 logic 位流（接板后）
$pio run -e foc2205 -t upload       # 烧固件
cmd //c tools/reset_run.bat         # 必做：烧录收尾是 reset halt，需手动放行
```

**Quartus 13 在本机的两个硬约束**（违反必失败）：
1. `logic/foc2205.qsf` 必须保留 `PARALLEL_SYNTHESIS OFF` —— 否则并行综合子进程 fast-fail，
   map 不提交 db，后续 eda 报 "Run Analysis and Synthesis first"。
2. `quartus_eda` 必须排在 `quartus_fit` 之后（它输出 post-fit 网表 `simulation/modelsim/foc2205.vo`）。
   一键流程 `af_quartus.tcl`（execute_flow）会在 map 后误报 `Error 293007` 中止，勿用。
   各步退出码 `0xC0000409` 是假失败，以 `quartus_logs/*.summary` 的 Successful 为准。

构建验证记录（2026-10-03，v6.1 INL_EN→PIN_28 复测）：固件编译通过（Flash 14.1KB，RAM 3.8KB，含
sincos LUT）；prelogic 0 错 0 警；Quartus 0 errors；Supra 0 errors；`logic/foc2205.bin`
22.4KB（22985 字节，压缩位流，含 PIN_28/22/23 布局，GPIO2_2=PIN_28 网表已核）。

## 项目文档与审查

- [元件引脚连接网表（docs/FOC2205_元件引脚连接网表.md）](docs/FOC2205_元件引脚连接网表.md)（**v1.0**：元件间信号互连 + 简化网标命名，电源部分除外；画原理图以此为准）
- [硬件接线设计（docs/DRV8316+MT6701_FOC驱动板接线设计.md）](docs/DRV8316+MT6701_FOC驱动板接线设计.md)（**v6.1**：INL_EN=PIN_28/JNTRST（2 线 DAPLink 零影响）、BOOT1 纯净 10k 下拉、独立 LDO 电源架构、BRK/DO 移至 PIN_22/23）
- [QFN32 芯片引脚评估与分配规范（docs/FOC2205_QFN32芯片引脚评估与分配规范.md）](docs/FOC2205_QFN32芯片引脚评估与分配规范.md)（V3.1：原生定义经 DAPLink 手册逐脚核对，含 INL_EN=PIN_28 复用记录）
- [审查结果交付文档（docs/FOC2205_审查结果交付文档.md）](docs/FOC2205_审查结果交付文档.md)：两轮审查整改交付记录。
- [电机参数（docs/电机参数.md）](docs/电机参数.md)（2026-10-14：2205/2804 电机参数表文本转录 + 与固件交叉核对——极对数 7 确认 `POLE_PAIRS`、供电 8~16V 交集、峰值电流无裕量；原图 `docs/电机参数.jpg`）。

> 两轮审查报告（P0/P1/P2 共 10 项、D-1~D-6 共 6 项）与逐条裁定整改记录已于 2026-10-03 移出仓库树，结论均已落地到代码与接线设计；原文可在 git 历史追溯（引入于 29bc30d / 2aa56b1）。

## 新板卡适配（2026-10-14 完成并上板验证）

新板资料：`docs/FOC驱动板原理图.pdf`、`docs/SimpleFOCMini-v2_netlist.md`（嘉立创工程名 SimpleFOCMini-v2）。

**引脚层面零改动**：新板 MCU 侧 32 脚中有 31 脚与既有 `foc2205.ve` 一致，唯一差异是 PIN_1 预留了
50MHz 有源晶振（IO_GB 脚），实际未焊接 —— 所以 `.ve` 未改、无需 prelogic。
BOM 里写的 `DRV8316CTRGFR`（CT = 硬件引脚配置变体）是选型错误，**实焊为 DRV8316CRRGFR（CR = SPI）**，
SPI 驱动链路不变。（分辨方法：芯片丝印 `DRV 8316CR` vs `DRV 8316CT`。）

**上电顺序**：板上无独立 LDO，3V3 由 U2 座第 5 脚外部供入；DRV8316 的 VREF/ILIM(37) 直挂 3V3 网络，
所以 **VM 必须先于（或同步）3V3 建立**，否则电流经该脚倒灌进未上电的驱动芯片。

**首次上板暴露并修复的 3 个固件 bug**（老代码从未上板，静态看不出来）：
1. `delay_ns()` 用 `read_csr(cycle)` —— AG32 核不实现 cycle CSR，触发非法指令异常
   （mcause=2 / mtval=0xc00026f3），第一次 SPI 传输后固件即死。改用 SDK 的 `UTIL_IdleCycle()`。
2. `delay_ns()` 的周期数按 `SYS_GetSysClkFreq()` 算 —— 该函数返回 HSE 晶振频率 8MHz 而非 PLL 后的
   200MHz，导致 `delay_ns(150)` 实际只等 1 个周期（≈5ns）。改用与 `.ve` 同步的 `FOC_SYSCLK_HZ`。
3. `mt6701_crc6()` 返回值未屏蔽回 6 位 —— `crc ^= 0x43` 残留 bit6，CRC 永远比不对。

**CPLD 桥改动**（`logic/spi_mode_wrap.v`）：DRV8316 桥流水线深度 12→32，以满
足其 tSU_nSCS=300ns（原 120ns 导致 SDO 回数错位）；MT6701 的 SSI 速率降至 3.125MHz 换取采样裕量。

## 上板记录（2026-10-14，新板卡首次点亮）

位流 23692 B、固件 14368 B，均 write + verify 通过。板级实测：

| 项目 | 实测值 | 判据 |
|---|---|---|
| DRV8316 回读 | CTRL2=0x7c、CTRL5=0x02、CTRL6=0x11、CTRL10=0x15 | 与写入值一致 |
| INL_ALL (PIN_28) | 高 | 驱动自检通过、3x 驱动已使能 |
| MT6701 CRC | 误码 0，angle=13317 稳定 | SSI 链路正常 |
| 电流零点 | 2069 / 2064 / 2063 | ≈2048（1.65V 偏置） |
| FOC ISR | 1 秒 +40566 次 | ≈40.5kHz（中心对齐 20kHz×2） |

校验方式见下节。

### 串口查看（2026-10-15 实测：COM26 @115200，开箱即用）

**结论：固件侧无需任何修改，也不需要额外飞线。** DAPLink 把它的 pin20/21
（`IO_UART0_TX/RX`）直接桥到目标芯片的 UART0，并枚举成自己的 CDC —— 所以
**插上 DAPLink 后 `COM26 @115200 8N1` 就是 FOC2205 的控制台**，和 Logic 板
是同一套用法。之前"串口没输出"是因为烧录收尾停在 `reset halt`、固件根本没跑
（见下节），不是 UART 的问题。

抓完整 boot 日志（**先开串口再复位**，否则会错过 banner）：

```bash
python tools/uart_capture.py COM26 115200 18 > bootlog.txt   # 先起
cmd //c tools/soft_reset.bat                                 # 再软复位
```

实测完整输出：

```
=== FOC2205 bring-up ===
SYSCLK=200000000 BUSCLK=100000000
BootMode=0 (0=FLASH 1=UARTloader 3=SRAM)
nSLEEP released
PWM3ph ready: 20000 Hz, ARR=2499
DRV8316: CTRL2=0x7c (want 0x7c) CTRL6=0x11 (want 0x11) STAT=0x08
INLx released -> 3x PWM drive enabled
MT6701: CRC pass 16/16, angle=7413 field=0 push=0
Izero: A=2069 B=2064 C=2063
Aligning rotor to d-axis...
Zero angle offset: 1050/1000 rad, sensor direction: +1
FOC loop running
isr=20095 ang=7413 ib=-1 crc_err=0 dir=+1
```

要点：

- **`reset_run.bat` 对已在运行的芯片无效**。DAPLink 只接了 TCK/TMS，没有 nRST
  线，openocd 的 `reset run` 只能把 halt 状态放行；芯片已在跑时它什么都不做。
  要真正重启用 `soft_reset.bat`（写 `SYS->RST_CNTL` 的 `SYS_RST_SFT` bit0）。
- **SDK 的 `printf` 不支持 `%+d`**，会原样输出 `dir=%+d`。需要符号时手动处理
  （`main.c` 里已改成 `%s%d` + 三元取符号）。
- 想用独立 USB-TTL 也可以：TTL 的 RXD→U2.3、TXD→U2.2、GND→U2.4（勿接
  U2.5/VCC 与 U2.1/BOOT0），此时不要用 COM26。

### JTAG 读 GPIO 寄存器的坑

GPIO7 的 APB 时钟没人开时，JTAG 直读其寄存器**一律返回 0（假值）**——
`TX_AFSEL=0x00` 曾因此误判为"AF 写入丢失"，并一度推导出"固件串口坏了"的错误
结论。读任何 GPIO bank 前先使能对应 `APB_MASK_GPIOx`；`tools/uart_pad.bat` 已经
自己把 `APB_MASK_GPIO7`(bit11) OR 进 `SYS->APB_CLKENABLE`(0x03000060) 再读，
**固件侧不需要任何配合代码**。

正解：`TX_AFSEL=0x00000040`、`RX_AFSEL=0x00000002`，board_init 一直写对了。

### 关于那个被删掉的 `uart0_tx_pad_fixup()`

排查过程中曾加过一个"开 GPIO7 时钟 + 重断言 AFSEL"的修复，理论是 SDK 的
`GPIO_AF_ENABLE()` 写入被丢弃。**A/B 实测证伪**：注释掉它之后串口日志完全一样，
所以它不是必需的，已删除。固件里只留了注释说明别再无依据地加回来。

（顺带确认 `SYS_EnableAPBClock()` 是纯 `|=`，只置位不清位，不会误关其他时钟；
GPIO6/GPIO7 bank 上虽然还挂着 GPTIMER2/3/4、UART1~4、CAN、MAC 等复用功能，但
本工程一个都没使能，`.ve` 里 GPIO 分配只有 GPIO2_0/1/2，所以开这两个 bank 的
时钟也确实无副作用。）

## 让电机转起来（motion 层 + 串口控制台）

新增 `src/motion.c/h` = main 里那句"手感层"的落地实现。**契约：只写
`g_foc.torque_q`，`foc.c` 一行未改**，所以随时可以摘掉而不动 FOC 闭环。
`main.c` 的 `foc_isr` 顺序为 `foc_step_isr()`（刷新角度 + 输出上一拍指令）→
`motion_step_isr()`（用新角度算下一拍）。

两个易踩的坑（代码里已注释）：

1. **位置必须用累积量**。MT6701 只给 0..16383 的绝对角，"转一圈"若按最短路径
   差算误差，起点=终点、误差恒 0，电机不会动。实现里每拍累加
   `raw_delta(now,prev)`（折到 ±8192）得到跨圈位置；指令用 float 斜坡累加
   （0.25 rev/s 时每拍增量只有 0.08 raw，整型会被截断成 0）。
2. **开环旋转不用改 foc.c**：每拍给 `g_foc.zero_electric_angle` 减一个增量即可
   （foc.c 里 `ang_e = raw_e - zero`）。退出时必须还原，否则闭环零位被污染。

串口控制台（COM26 @115200，见上节抓日志方法）：

| 键 | 作用 |
|---|---|
| `r` / `R` | 位置伺服 +1 / -1 圈（电子齿轮跟随 + PD + 前馈 + 积分） |
| `o` | 开环扫掠：强制电压矢量转一圈（按当前速度档，不依赖编码器） |
| `t` / `T` | 恒定 +q / -q 力矩保持 3 s（诊断"给电压到底出不出力"） |
| `s` | 释放力矩 |
| `p` / `g` | 冻结 PWM 到 75/25/50%（万用表量引脚）/ 恢复 FOC ISR |
| `f` | 读 DRV8316 故障寄存器 |
| `+` / `-` | 力矩限 ×1.25 / ÷1.25（**上限锁死在 `MOTION_POWER_PCT_MAX`**） |
| `k` / `j` / `i` | kp（位置增益）/ kd（阻尼）/ ki（积分）档 |
| `v` / `c` | 速度档（0.02~0.5 rev/s）/ 跟随带宽档（100~1600 raw） |
| `d` / `h` | 打印当前配置 / 帮助 |

开机不转（`MOTION_AUTORUN=0`），停在 `MOTION_IDLE` 力矩为 0，要转发 `r`。
实测 ISR = **40015 Hz**。中止保护：误差 >4096 raw（90°）判失步、CRC 增量 >200，
另有"位置停滞 1 秒"的收尾判定（见下）。中止即 torque=0。

```bash
python tools/uart_console.py t 6     # 发命令 + 抓回显（uart_capture.py 只能收）
python tools/uart_console.py r 12    # 转一圈并看进度
cmd //c tools/pwm_dump.bat           # JTAG 读 GPTIMER0: CR1/SR/BDTR/CCR0-2
```

## 控制回路优化（2026-10-15 晚）：从"抖到不能看"到 990/1000 圈

出力锁 10%（`vq_max=819 Q12 = 0.199 V`）的前提下，逐项修掉了抖动的成因。
判据：**看 `ang` 增量是否均匀，不要看 `vel`**（速度估计天生噪声大）。

### 1. 电子齿轮跟随（`err_follow`，最关键）

旧逻辑无条件按 `s_inc` 推进指令，指令是一条与转子状态无关的直线。出力被锁
10% 时转子跟不上，误差一路涨到数百 raw，P 项立刻打满限幅 → 误差反向时又立刻
打满反向 → **bang-bang 极限环**。改成"指令最多超前转子 `err_follow`（默认
800 raw）"，跟得上就走、跟不上就等。误差**结构上就有界**，永远进不了
bang-bang 区。代价是平均速度可能低于设定值——力矩受限时这是诚实的行为。

### 2. 速度估计重建

单拍位移只有 0/1 raw，×40 kHz 后量化噪声达 ±40000 raw/s。旧的一阶 IIR 压得住
就迟滞、压不住就被 `kd` 放大成真实力矩抖动。改成 **256 拍窗口差分**
（噪声 ∝ isr_hz/窗口）+ 单拍位移限幅（挡编码器假跳变）+ 速度硬限幅。

### 3. 阻尼项单独限幅

即使重建后，磁干扰下速度噪声仍可达 ±25000 raw/s，`kd` 乘上去轻松超过出力
上限。把阻尼项夹在限幅的 25% 以内：小误差时仍线性起阻尼，大噪声时不打飞输出。

### 4. 库仑摩擦前馈 `kfric`

干摩擦大小与速度无关、只随方向变号。没有它，P 项必须自己"憋"出这个电压转子
才动，表现为持续的稳态滞后。

### 5. 积分项：条件抗饱和 + 只在稳态工作

- 每拍增量只有 0.004 Q12，**必须 float 累积**（int 会截断成 0，积分形同不存在）。
- 输出饱和时停止积分（抗 windup）。
- **只在本站误差 |e| < 4×settle 时才累积**。启动那一两百毫秒的负误差曾把积分
  直接灌满（−491），前馈被抵消掉，走到一半电机被自己拉住不动。
- 远离稳态时以 1 s 时间常数泄放回中。

### 6. 收尾：位置停滞 + 指令落到实际位置

- 停滞判定只看"1 秒内位移 < 6 raw"，**不要求力矩饱和**——早期版本要求打满，
  结果卡在"误差 288 raw 略超带宽、力矩只用一半"的死区里，只能拖到 timeout。
- 进入保持态时把指令落到**实际位置**而不是死守终点，否则残留误差会让控制器
  一直全功率去拉（10% 又拉不动），`vq` 长期打满还抖。残差通过
  `motion_final_err_raw()` 如实上报。
- 保持态死区：带宽内只留积分维持，不追编码器噪声。

### 7. 开环的 2 倍 + 方向修复

`ang_e = (raw_e − zero) × sensor_direction`：`dir=−1` 时 zero 的推进与转子自身
变化叠加，稳态 `n = −ω/(2·pp)`，转速恰为指令一半（三档实测恒 0.497，已 ×2
补偿）；**`dir=+1` 时无稳态解**（电压矢量恒比转子快 ω，正反馈失步）。方向判定
修复后 dir 恒为 +1，所以开环期间必须把 `sensor_direction` 临时置 −1（它是
`foc_params_t` 的数据成员，改它不需要动 `foc.c`），退出还原。

### 实测结果（10% 上限）

| 测试 | 结果 |
|---|---|
| 闭环 `r` @0.25 rev/s | 990/1000 圈，4082 ms，`vq` 全程在 ±550 内**未打满**，残差 −243 raw |
| 闭环 `r` @0.05 rev/s | 993/1000 圈，20105 ms（指令 20 s/圈） |
| 闭环 `R` 反转 | 速度 0.052 rev/s vs 指令 0.05，误差 ±270 |
| 开环 `o` @0.05 rev/s | **1038/1000 圈，20578 ms，残差 0 raw**；平均 827 raw/s vs 指令 819（+0.9%） |
| 开环 `o` @0.10 rev/s | 1067/1000 圈，10500 ms（+1.7%） |
| 开环 `o` @0.25 rev/s | 1140/1000 圈，4588 ms（修复前只有 0.497 倍） |
| 保持态 HOLD | `ang` 稳定在 ±1 raw，`vq` 仅 80（修复前打满 819 且抖 ±150 raw） |

开环三档速度实测/指令比 100.9% / 101.7% / 101.3% —— 与速度无关的系统性 2 倍
偏差已消除，残余 +1~2% 属于转子轻微超前电压矢量（正常滑差）。

### 已知物理限制：闭环比开环抖，是反馈结构的固有代价

同一电机、同一速度（0.05 rev/s）的对照实测：

| 模式 | 1 秒窗口速度波动 | 机械抖动（相对 1.2 s 趋势的残差） |
|---|---|---|
| 开环 vq=819 | ±4.9% | std 13 raw，峰峰 46 raw（1.0°） |
| 开环 vq=326 | ±3.4% | std 33 raw，峰峰 134 raw（2.9°） |
| 闭环（换向角滤波 OFF） | ±19.4% | std 61 raw，峰峰 250 raw（5.5°） |
| 闭环（换向角滤波 1/64） | ±14.7% | std 58 raw，峰峰 214 raw（4.7°） |

**成因**：开环的电压矢量由内部累加器以恒定速率推进，与转子无关 —— 转子一旦
落后，负载角自动增大把它拉回来（同步电机的天然刚性）。闭环的电压矢量是从
测得的转子角算出来的，**跟着转子走**：转子在齿槽/摩擦处一慢，磁场也跟着慢，
负载角不会自动增大 → 没有自动恢复力，扰动直接变成速度波动。

**三个"想当然"的解释已被实验排除**：

1. 不是"力矩太小顶不过齿槽" —— 开环把力矩降到 326（与闭环平均值相当），
   速度波动反而更低（±3.4%）。
2. 不是"P 项放大编码器噪声" —— kp 从 2 降到 0.5，抖动反而恶化
   （峰峰 217 → 425 raw）。
3. 不是"编码器噪声直接调制换向角" —— 给换向用的电角度加 1/64 低通
   （噪声衰减约 11 倍），抖动只从 250 降到 214 raw。说明这个抖是**真实的
   机械运动**，不是传感器噪声。

`q` 键循环切换换向角低通（关 / 16 / 64 / 256 / 1024），默认 1/64。它带来的
改善有限但无副作用，保留为可调项。

**要兼顾定位精度与开环般的平顺**，正解是混合换向：电气角由内部斜坡给出
（保证刚性），编码器只做慢速漂移校正。尚未实现。

### 编码器噪声（MT6701）

编码器（直接读数无滤波）在**电机通电时**噪声显著变大（静止时完全稳定）。最可能是绕组磁场干扰磁编码器（布局问题）。表现为位置估计有 ±150 raw
的低频摆动，速度估计天然不可信。上述 2/3/6 项都是围绕它的缓解措施；要根治
得从硬件/布局入手，或给角度加观测器。

### 2026-10-15 早前：电机不动，已定位到功率级（已解决）

位置环 vq 已下发到限幅、CCR 实测三相各不相同（1249/2061/437）→ **MCU 侧 PWM
确实在调制**；DRV8316 无故障（`IC_STAT=0x08` = NPOR=1 VM 正常、`STAT1=0x00`、
无 OCP/VCP_UV）、CTRL2=0x7C（3x 模式）、INL 高、DRVOFF 接地、nFAULT 未触发。
但 **角度恒为 7413、相电流 ≈0**，开环扫掠 4 s 也不动 ⇒ 不是"力矩不够/零偏错"，
而是 **INHx 没到 DRV8316 或电机三相开路**，需用万用表沿着
`PIN_7/8/9 → INHA/B/C → OUTA/B/C → 电机相电阻` 逐级量。

## 上位机 `tools/foc_panel.py`（角度显示 + 三相手动强制）

```bash
cmd //c tools\run_foc_panel.bat     # 或 python tools/foc_panel.py（需 tkinter + pyserial）
```

界面上选好串口（默认 COM26 = DAPLink CDC 控制台，115200）点"连接"即可。

- **角度**：表盘指针 + 度数 + raw + 累积圈数（跨圈在上位机侧估算）。
- **三相手动强制**：A/B/C 三个按钮各自切"高(VM)/低(GND)"，强度可选
  25/50/75/100%（100% = 直通，压差 = VM；50% = 高 75%/低 25%，压差减半）。
  用于排查哪相通、相电流有没有、转子会不会被吸到某个位置。
- 顺带显示三相电流 LSB、CRC 误码、`IC_STAT`、力矩指令、当前模式。

**手动强制 = 直流通电**，电流只受电机电阻限制（不像 FOC 那样被电感/占空比限制），
所以：先用低强度、短时点动；固件侧 **30 秒无操作自动释放**，上位机每 5 秒自动
重发 mask 保活；断开串口前界面会主动发 `g` 释放输出。

协议（固件侧 `main.c` 实现，都是 ASCII 单/双字符）：

| 命令 | 含义 |
|---|---|
| `?` | 查询 → 一行 `#FOC,ang=..,deg=..,crc=..,ia=..,ib=..,ic=..,mode=..,mask=..,pct=..,drv=0x..,vq=..,err=..,vel=..,st=..` |
| `m` / `g` | 进入 / 退出手动强制 |
| `xN` | 三相掩码 N=0..7（bit0=A bit1=B bit2=C，1=高） |
| `wN` | 强度 N=1..4 → 25/50/75/100% |
| `r`/`R`/`s`/`f` | 转 +1/-1 圈 / 释放 / 读故障 |

实现要点：手动模式**不关 PWM 中断**（关了角度就停更），而是在每拍 ISR 末尾用
手动值覆盖 foc 刚写入的 CCR，因此角度与电流采样照常刷新。

## 无串口时的校验手法（tools/）

烧录收尾是 `reset halt`，必须跑 `tools/reset_run.bat` 固件才会真正执行；
要重新抓 boot 日志则用 `tools/soft_reset.bat`（真软复位）。串口可用时优先用
`tools/uart_capture.py`，以下 JTAG 手法用于串口不可用的场合（本次定位全靠它）：

```bash
cd tools
cmd //c reset_run.bat     # 放行 CPU（仅首次烧录后有效，见上节）
cmd //c soft_reset.bat    # 软重启（抓 boot 日志用这个）
cmd //c check_run.bat     # PC / nSLEEP(PIN_5) / INL_ALL(PIN_28) / SPI 回读
cmd //c foc_status.bat    # ISR 计数、CRC 误码、角度、电流零点、IQ
cmd //c trap_dump.bat     # 崩异常时抓 mcause / mepc / mtval
cmd //c uart_pad.bat      # UART0 TX/RX 的 AFSEL 与 pad 电平
cmd //c clk_dump.bat      # CLK_CNTL / PBUS_DIVIDER / APB 时钟门控
```

判据：**PC 不在 `exception_handler`**；`INL_ALL` 为高表示驱动自检通过；
`foc_status.bat` 的 ISR 计数两次读取应递增（约 40k/秒）。
脚本里的全局变量地址来自 `riscv64-unknown-elf-nm -n <elf>`，**固件重编后地址会漂移，需重新核对**。
