# AG32 工作区总索引（INDEX）

> 本文件是 `C:\Users\Administrator\Documents\AG32` 的**总入口索引**：先看这里，再进各工程目录。
> 维护约定：顶层目录或工程发生新增/移动/删除时，同步更新本文件；工程内部细节写在各自的 `README.md` / `FILE_INDEX.md`。
> 统计基准：2026-10-17 整理后共 2718 个文件（不含 `.git`）。

## 0. 快速导航（按任务找入口）

| 我要…… | 去哪 |
|---|---|
| 动手前了解环境、烧录流程、排障 | [docs/HANDOVER.md](docs/HANDOVER.md) |
| 查硬性规则、引脚约定、工作区约定 | [AGENTS.md](AGENTS.md) |
| 做逻辑分析仪（SUMP / 波形发生器） | [Logic/README.md](Logic/README.md)、[Logic/PERFORMANCE_REPORT.md](Logic/PERFORMANCE_REPORT.md) |
| 做 FOC 力反馈旋钮（2205 驱动板） | [FOC2205/README.md](FOC2205/README.md)、[FOC2205/FILE_INDEX.md](FOC2205/FILE_INDEX.md) |
| 查 FOC 驱动板器件手册 / 原理图 / 网表 | [FOC2205/docs/hardware/README.md](FOC2205/docs/hardware/README.md) |
| 跑标准验证工程（流水灯 / CAN-UART） | [projects/](projects) |
| 查早期旋钮原型与上位机（foc_knob） | [foc/FILE_INDEX.md](foc/FILE_INDEX.md) |
| 找 SmartKnob 上游参考源码 / 素材 | `ref-smartknob/` |
| 用 OpenOCD / Supra 探针脚本 | [tools/README.md](tools/README.md) |
| 找官方例程原件（只读） | `example/`、`example_logic_led/` |
| 找工作区级官方 PDF（IDE 环境、产品概览、DAPLink 手册） | [docs/README.md](docs/README.md) |

## 1. 工程总览

| 工程 | 路径 | 目标硬件 | 状态（2026-10-17） | 入口文档 |
|---|---|---|---|---|
| 逻辑分析仪 | `Logic/` | AG32VF303 100 脚板 + DAC/信号发生器 | 采样/上位机/回环实测通过；PIN_5 物理回环与 LED 启动序列待肉眼确认 | `Logic/README.md`、`Logic/HANDOVER.md` |
| FOC 力反馈旋钮（2205） | `FOC2205/` | AG32VF303KCU6(QFN32)+MT6701QT-STD+DRV8316C | 重构 + 通电贯通；闭环平滑扫描完成；烧录链路仍受 SWD/AHB 挂死阻塞 | `FOC2205/README.md`、`FOC2205/FILE_INDEX.md` |
| 旋钮早期原型 | `foc/foc_knob/` | 早期 FOC 驱动板 + 霍尔 | 原型阶段，带 host 上位机与回归脚本 | `foc/FILE_INDEX.md`、`foc/foc_knob/README.md` |
| 流水灯验证 | `projects/ag32vf303_flowled/` | AG32VF303 100 脚 Demo 板 | MCU 版 + 纯 CPLD 版均已烧录验收 | `projects/ag32vf303_flowled/` |
| CAN/UART 复用测试 | `projects/can_uart_test/` | AG32VF303 100 脚 Demo 板 | 引脚复用与回环测试 | `projects/can_uart_test/` |
| 官方参考例程（只读） | `example/`、`example_logic_led/` | AGM 原厂 | **勿修改勿删除**，LED 引脚与接口约定出处 | — |
| SmartKnob 上游参考（只读） | `ref-smartknob/` | scottbez1/smartknob | 参考副本，git 忽略；素材见 `ref-smartknob/upstream-assets/` | `ref-smartknob/README.md` |

## 2. 目录树（顶层）

