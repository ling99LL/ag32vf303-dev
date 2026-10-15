# FOC2205 文件索引（AG32VF303 + MT6701 + DRV8316C 驱动板）

> 本文件是 `FOC2205/` 目录的**全文件用途索引**：任何文件都能在此查到用途与关键词。
> 本工程与 `foc/foc_knob` **零交叉**（不引用其任何文件），两份索引互不覆盖。
> 维护约定：新增/删除文件时同步更新本索引；编译产物目录只需改目录级说明。
> 统计基准：2026-10-14，`FOC2205/` 共 306 个文件（含本索引与 git 忽略的编译数据库）。

**图例**：`[源]` 手写源码/配置（改动需评审） · `[文档]` 文档 · `[生成]` 工具自动生成（勿手改，可重建） · `[缓存]` 可再生成缓存（git 忽略）

---

## 1. 顶层导航

| 路径 | 类别 | 用途 | 关键词 |
|---|---|---|---|
| `FILE_INDEX.md` | 文档 | 本索引 | 索引、文件清单、用途 |
| `README.md` | [文档] | 工程主文档：芯片/磁编/驱动参数总表、目录结构、构建命令（实测通过）、文档与审查链接、上板记录（待填） | 主文档、构建、上板 |
| `CONTEXT.md` | [文档] | 力反馈旋钮、运动动作、保持态、力矩释放与动作残差的领域术语表 | SmartKnob、术语、保持态、残差 |
| `docs/adr/0001-module-delivery-boundary.md` | [文档] | 首版交付边界：可嵌入力反馈旋钮模块，不包含独立终端外壳与应用 | ADR、模块、交付边界 |
| `docs/adr/0002-module-control-and-host-interface.md` | [文档] | 模块本地控制与保护，UART TTL 115200 连接宿主和电脑上位机；故障释放后显式恢复至无输出待命 | ADR、UART、宿主、故障恢复 |
| `docs/basic-motion-acceptance.md` | [文档] | 基础运动验收：首轮开环 3/6/15 rpm、正反各实际转满 5 圈、各先通过 1 次；通过判据已确认，六项待实测；停止释放、恢复后待命 | 验收、开环、闭环、释放、待命 |
| `platformio.ini` | [源] | 构建配置：env `foc2205`（release），`logic_dir = logic` + `ip_name = analog_ip`（用户逻辑目录）、`AGRV2KQ32`、烧录 `cmsis-dap-openocd`、monitor COM26@115200 | 构建、环境、logic_dir、烧录 |
| `foc2205.ve` | [源] | CPLD 引脚映射（v6.1：PIN_14=MT_CS、PIN_5=nSLEEP、PIN_7/8/9=INH、PIN_28=INL_ALL、PIN_10/11/12=电流采样、PIN_22/23=BRK/DO…）。**改动后必须** prelogic + Quartus + Supra + buildlogic + 重烧 | 引脚映射、ve、改脚、logic |

---

## 2. docs/（设计文档与规格书，9 个文件）

| 路径 | 类别 | 用途 | 关键词 |
|---|---|---|---|
| `DRV8316+MT6701_FOC驱动板接线设计.md` | [文档] | **硬件接线总纲 v6.1**：电源树/去耦/地平面、INL_EN=PIN_28（2 线 DAPLink 零影响）、BOOT1 10k 下拉、BRK/DO 移 PIN_22/23、bring-up 流程（§6-7 被 main.c 引用） | 接线、电源树、硬件设计、bring-up |
| `FOC2205_QFN32芯片引脚评估与分配规范.md` | [文档] | QFN32 全 32 脚逐一评估 V3.1：原生定义对照 DAPLink 手册核对，零占用 JTAG 5 线/晶振/BOOT1 的分配合法性 | 引脚规范、引脚评估、QFN32、JTAG |
| `FOC2205_元件引脚连接网表.md` | [文档] | **画原理图以此为准 v1.0**：元件↔元件信号互连 + 必需阻容（电源树除外，见接线设计 §5）；依据 foc2205.ve v6.1 + 两份规格书逐脚核对 | 网表、互联、原理图、阻容 |
| `FOC2205_审查结果交付文档.md` | [文档] | 两轮审查（P0/P1/P2 共 10 项 + D-1~D-6 共 6 项）整改交付记录；原文已移出仓库，结论已落代码，git 历史可溯 | 审查、整改、验收、交付 |
| `C2913974_位置传感器_MT6701QT-STD_规格书_WJ1878447.PDF` | [文档] | MT6701QT-STD 官方规格书（SSI 帧格式/CRC6/Mg 状态位出处 p.3-4） | 规格书、datasheet、MT6701、磁编 |
| `C5447274_无刷直流(BLDC)电机驱动芯片_DRV8316CRRGFR_规格书_WJ487025.PDF` | [文档] | DRV8316C 官方规格书（SPI 帧/引脚表 6-1 出处 p.4-5） | 规格书、datasheet、DRV8316、驱动 |
| `mt6701.txt` | [文档] | MT6701 中文资料文本提取（接口/分辨率/封装速查，编码为 GBK 乱码但可读；**未被 git 跟踪** `??`） | MT6701、中文资料、速查（untracked） |
| `电机参数.jpg` | [文档] | **2205 电机（型号 2804）产品参数原表**（12N14P 极对数 7、8V/2.5A/20W、6000RPM、0.03N·m、7.4~16V）；图片不可检索，查参数用同名 `.md` | 电机参数、2205、2804、极对数、规格（untracked） |
| `电机参数.md` | [文档] | 上图的**文本转录 + 工程交叉引用**：表内自洽验算（0.22A=空载、力矩单位 g·cm）、与固件 `POLE_PAIRS 7` 确认、供电 8~16V 交集、电机峰值电流与 DRV8316 8A 无裕量、电频率 700Hz@额定 | 电机参数、转录、极对数、供电、电流裕量、电频率（untracked） |

