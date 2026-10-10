# AG32 开发工作区说明（AGENTS.md）

本工作区用于 AGM 遨格芯 AG32 系列芯片（RISC-V MCU + 2K LE CPLD 二合一）的开发与验证。工作区根目录是 git 仓库（分支随当前工程走，如 `foc2205`），各目录独立成工程。

## 权威文档（改动敏感区域前先读）

- **`docs/HANDOVER.md`** — 环境总览、烧录流程、排障表、纯 CPLD 三段式编译（§9）、QFN32 引脚表出处。任何 AG32 操作前必读。
- `.zcode/skills/ag32-dev/SKILL.md` — AG32 开发 skill（命令速查 + 硬性规则）。
- `docs/AGM_DAP_LINK_Rev2.51.pdf` — DAPLink 手册，p.12-13 是 QFN32 完整引脚表。
- `docs/` 其余 PDF 为环境搭建与产品概览官方文档。

## 目录结构

| 目录 | 用途 |
|---|---|
| `projects/ag32vf303_flowled/` | 标准验证工程：MCU 版流水灯（`-e flow`）+ 纯 CPLD 版（`-e cpldled`）+ 已删逻辑的参考痕迹，platformio.ini 是配置范本 |
| `projects/can_uart_test/` | CAN/UART 复用测试工程 |
| `example/`、`example_logic_led/` | **AGM 官方参考例程（用户提供的原始资料，勿修改勿删除）**，LED 引脚与接口约定的出处 |
| `foc/foc_knob/` | FOC 力反馈旋钮工程（带 host 上位机与 probe/reset 脚本） |
| `FOC2205/` | AG32VF303KCU6(QFN32)+MT6701QT-STD+DRV8316C 三芯片 FOC 驱动板，2205 电机力反馈旋钮；**与 `foc/foc_knob` 零交叉的独立工程**，`foc2205.ve` + `logic/`(ADC×3 + SPI mode1 桥×2) |
| `Logic/` | AG32VF303 4 通道逻辑分析仪（方案 B：CPLD 硬件采样），SUMP/OLS 协议直连 PulseView/Sigrok；`logic_board.ve` + USB CDC + 性能实测报告 |
| `ref-smartknob/` | scottbez1/smartknob 参考源码副本（只读参考） |
| `docs/` | 交接文档与官方 PDF 归档 |

## 工具链与命令

- PIO CLI：`C:/Users/Administrator/.platformio/penv/Scripts/pio.exe`（SDK AgRV_pio 1.8.10 已装齐，含 Supra/OpenOCD/工具链）。
- 构建/烧录（在对应工程目录）：
  ```bash
  pio run -e flow -t upload        # MCU 固件：编译+烧 logic 校验+程序
  pio run -e flow -t buildlogic    # 仅生成逻辑位流（纯 VE 流程）
  pio run -e cpldled -t prelogic   # 自定义逻辑：生成 logic/ 工程
  ```
- 自定义 CPLD 逻辑三段式（logic_dir 流程下 **buildlogic 不产位流**）：`prelogic` → `logic/run_quartus.tcl`（Quartus 无头综合）→ `logic/run_supra.bat`（Supra 布局布线）→ `-t logic` + `-t upload`。
  - **脚本名勘误**：`run_quartus.tcl`/`run_supra.bat` 包装脚本只存在于 `projects/ag32vf303_flowled/logic/`。`FOC2205/logic/` 与 `Logic/logic/` 只有原始 `af_quartus.tcl` / `af_run.tcl`，需直接调 Quartus 与 Supra（`quartus_sh -t af_quartus.tcl` → `af_cmd.bat -f af_run.tcl`），各工程完整命令见其自身 README。
- OpenOCD 直读调试：`halt` 后用 `mem2array`+`echo`（`mdw` 在 openocd_cmd.bat 下可能静默），可 halt 后 `mww` 直接驱动 GPIO 验证硬件。

## 硬性规则（违反即失败）

1. **logic_device 必须匹配封装**：100 脚 demo 板 = 默认 AGRV2KL100（不写即默认）；QFN32 KCU6 = `AGRV2KQ32`。
2. **必须先烧 LOGIC 才能访问 MCU**（调试口也依赖 logic；空 logic 时 `reset run` 卡 ROM，PC≈0x0001xxxx）。
3. **logic 地址陷阱**：压缩位流 0x80034000 / 未压缩 0x80027000，选项字节记录 ROM 加载地址，`-t logic` 不更新选项字节——格式或地址与之前不一致会卡 ROM。工程统一 `logic_compress = true`。
4. **改 `.ve`** → `buildlogic`/三段式 + 重烧 logic；只改 C → 仅 `upload`。
5. DAPLink 用 `protocol = cmsis-dap-openocd`；目标板供电靠 DAPLink **J3V 跳线**（DPIDR=0x00000000 = 没电，先查供电和 J4 跳线）。
6. 100 脚 demo 板 LED：GPIO4_1..4 → die pads PIN_34/33/32/31，**低电平点亮（接 VCC 侧，实测确认）**。QFN32 可用 pad：1,2,3,5,7-15,18-23,26-29,31；PIN_24/25=JTMS/JTCK 不可挪用。
7. 工程路径必须纯英文（SDK 不支持中文路径）；串口号随 USB 口漂移（platformio.ini 里 COM26 需按设备管理器核对）。
8. 用户 Verilog 必须写在 `logic/analog_ip.v` 的 **module 内部**（Quartus 13 按 Verilog-2001 解析）；重新 prelogic 会覆盖 top 但不覆盖 analog_ip.v。
9. 给 af.exe 传参必须用 .bat 包装文件（Git-Bash 内联引号会被打碎）。

## 环境现状（2026-09 验收）

- MCU 流水灯与纯 CPLD 流水灯均已烧录验收；JTAG 采样/无串口调试技巧见 HANDOVER §3.5/§9.4。
- `FOC2205/` 全链路构建实测通过（Quartus 综合 + Supra P&R + 位流校验），硬件实测细节见 `FOC2205/README.md`；`Logic/` 性能实测数据见 `Logic/PERFORMANCE_REPORT.md`。
- SDK 来源：百度网盘 `pan.baidu.com/s/17bp-zAnsYRuVMRTSSVHN5A` 提取码 `12ej`；官方技术群 QQ 379254175。
- 换 QFN32 自研板时：改 `logic_device = AGRV2KQ32` + 按 DAPLink 手册 p.12-13 重写 VE + 重烧 logic。