```text
AG32/
├─ INDEX.md                        本文件：总索引（先看这里）
├─ README.md                       工作区总览与快速命令
├─ AGENTS.md                       工作区约定与硬性规则（Agent 必读）
├─ docs/                           工作区级文档：交接文档 + 官方 PDF
│   ├─ HANDOVER.md                 环境总览、烧录流程、排障表、纯 CPLD 三段式编译
│   ├─ AG32_IDE开发环境搭建.pdf
│   ├─ AG32_MCU产品概览.pdf
│   └─ AGM_DAP_LINK_Rev2.51.pdf    DAPLink 手册（p.12-13 = QFN32 完整引脚表）
├─ Logic/                          逻辑分析仪（CPLD 采样 + USB CDC + 信号发生器）
│   ├─ README.md / HANDOVER.md / PERFORMANCE_REPORT.md
│   ├─ src/ logic/ tools/          固件 / CPLD 逻辑 / 上位机与测试
│   └─ captures/                   VCD 抓图与连接验证截图
├─ FOC2205/                        FOC 驱动板（QFN32 自研板 + 固件 + 构建链）
│   ├─ README.md / FILE_INDEX.md / CONTEXT.md
│   ├─ src/ logic/ tools/ experiments/
│   └─ docs/                       设计、验收、审查与调试记录
│       ├─ hardware/               板级硬件资料：原理图、网表、器件规格书、EasyEDA 导出
│       └─ adr/                    架构决定
├─ projects/
│   ├─ ag32vf303_flowled/          标准验证工程（MCU 流水灯 + 纯 CPLD 流水灯）
│   └─ can_uart_test/              CAN/UART 复用测试
├─ foc/                            FOC 力反馈旋钮早期原型（与 FOC2205 零交叉）
│   ├─ FILE_INDEX.md
│   └─ foc_knob/                   固件 + host 上位机 + probe/reset 脚本
├─ tools/                          工作区级调试探针（不绑定单一工程）
│   ├─ openocd/                    OpenOCD 直读探针（PC / Flash / GPIO / UART 状态）
│   └─ supra/                      Supra 器件识别探针
├─ example/                        官方参考例程（agrv2k_407 板）— 只读
├─ example_logic_led/              官方 CPLD LED 例程 — 只读
└─ ref-smartknob/                  SmartKnob 上游参考副本 — 只读、git 忽略
    └─ upstream-assets/            上游原理图（KiCad）/ 文件树 / 源码包

（隐藏目录 `.zcode/`、`.workbuddy/` 为工具会话状态，见第 5 节。）
```

## 3. 本次整理（2026-10-17）文件去向

原先散落在工作区根目录的 22 个文件已按归属归档；下表为**旧路径 → 新路径**映射，便于回查历史记录。

### 3.1 归入 `FOC2205/docs/hardware/`（FOC 驱动板板级资料）

| 旧路径 | 新路径 | 说明 |
|---|---|---|
| `docs/FOC驱动板原理图.pdf` | `FOC2205/docs/hardware/FOC驱动板原理图.pdf` | 自研板原理图（嘉立创工程名 SimpleFOCMini-v2） |
| `docs/SimpleFOCMini-v2_netlist.md` | `FOC2205/docs/hardware/SimpleFOCMini-v2_netlist.md` | EasyEDA 原生网表转换版 |
| `FOC2205/docs/C2913974_位置传感器_MT6701QT-STD_规格书_WJ1878447.PDF` | `FOC2205/docs/hardware/datasheets/C2913974_MT6701QT-STD_规格书_WJ1878447.PDF` | MT6701QT-STD 规格书（原地细化归档） |
| `FOC2205/docs/C5447274_无刷直流(BLDC)电机驱动芯片_DRV8316CRRGFR_规格书_WJ487025.PDF` | `FOC2205/docs/hardware/datasheets/C5447274_DRV8316CRRGFR_规格书_WJ487025.PDF` | DRV8316CRRGFR 规格书（原地细化归档） |
| `FOC2205/docs/drv8316_text.txt` | `FOC2205/docs/hardware/datasheets/DRV8316C_datasheet_text.txt` | DRV8316C 手册逐页文本提取（同名重命名以便区分正/负版本） |
| `drv8316.pdf` | `FOC2205/docs/hardware/datasheets/DRV8316_TI-SLVSF16B_datasheet.pdf` | TI SLVSF16B（**非 C 后缀**版）手册，与板载 C 版并列留档 |
| `drv8316_text.txt` | `FOC2205/docs/hardware/datasheets/DRV8316_TI-SLVSF16B_text.txt` | 上件文本提取（未入库，本次一并归档） |
| `osc_datasheet.pdf` | `FOC2205/docs/hardware/datasheets/OT2EL4C4JI-111OLP-50M_datasheet.pdf` | YXC YSO110TR 50 MHz 有源晶振（OSC1，LCSC C5203552） |
| `osc_page_1..4.png` | `.../OT2EL4C4JI-111OLP-50M_page1..4.png` | 晶振手册页面截图 |
| `lcsc_5892914.html` | `.../OT2EL4C4JI-111OLP-50M_lcsc-C5203552.html` | 立创商城商品页存档 |
| `usblc6-2p6_datasheet.pdf` | `.../USBLC6-2P6_datasheet.pdf` | USBLC6-2P6 ESD 保护手册 |
| `esd_text.txt` | `.../USBLC6-2P6_text.txt` | 上件文本提取（原名 `esd_*` 易与器件对不上，已改名） |
| `led_datasheet.pdf` | `.../GL0603UG01_LED_datasheet.pdf` | 桂光光电 GL0603UG01 LED 手册 |
| `led_page_4.png` | `.../GL0603UG01_LED_page4.png` | LED 手册典型曲线页截图 |
| `lcsc_led.html` | `.../GL0603UG01_LED_lcsc-54645989.html` | 立创商城商品页存档 |
| `.tmp_sch_review/`（7 个 json） | `FOC2205/docs/hardware/easyeda-review/` | EasyEDA 原理图审查原始导出（仍不入库，见 `.gitignore`） |
| `esd_datasheet.pdf` | **已删除** | 与 `USBLC6-2P6_datasheet.pdf` 字节完全一致（SHA-256 `c22912a5…`），保留一份 |