---

## 3. src/（固件源码，14 个文件）

| 路径 | 类别 | 用途 | 关键词 |
|---|---|---|---|
| `main.c` | [源] | 入口：bring-up 流程（接线设计 §6-7 逐步上电/配置/闭环） | 主程序、bring-up、入口 |
| `app_io.c` / `app_io.h` | [源] | 引脚级 bring-up 工具（`delay_ns/us` 按 sysclk cycle 精确延时、GPIO2_0=MT_CS、GPIO2_1=nSLEEP 等位操作与引脚表注释）；命名避开 SDK `board.h` | 引脚、延时、GPIO、bring-up |
| `pwm3ph.c` / `pwm3ph.h` | [源] | GPTIMER0 中心对齐三相 PWM（3x 模式：只驱 INH×3，INL 板上短接由 GPIO2_2 驱）；更新中断回调挂 FOC；**BRK 硬件刹车**（nFAULT 低 → 零软件延迟封输出） | PWM、三相、BRK、刹车、定时器 |
| `drv8316.c` / `drv8316.h` | [源] | DRV8316C SPI 驱动：16-clock 帧 @6.25MHz、B8 偶校验生成/校验、寄存器读写；SDO 经 mode-1 桥在帧尾锁存到 `SPIW_RXDATA0` | DRV8316、SPI、驱动芯片、寄存器 |
| `mt6701.c` / `mt6701.h` | [源] | MT6701 SSI 读角度：24-clock @12.5MHz（1.92µs/帧），帧 = 14bit 角度 + Mg[3:0]（Mg[2]=按压）+ CRC6（X^6+X+1 逐位实现）；DO 经 mode-1 桥锁存 `SPIW_RXDATA1` | MT6701、SSI、角度、CRC6、按压 |
| `current.c` / `current.h` | [源] | 三相电流采样：3 路 logic 侧 ADC（SOA/B/C→PIN_10/11/12 固定模拟脚）背靠背连发 <100ns 相间偏差、PWM 更新中断里准同时采；含零点/增益校准 `g_cur_cal` | 电流采样、ADC、SOA、零点校准 |
| `foc.c` / `foc.h` | [源] | FOC 电压模式环：更新中断里"采电流 + 读角度 → 更新三路 CCR"；sincos LUT(256)、手感参数钩子（`g_foc`） | FOC、电压模式、控制环、手感参数 |
| `analog_ip.h` | [源] | CPLD 侧 `analog_ip` 宏的寄存器映射（CTRL/STAT 等 `__IO` 结构体），固件读写 CPLD 内 ADC/SPI 桥的接口层 | 寄存器映射、analog_ip、CPLD接口 |

---

## 4. logic/（CPLD 逻辑工程，28 个根文件 + 5 个编译子目录）

### 4.1 手写逻辑（改动 → 必须重跑三段式编译）

