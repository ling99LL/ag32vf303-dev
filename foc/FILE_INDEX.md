# foc/ 文件索引（FOC 力反馈旋钮工程）

> 本文件是 `foc/` 目录的**全文件用途索引**：任何文件都能在此查到用途与关键词。
> 维护约定：新增/删除文件时同步更新本索引；生成物目录只需改目录级说明。
> 统计基准：2026-10-14，`foc/` 共 509 个文件（含本索引与 git 忽略的缓存/实验数据）。

**图例**：`[源]` 手写源码/配置（改动需评审） · `[文档]` 文档 · `[数据]` 实验/采集数据 · `[生成]` 工具自动生成（勿手改，可重建） · `[缓存]` 可再生成缓存（git 忽略）

---

## 1. 顶层导航

| 路径 | 类别 | 用途 | 关键词 |
|---|---|---|---|
| `foc/FILE_INDEX.md` | 文档 | 本索引 | 索引、文件清单、用途 |
| `foc/FocTuner.lnk` | [生成] | Windows 快捷方式 → `foc_knob/host/dist/FocTuner.exe`，双击启动上位机 GUI | 快捷方式、启动、Tuner（git 忽略 `*.lnk`） |
| `foc/foc_knob/` | — | 工程本体，见下文 | 旋钮、力反馈、knob |

---

## 2. foc/foc_knob/ 根文件

| 路径 | 类别 | 用途 | 关键词 |
|---|---|---|---|
| `README.md` | [文档] | 工程主文档：引脚分配、硬件注意事项、编译烧录、串口命令、上位机、调参指南、代码结构、已知限制 | 主文档、说明、命令表、调参 |
| `../FILE_INDEX.md` | 文档 | 本索引文件（位于 `foc/` 顶层，覆盖整个 foc 目录） | 索引 |
| `platformio.ini` | [源] | 构建配置：env `foc`，`agrv2k_303` + `logic_device = AGRV2KQ32`（QFN32 必须）、`cmsis-dap-openocd` 烧录、UART0 monitor COM26@115200 | 构建、环境、烧录协议、串口号 |
| `foc_knob.ve` | [源] | CPLD 引脚映射（pad ↔ MCU 功能）。**改动后必须** `buildlogic` + `-t logic` + `-t upload` 重烧 logic | 引脚映射、ve、改脚、logic |
| `hall_seq.json` | [数据] | `host/hall_capture.py` 采集的霍尔原始时序帧（t/hall/ang/vel），供 `analyze_seq.py` / `sim_hall.py` 离线分析 | 霍尔时序、采集、格雷码 |
| `probe.bat` | [源] | OpenOCD 一行脚本：halt → 打印 PC → resume。判卡死位置（PC≈0x0001xxxx = 卡 ROM） | 调试、读 PC、卡死、OpenOCD |
| `reset.bat` | [源] | OpenOCD 一行脚本：`reset run`，目标板软复位 | 复位、reset |

---

## 3. foc/foc_knob/src/（固件源码，11 个文件）

| 路径 | 类别 | 用途 | 关键词 |
|---|---|---|---|
| `foc_knob.h` | [源] | 全局共享配置：驱动板 GPIO 位定义（EN/RESET/SLEEP/FAULT、霍尔 3 线）、电机参数、`KnobParams` 与 m0..m5 模式枚举、旋钮手感参数 | 参数结构、模式枚举、引脚位 |
| `main.c` | [源] | 入口：板级初始化、校准流程（cal/scan）、串口命令分发（`h` 帮助）、状态打印；头部含 build/烧录/串口速查 | 主循环、命令、校准、入口 |
| `pwm3ph.c` / `pwm3ph.h` | [源] | GPTIMER0 CH0/1/2 三相中央对齐 PWM（20kHz）：CCR 预装载、MOE/OSSI 安全关断（禁用输出=安全刹车） | PWM、三相、定时器、CCR |
| `hall.c` / `hall.h` | [源] | 霍尔扇区译码（60° 电角度）+ 边沿时间戳 + 扇区间插值 + 速度估计 + 旧法校准；抗电流毛刺的边沿速率滤波 | 霍尔、角度、插值、速度、校准 |
| `foc.c` / `foc.h` | [源] | FOC 核心：sincos LUT → 逆 Park → SVPWM → 三相占空比；`foc_loop_irq()` 挂 GPTIMER0 更新中断 = 主循环；电压模式力矩（Uq） | FOC、SVPWM、逆Park、中断、Uq |
| `knob.c` | [源] | 力反馈效果 m0..m5：自由/阻尼/惯性/有界/弹簧（PD 形态）；m3 = SmartKnob 挡位引擎移植（`detent_track()` 状态机+死区+飞车保护） | 力反馈、效果、挡位、SmartKnob、detent |
| `driver.c` / `driver.h` | [源] | 驱动板控制线：EN 使能门控、nSLEEP 休眠、nRESET 20µs 软复位脉冲、nFAULT 读取（拉低 → 封 PWM 锁存） | 驱动板、使能、休眠、故障、FAULT |

