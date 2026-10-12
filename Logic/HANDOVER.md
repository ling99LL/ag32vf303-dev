# Logic 4 通道逻辑分析仪 — 交接快照（2026-10-12）

## 当前版本

- **固件 / 上位机脚本**：git commit `62f7375`（`fix(logic): resurrect DAC hard macro + calibrate DMA pacing; add board test tools`，分支 `foc2205`）；上轮 `d1818b3`（`feat(logic): raise self-test square wave to 10/25/50 MHz + on-board loopback verification`）——**均未推送**（`foc2205` 本地领先远端，含 `94f8b3f`、`d1818b3`、`62f7375` 及本文档提交）
- **板上已烧录（2026-10-12 夜，与仓库一致）**：固件 = v1.1 + DAC 定速修复（`62f7375` 的 `src/main.c`，24768B）；CPLD logic 位流 = `62f7375` 的 `logic_board.bin`（22368B，含 DAC0 硬宏 + keep-guard + P5 引擎 + 新引脚，加载地址 `0x80034000`）。两者均经 DAPLink OpenOCD 写入 + verify；**冒烟 19/19、回环 18/18 通过（见"实测结论"）**。
- **自测波档位表**（`Logic/src/main.c`）：div=0 → **50 MHz**、div=1 → **25 MHz**、div≤4 → **10 MHz**、其余 → 20 kHz；`f = 100MHz/(SQ_DIV+1)`（寄存器 `0x0C`，低位 A、高位 B）
- **SUMP 扩展命令**：`0x83` 手动覆盖方波分频（payload `0xFFFFFFFF` = 自动档位表）；`0x00` 复位时自动恢复 AUTO；新增发生器命令 `0x84`~`0x8D`（见 README §9）
- **2026-10-12 引脚重映射（已随夜版固件/位流上板）**：LED 改为 `GPIO4_1..4 → PIN_19/18/13/14`；CH0~CH3 = PIN_7~10 不变。协议/逻辑级冒烟通过；**PIN_11 已由回环闭环验证**；LED 指示与 PIN_5 物理输出待肉眼/跳线确认（见"实测结论"末条）。
- **2026-10-12 信号发生器大升级（已上板，冒烟通过）**：
  - **PIN_11 = DAC0 模拟波形输出**：10bit DAC 硬核（`apb_dac`/`alta_dac`，FIXED_COORD `{22 11}` 绑定，见 `logic/logic_board.asf` 用户段）+ MCU DMA 循环播表（DMAC CH0 → `0x60003000` 窗口，rate = 100MHz/(DIV+1)），波形：正弦/方波/锯齿/三角，频率 1 Hz~（上限/最少采样点），幅度 1~100%，输出上电默认关闭。旧 `TEST_OUT=PIN_11` 数字分配已移除（PIN_11 不再有数字驱动，避免与 DAC 冲突）。**定速标定（10/12 夜）**：采样率上限默认 5 MSa/s（AHB→APB DMA 每样本 ~16 总线周期握手；波表重复填满 2048 点缓冲使 LLI 重载率降至 1/2048，消除小表高频频率减半/偏低问题）。
  - **PIN_5 = 数字输出**（CPLD `SG_OUT`），内部二选一：①**方波 1 Hz~100 MHz**（级联递减计数器 A/B 双段分频，`f=100MHz/((A+1)(B+1))`，200MHz 域 Fmax 214.9MHz）；②**延时触发/脉冲引擎**（延时→高/低电平、延时→脉冲、上位机触发；延时 0~42.9s@10ns 步进，时基可 ×10/100/1000；状态/剩余时间可回读）。
  - 上位机：`Logic/tools/run_wavegen.bat`（Python 3.11 Tkinter GUI），完整协议见 `Logic/README.md` §9。
  - 编译记录：prelogic → run_quartus_steps.bat → run_supra.bat 全链 **0 errors**，位流 22368 字节（≈21.8KiB，终版；首版 21911B）；固件 RAM 62.5% / Flash 9.4%。**2026-10-12 夜已上板烧录，冒烟首轮 18/18 → 定速修复后 19/19，回环 18/18（见下）。**
  - **`alta_dac` 硬宏宕机修复（10/12 夜，关键）**：`dac_dout` 悬空 → Quartus 当死逻辑删除整个硬宏（连带 Supra `FIXED_COORD` 绑定失效、PIN_11 静默无输出）；修复 = `analog_ip.v` 加 `preserve` keep-guard 寄存器 + 构建脚本第 1 步跑 `af_ip.tcl` 生成 `alta_auto` 宏分区；`run_quartus_steps.bat` 已加两道自动护栏（qsf 缺分区行 / 网表缺 `alta_dac` 都直接报错阻止出流）。