| 路径 | 类别 | 用途 | 关键词 |
|---|---|---|---|
| `analog_ip.v` | [源] | **用户逻辑主体（785 行）**：ADC×3 采样引擎 + `spi_mode_wrap` 实例化（`:250`）+ `ahb2apb`/`reg_ctrl` 寄存器桥；用户 Verilog 必须写在此 module 内部（SDK 规则） | 用户逻辑、ADC、module 内部、核心 |
| `spi_mode_wrap.v` | [源] | **mode-1 SPI 桥 ×2**：AG32 硬 SPI 固定 mode-0，此模块把 SCK 相移 90° 实现 mode-1（MT6701 SSI 与 DRV8316C 都要 mode-1），DO/SDO 下降沿捕获、帧尾锁存 | mode-1、SPI 桥、SCK 相移、SSI 桥 |
| `analog_ip_tmpl.v` | [生成] | `analog_ip.v` 的端口骨架模板（gen_vlog 生成：`analog_ip.v` 已存在时写成 `_tmpl` 避免覆盖），端口名由 gen_vlog 固定，改端口先看它 | 模板、端口、骨架、gen_vlog |
| `ahb2apb.v` | [源] | AHB→APB 总线桥（SDK 标准件，`example/logic/`、`Logic/logic/` 同款）：MCU 总线访问 CPLD 寄存器区 | 总线桥、AHB、APB、SDK 标准件 |
| `reg_ctrl.v` | [源] | 寄存器组控制（SDK 标准件）：`reg_mask/wren/wrdata` 寄存器读写握手，供 `analog_ip.v` 实例化 | 寄存器、reg_ctrl、SDK 标准件 |

### 4.2 prelogic 生成的工程文件（`-t prelogic` 重建，勿手改）

| 路径 | 类别 | 用途 | 关键词 |
|---|---|---|---|
| `foc2205.v` | [生成] | 顶层包装（"automatically generated, DO NOT modify"），prelogic 由 .ve + 设备模板生成 | 顶层、prelogic、自动生成 |
| `foc2205.qpf` / `foc2205.qsf` | [生成] | Quartus 工程文件（qsf 含 FAMILY/DEVICE/TOP + `VERILOG_FILE foc2205.v, analog_ip.v` + SDC 引用） | Quartus、工程、qsf、器件 |
| `foc2205.sdc` | [生成] | 时序约束（HSI 100ns 时钟、异步时钟组） | SDC、时序约束、时钟 |
| `foc2205_assignment_defaults.qdf` | [生成] | Quartus 默认 assignment 库（57KB，quartus 首次运行落盘） | 默认设置、qdf |
| `foc2205.proj` | [生成] | Quartus GUI 迁移状态（design=foc2205, device=AGRV2KQ32, fitter 参数） | GUI、工程状态 |
| `foc2205.vex` | [生成] | 引脚约束文件（"automatically generated"，pin→net 对照，Supra P&R 输入之一） | 引脚约束、vex、pin |
| `foc2205.asf` / `foc2205.pre.asf` / `foc2205.post.asf` / `foc2205.pre_map.asf` / `foc2205.post_map.asf`（5 个） | [生成] | Supra 各阶段 assignment 快照（含 `pio_begin DO NOT MODIFY` 段：PLL/IO 设置，af_run.tcl 按阶段 source） | asf、Supra、阶段快照 |
| `af_quartus.tcl` | [生成] | **Quartus 编译入口**（`quartus_sh -t af_quartus.tcl`）：先跑 `af_ip.tcl`，再 execute_flow -compile（5 次随机 seed/effort 重试） | Quartus、编译入口、tcl |
| `af_ip.tcl` | [生成] | 硬宏 IP 分区扫描：对 `alta_*` 系列宏实例 set PARTITION_* 保护，防综合把硬宏当死逻辑删除（2026-10-12 DAC 宕机修复同款护栏） | 宏分区、IP、护栏、alta_dac |
| `af_map.tcl` | [生成] | yosys 综合 map 步骤脚本（af_quartus 流程内部调用） | yosys、综合、map |
| `af_run.tcl` | [生成] | **Supra P&R 入口**（`af_cmd.bat -f af_run.tcl`）：布局布线 → 写 `_routed.v` → `bitgen` 产 `.bin` → `bin_to_asc` 产 `.inc` → gen_batch 产 `_batch.bin` | Supra、布局布线、位流、bitgen |
| `af_batch.tcl` | [生成] | 批量编译脚本（多 seed/effort/CORNER 组合跑 Quartus，af_run 的批量模式入口） | 批量、seed、多角、batch |
| `logic_log.txt` | [生成] | 上次 Supra 运行日志（末尾 `Total 0 fatals, 0 errors` = 编译通过） | 日志、编译结果、Supra 日志 |

### 4.3 位流与产物（根目录，10 个，git 跟踪）