### 3.2 归入 `Logic/captures/`

| 旧路径 | 新路径 | 说明 |
|---|---|---|
| `capture.vcd` | `Logic/captures/planb-capture-2026-10-10.vcd` | 方案 B CPLD 采样导出（CH0~CH3 = PIN_7~10） |
| `pulseview_check.png` | `Logic/captures/pulseview_check.png` | PulseView 连接验证截图 |

### 3.3 归入 `tools/`（工作区级探针）

| 旧路径 | 新路径 | 用途 |
|---|---|---|
| `test_pc.cfg` | `tools/openocd/probe-pc.cfg` | halt 后打印当前 PC（判卡 ROM） |
| `test_read.cfg` | `tools/openocd/probe-flash-id.cfg` | 读 0x80000000 flash 头 |
| `test_gpio.cfg` | `tools/openocd/probe-gpio4-regs.cfg` | 读 GPIO4 寄存器组（Demo 板 LED） |
| `test_state.cfg` | `tools/openocd/probe-sys-state.cfg` | 读 GPIO0/GPIO4/UART0 状态 |
| `test_supra.tcl` | `tools/supra/probe-arch-AGRV2KL100.tcl` | Supra 加载 AGRV2KL100 架构自检 |

### 3.4 归入 `ref-smartknob/upstream-assets/`

| 旧路径 | 新路径 | 说明 |
|---|---|---|
| `ref-smartknob-view_base.kicad_sch` | `ref-smartknob/upstream-assets/smartknob-view_base.kicad_sch` | 上游 SmartKnob View 底板原理图 |
| `sk-tree.json` | `ref-smartknob/upstream-assets/sk-tree.json` | 上游文件树快照 |
| `smartknob-master.tar.gz` | `ref-smartknob/upstream-assets/smartknob-master.tar.gz` | 上游源码包 |

> ⚠️ `ref-smartknob/` 整体被 `.gitignore` 忽略（第三方只读副本）。因此 `ref-smartknob-view_base.kicad_sch` 迁移后**文件仍在磁盘上、内容不变**，但不再是 git 跟踪文件。

## 4. 归档与命名约定

- **按工程归档**：任何文件进到它所属工程的一级目录下；跨工程共用的东西才放 `docs/`、`tools/`、`example*/`。
- **工程名即目录名**：路径保持纯英文（SDK 不支持中文路径，Quartus 13 同样）。
- **器件资料命名**：`<器件型号>_<类别>_<来源>`，例如 `USBLC6-2P6_datasheet.pdf`、`DRV8316_TI-SLVSF16B_datasheet.pdf`、`GL0603UG01_LED_lcsc-54645989.html`。
- **同名歧义必区分**：`DRV8316`（TI SLVSF16B）与板载 `DRV8316C` 必须靠文件名区分，勿互相覆盖。
- **抓图/导出**：波形与截图放工程内 `captures/`，测试日志放 `tools/` 且带日期后缀。
- **生成物不入库**：`.pio/`、`logic/{db,incremental_db,quartus_logs,simulation,alta_db,alta_logs}/`、`__pycache__/` 由 `.gitignore` 统一忽略。

## 5. 未纳入"工程文件"的目录

| 目录 | 性质 | 处理方式 |
|---|---|---|
| `.git/` | 版本库 | 唯一远端 `origin = https://github.com/ling99LL/ag32vf303-dev.git`（分支 `main`） |
| `.zcode/` | ZCode 工具的 skill 与会话计划 | `.zcode/skills/ag32-dev/` 为 AG32 开发 skill；`.zcode/plans/` 忽略入库 |
| `.workbuddy/` | 工作日志与长期记忆（按日） | 会话状态，忽略入库；内容对排障有参考价值 |
| `example/`、`example_logic_led/` | 原厂例程原件 | **只读，勿改勿删** |
| `ref-smartknob/` | 第三方参考副本 | 只读；整体忽略入库 |

## 6. 维护检查清单

1. 新文件先想"属于哪个工程"，再决定落点；根目录只留 `INDEX.md` / `README.md` / `AGENTS.md` / 工程目录 / `docs/` / `tools/`。
2. 改了顶层结构 → 更新本文件第 2 节目录树与第 1 节总览表。
3. 工程内部增删文件 → 更新该工程的 `README.md`（或 `FILE_INDEX.md`）。
4. 提交前跑一次 `git status`：确认没有生成物被误入库、没有该忽略的文件暴露出来。