## 硬件与接口

- 芯片：AG32VF303，QFN32（`logic_device = AGRV2KQ32`，**不可改**）
- 引脚：CH0~CH3 = PIN_7/8/9/10（输入，弱下拉；板级编号 CH1~CH4）；**PIN_11 = DAC0 模拟波形输出**（QFN32 固定复用，勿再分配数字功能）；**PIN_5 = SG_OUT 数字输出**（方波 1Hz~100MHz 或触发/脉冲引擎）；LED = PIN_19/18/13/14（低电平点亮）
- 接口：USB 2.0 FS CDC = **COM33**（SUMP/OLS，PulseView 直连）；UART0 调试 = COM26；烧录用 DAPLink `cmsis-dap-openocd`
- 自测回环：**PIN_10 ↔ PIN_11 跳线**（10/12 夜已接上并回环实测 **18/18**：DAC 全波形经 PIN_11→PIN_10 捕获验证）；自测方波（PIN_5）回环需把跳线改接 **PIN_5 ↔ 任一 CH**（未做）

## 实测结论（均上板实测，非纸面）

- `live_hardware_test.py` 全套 **100% PASS**：8 档采样率绝对时基校验、硬件电平触发、8192 满载上传（~1.0 MB/s 净吞吐）
- 高频自测波：50 MHz @100MSa/s（2 点/周期严格 1010）、25 MHz @4 点、10 MHz @10 点等 6 项沿数与理论值精确吻合
- 稳定性：6 组高频配置 × 60 轮 = 360 次捕获 **0 失败**
- 详细数据见 `Logic/PERFORMANCE_REPORT.md` §2.1 / §2.1b

- **2026-10-12 夜 烧录 + 冒烟测试**（`tools/smoke_test.py`，板载实跑；首轮 18/18，定速修复后终版 **19/19 PASS**）：
  - 烧录：位流 22368B @0x80034000、固件 24768B @0x80000000（终版已重烧对齐仓库 commit `62f7375`），DAPLink OpenOCD 写入 + verify 通过；重启后 COM33 重新枚举、SUMP ID `1ALS` 应答正常
  - 协议：GEN v1.1 GET_INFO 正常（启动态 = DAC 关 / PIN_5 方波源）；DAC 使能/关闭、四波形切换、频率自动求解全部按预期回报（首轮 1MHz 方波 → 1.0417MHz 偏低；定速修复后 → **1.000000MHz 精确**）
  - CPLD 采样器：8192 点满载捕获回传完整；4 通道扫描干净（弱下拉、零串扰）
  - P5 触发引擎（寄存器级实测）：主机脉冲模式总时长 0.308s（编程 0.1s 延时 + 0.2s 脉宽）、高电平段 0.103~0.288s、剩余计数从 9989 起递减；延时电平模式 arm→输出拉高 0.053s（编程 50ms）；clear 复位正常——**时序与编程值精确吻合**
  - 静态核验：Supra 运行日志确认 `FIXED_COORD {22 11}` 在正式 P&R 中生效（DAC0 硬核实际放置在 PIN_11 坐标）