（`knob.c` 对应头文件接口收在 `foc_knob.h`，无独立 knob.h。）

---

## 4. foc/foc_knob/host/（上位机与测试脚本，18 个文件）

### 4.1 GUI 与打包

| 路径 | 类别 | 用途 | 关键词 |
|---|---|---|---|
| `foc_tuner.py` | [源] | 上位机主程序：$T 遥测解析、实时仪表盘、三路曲线（角度/速度/Uq，5/10/30s 窗口）、m0..m5 切换、参数滑块、动作按钮、原始终端 | 上位机、GUI、曲线、调参、Tuner |
| `FocTuner.spec` | [生成] | PyInstaller 打包配置（以 foc_tuner.py 为输入）；重打包 `pyinstaller FocTuner.spec` | 打包、spec、PyInstaller（git 忽略） |
| `dist/FocTuner.exe` | [生成] | 打包好的单文件 GUI（~10MB，双击即用）；`FocTuner.lnk` 指向它 | exe、成品、可执行（git 忽略） |
| `build/FocTuner/**`（14 文件） | [缓存] | PyInstaller 中间产物（toc/pkg/pyz/pyc/warn/xref），重打包时重建 | 打包缓存（git 忽略） |
| `__pycache__/`（1 文件） | [缓存] | Python 字节码缓存 | 缓存（git 忽略） |

### 4.2 校准 / 回归验证（跑一遍即给结论，多为只打印）

| 路径 | 类别 | 用途 | 关键词 |
|---|---|---|---|
| `scan_cal.py` | [源] | 一键 `scan` 开环校准 + 闭环 `rot 360` 自检；校准入口 | scan、校准、自检 |
| `verify_live.py` | [源] | 回归：旋转全程 $T 遥测/霍尔必须实时刷新（开环+闭环，防"旋转时串口卡死"回归） | 回归、遥测、实时 |
| `verify_landing.py` | [源] | 回归：闭环 `rot` 正反一圈落点误差 ≤ ±6°（霍尔译码量化台阶 10° 机械） | 回归、落点、精度 |
| `verify_detent.py` | [源] | 回归：m3 挡位引擎（rot ±90° 计数 3/0、静止 |uq| 微小无嗡鸣） | 回归、挡位、detent、m3 |

### 4.3 机理诊断（复现特定抖动/故障）

| 路径 | 类别 | 用途 | 关键词 |
|---|---|---|---|
| `shake_probe.py` | [源] | m3 静止力矩 vs 译码网格相位普查：+10° 落 6 点（整 10° 周期）看静止 |uq|，判"一直抖"机理；只打印 | 抖动、静止力矩、m3、诊断 |
| `wall_hold_probe.py` | [源] | m4 有界模式压在边界上驻留普查：越界 1..9° 落点 + 3s 200Hz 遥测，查边界 P 自激；只打印 | 边界、墙、驻留、m4 |
| `diag_en.py` | [源] | JTAG 中途强拉 EN 高：区分"固件丢 EN 写 / 外部拉低 / 驱动板死"三类 EN 失效；只打印 | EN、JTAG、诊断、驱动板 |
| `diag_power.py` | [源] | JTAG 开环拖动中 halt 两次：dump GPTIMER CNT/CCR0-2（三相是否轮转）+ GPIO0 输入（霍尔是否冻结） | 功率级、CCR、JTAG、诊断 |
| `diag_rt.py` | [源] | JTAG 在 `scan` 拖动中连读 4 次 GPIO0 输入 + CCR0，验证霍尔输入实时变化 | 实时、霍尔、JTAG、诊断 |
| `sim_hall.py` | [源] | 用 `hall_seq.json` 离线逐帧回放**修复前**的 hall.c 逻辑（旧扇区表/旧限幅），回归复现译码问题 | 离线仿真、hall、回归、旧逻辑 |
| `analyze_seq.py` | [源] | 分析 `hall_seq.json`：帧数/跨度、校验 3 霍尔格雷码循环序（每步恰 1 bit 翻转） | 分析、格雷码、时序、hall |

### 4.4 采集与普查（输出数据文件）