| 路径 | 类别 | 用途 | 关键词 |
|---|---|---|---|
| `foc2205.bin` | [生成] | **压缩位流主产物**（22985 字节，Supra bitgen）→ `-t logic` 烧入 0x80034000 | 位流、烧录、bin、logic |
| `foc2205_batch.bin` | [生成] | gen_batch 打包的 MCU+logic 合并烧录文件（device_id + `--logic-address 0x80007000` + 压缩参数） | batch、合并烧录、批量 |
| `foc2205.inc` | [生成] | `.bin` 的 C 数组文本形式（`bin_to_asc`，117KB），编译期嵌入固件 | inc、C数组、嵌入位流 |
| `foc2205.hx` | [生成] | 头文件（`_AGM_BOARD_INFO`），prelogic 生成，固件 include 的 logic 元信息 | hx、头文件、board_info |
| `foc2205_routed.v` | [生成] | Supra 布局布线后网表（`write_routed_design`），验证布线结果用 | 布线网表、routed、验证 |
| `foc2205.asf` / `foc2205.pre.asf` / `foc2205.post.asf` / `foc2205.pre_map.asf` / `foc2205.post_map.asf` | [生成] | 见 §4.2 同名条目（此处列出便于按产物查找） | asf |

### 4.4 编译数据库子目录（整目录 git 忽略，可随时重建）

| 路径 | 文件数 | 类别 | 用途 / 重建方式 | 关键词 |
|---|---|---|---|---|
| `logic/db/` | 99 | [缓存] | Quartus 综合/适配数据库（map/cmp/hdb/cdb/qmsg 等）；`quartus_sh -t af_quartus.tcl` 重建 | Quartus数据库、db、综合缓存 |
| `logic/incremental_db/` | 65 | [缓存] | Quartus 增量编译分区缓存（compiled_partitions/，含 ADC 宏三份分区） | 增量编译、分区缓存 |
| `logic/alta_db/` | 21 | [缓存] | Supra P&R 数据库与报告（place.tx/route.tx、fmax/hold/setup 报告、pinmap/cellmap） | Supra、数据库、P&R报告 |
| `logic/alta_logs/` | 2 | [缓存] | Supra 运行原始日志（run.log / run.err） | Supra日志、run.log |
| `logic/quartus_logs/` | 14 | [缓存] | Quartus 各阶段报告（map/fit/sta/merge/flow 的 .rpt/.summary、**`foc2205.pin` 引脚分配报告**、`.done` 完成标记） | 报告、summary、pin报告、时序 |
| `logic/simulation/modelsim/` | 10 | [缓存] | ModelSim 仿真网表与 SDF（quartus_eda 生成 .vo/.sdo） | 仿真、ModelSim、网表、SDF |

---

## 5. 编译缓存（整目录可重建）

| 路径 | 文件数 | 类别 | 用途 / 重建方式 | 关键词 |
|---|---|---|---|---|
| `.pio/` | 40 | [缓存] | PlatformIO 构建产物：`build/foc2205/`（固件 elf/SDK 对象/ips）、`build/foc2205/ips` = prelogic 安装的 IP；`pio run -e foc2205` 重建 | 构建缓存、elf、编译（git 忽略） |

---

## 6. 按任务反查（task → file）

| 我想… | 看这里 |
|---|---|
| 画/改 PCB 原理图 | `docs/FOC2205_元件引脚连接网表.md`（互联） + `docs/DRV8316+MT6701_FOC驱动板接线设计.md`（电源树/布局） |
| 改引脚/换脚位 | `foc2205.ve` + `docs/FOC2205_QFN32芯片引脚评估与分配规范.md`（合法性），然后全套重编译（README 构建节） |
| 改 CPLD 逻辑（ADC/SPI 桥） | `logic/analog_ip.v`（module 内部）+ `logic/spi_mode_wrap.v`；端口变更看 `analog_ip_tmpl.v` |
| 改 SPI/角度读取 | `src/mt6701.c`（协议） + `logic/spi_mode_wrap.v`（mode-1 时序） |
| 改电流采样 | `src/current.c`（采样/校准） + `logic/analog_ip.v`（ADC 引擎） |
| 改 FOC 环/手感 | `src/foc.c`（环） + `src/pwm3ph.c`（中断时机） |
| 改驱动芯片配置 | `src/drv8316.c`（SPI 寄存器） |
| 改 bring-up 流程 | `src/main.c`（对应 `docs/…接线设计.md` §6-7） |
| 编译位流报错 | `logic/logic_log.txt`（Supra 结果）、`logic/quartus_logs/*.summary`（Quartus 各阶段）、`logic/alta_logs/run.err` |
| 查引脚分配 | `logic/quartus_logs/foc2205.pin`（实现后）、`foc2205.ve`（设计意图） |
| 查芯片协议细节 | `docs/` 两份规格书 PDF（MT6701 帧 p.3-4；DRV8316 帧 p.4-5） |
| 烧录 | README 构建节：`-t logic` 烧位流、`-t upload` 烧固件（自动校验 logic） |
| 看审查结论 | `docs/FOC2205_审查结果交付文档.md`（原文在 git 历史 29bc30d / 2aa56b1） |
| 查电机规格（极对数/电压/电流/扭矩） | `docs/电机参数.md`（文本，含交叉核对）；原图 `docs/电机参数.jpg` |