- **2026-10-12 夜 回环测试**（`tools/loopback_test.py`，PIN_10↔PIN_11 跳线，**18/18 PASS**）：
  - 关闭态基线 CH1~CH4 全静态；DAC 1MHz 方波使能后自动定位到 bit3/PIN_10（164 边沿，理论 163.8）——`alta_dac` 宏修复的直接闭环验证
  - 方波扫频 10 kHz / 100 kHz / 1 MHz / 2.5 MHz：实测误差 0.1% ~ 2.9%（定速修复后 1 MHz / 2.5 MHz 实测均 0.1%）
  - 四波形（正弦/方波/锯齿/三角 @100 kHz）回环均可见、幅度/占空比正常、关闭后静默
- **待物理确认**：PIN_5 数字输出（把跳线改接 **PIN_5 ↔ 任一 CH** 后复跑 `tools/loopback_test.py COM33` 或冒烟即可）；LED 启动序列（4 颗逐亮 + 2 次全亮闪 + LED1 常亮 + 1.5s 心跳）需肉眼确认

## 常用命令（工作目录 `Logic/`）

```bash
pio run -e logic_analyzer -t upload      # 只改 C：编译 + DAPLink 烧录（不重建 logic）
pio run -e logic_analyzer -t prelogic    # 改 .ve：先重新生成 logic 工程
python live_hardware_test.py             # 上板回归（COM33；需 PIN_5↔任一 CH 跳线，自测方波源已改 PIN_5）
python tools/smoke_test.py COM33         # 烧录后冒烟（协议/采样/引擎/DAC，19 项，无跳线也可跑）
python tools/loopback_test.py COM33      # 板级回环（需 PIN_10↔PIN_11 跳线；DAC 全波形闭环，18 项）
# 改 .ve 必须三段式：prelogic → logic/run_quartus_steps.bat → logic/run_supra.bat → -t logic + -t upload
#   ★ 勿用 run_quartus.tcl / execute_flow（本机 Quartus 收尾 fast-fail 会被误判为失败，见下节）
```

## 交接注意事项 / 待办

- **⚠️ Quartus 环境问题（2026-10-12 排查，影响本机所有 logic 编译）**：Quartus II 13.0sp1 命令行工具（map/cdb/fit/sta/eda）在本机**总会完整完成工作并写出 "Successful" 报告，但进程收尾阶段以 Windows fast-fail（退出码 `0xC0000409` STATUS_STACK_BUFFER_OVERRUN）退出**——stdout 缓冲未刷新，造成日志"中途截断"的假象；`run_quartus.tcl`（execute_flow 一键流程）在 map 后误报 `Error (293007) ... ended unexpectedly` 而中止。**对策**：改用 `logic/run_quartus_steps.bat`——分步执行同一流程（忽略退出码），以各步 `quartus_logs\*.summary` 报告为准；2026-10-12 从零实测全链通过（Quartus 六步 + Supra，0 errors）。已用"改动前配置"对照复现同一现象，**与设计源码无关**；如将来 Quartus 环境修复（重装/换机），可直接回到 `run_quartus.tcl`。
- 本轮 3 个提交（`94f8b3f` / `d1818b3` / `62f7375` + 本文档提交）**均未推送**；`Logic/benchmark_usb.py` 及根目录若干散件仍未 git 跟踪（历史遗留）
- PulseView GUI 实际抓取未实证（协议层 SUMP 已实测）；边沿触发使用 SUMP 非标准位（mask bit4 → ctrl bit12）扩展实现
- 50 MHz 自测波处于 100 MSa/s 奈奎斯特边缘（2 点/周期），数字级验证通过，但波形形态需示波器确认
- 换引脚自测波/采样通道时：改 `Logic/logic_board.ve` 的 PIN 声明，需重走三段式并重烧 logic；避开 PIN_24/25(JTAG)、PIN_22/23(USB DM/DP)、PIN_1(晶振)