| 路径 | 类别 | 用途 | 关键词 |
|---|---|---|---|
| `hall_capture.py` | [源] | 采集霍尔边沿时间线 → 写 `foc_knob/hall_seq.json`（200Hz $T + st 帧） | 采集、hall、json、录制 |
| `record_turn.py` | [源] | 录制真人转动旋钮的高速遥测（先切 m3 默认挡位参数）→ 写 `turn_capture.csv`；`[秒] [COM]` 参数 | 录制、转动、遥测、csv |
| `turn_capture.csv` | [数据] | 上述录制结果（26001 行 $T 遥测），手感离线分析输入 | 录制数据、遥测（git 忽略 `host/*.csv`） |
| `all_mode_probe.py` | [源] | **全模式普查**：host 驱动 `rot` 制造扰动，逐模式（m0..m5）200Hz 记录 2s+ 遥测，评分峰峰值/满幅占比/burst 次数/尾段是否收敛 → 写 `mode_probe/<tag>/`；用法 `python all_mode_probe.py [COM] [tag]` | 普查、全模式、评分、扰动、tag |
| `drag_release_probe.py` | [源] | **带残余速度释放普查**：m5 归位拖动加速到 1.2rad/s 后**飞行中**切目标模式，模拟"转着松手"（普查落点测试覆盖不到的场景）→ 写 `mode_probe/<tag>/` | 松手、飞行、残余速度、释放、tag |

### 4.5 host/mode_probe/（实验数据，387 个 CSV，git 忽略）

全部由上表两个 probe 脚本按 `[tag]` 参数落盘，**文件名按固定规则解码，规则即索引**：

**目录 = tag 批次**（一轮参数迭代一个目录）：

| 目录 | 轮次含义 | 文件数 | 生成脚本 |
|---|---|---|---|
| `base/` | 基线批次（脚本默认 tag） | 20 | `all_mode_probe.py` |
| `v2/` … `v9/`, `v10/`, `v10b/`, `v11/` … `v16/` | 手感参数第 2~16 轮迭代（v10b = v10 重跑） | 各 20 | `all_mode_probe.py` |
| `rel/` | 释放普查第 1 轮（当时 m2 未测，缺 1 文件） | 7 | `drag_release_probe.py` |
| `rel2/` … `rel6/` | 释放普查第 2~6 轮 | 各 8 | `drag_release_probe.py` |

**文件名 = `m{模式}_{场景}_{条件}.csv`**：

| 段 | 取值 | 含义 |
|---|---|---|
| `m0`..`m5` | free 自由 / damp 阻尼 / inertia 惯性 / detent 挡位 / bounded 有界 / spring 弹簧 | 模式（与串口 `m0..m5` 一致） |
| 场景（all_mode） | `land`（落点） / `park`（驻留） / `wall`（压边界） / `spring`（弹簧回中） / `land_+40_flight`（挡位飞越） | 测试场景 |
| 场景（rel*） | `coast_release` / `damp_catch` / `inertia_catch` / `catch_phase_A|B|C` / `inbound_release` / `control` | 释放场景（惯性滑行松手/阻尼接住/惯性接住/挡位三相位接住/越界回归/对照组） |
| 条件 | `+10` … `+90` | 扰动角度（度），如 `m5_spring_+60` = 弹簧模式松手偏离 60° |

CSV 内容：200Hz `$T` 遥测行 + 尾部评分（peak-to-peak / rail duty / burst / tail settle）。

---

## 5. 生成物与缓存（整目录可重建）

| 路径 | 类别 | 用途 / 重建方式 | 关键词 |
|---|---|---|---|
| `foc_knob/.pio/`（69 文件） | [缓存] | PlatformIO 构建产物（固件 elf/bin、SDK 对象文件、`.pio/logic/logic_db` = prelogic 生成的 logic 工程缓存）；`pio run -e foc` 重建 | 构建缓存、elf、编译（git 忽略 `.pio/`） |

---

## 6. 按任务反查（task → file）

| 我想… | 看这里 |
|---|---|
| 改引脚/换脚位 | `foc_knob.ve`（+ 重烧 logic 三步，见 README 编译与烧录） |
| 改手感/加效果 | `src/knob.c`（效果主体）、`src/foc_knob.h`（参数定义）、`README.md` 调参指南 |
| 改 FOC 电气环 | `src/foc.c`、`src/pwm3ph.c` |
| 改串口命令 | `src/main.c`（命令表在 README 串口命令节） |
| 改校准/霍尔角度 | `src/hall.c` |
| 改驱动板保护逻辑 | `src/driver.c` |
| 调 GUI/上位机 | `host/foc_tuner.py`；成品重打包见 `FocTuner.spec` |
| 复现/分析抖动 | `host/shake_probe.py`（静止）、`host/wall_hold_probe.py`（边界）、数据在 `mode_probe/` |
| 分析历史手感数据 | `mode_probe/<tag>/*.csv`（命名解码见 §4.5）、`turn_capture.csv` |
| 查霍尔译码问题 | `hall_seq.json` + `analyze_seq.py` / `sim_hall.py`、`src/hall.c` |
| 烧录/调试卡死 | `probe.bat`（读 PC）、`reset.bat`、`README.md` 上电流程 |
