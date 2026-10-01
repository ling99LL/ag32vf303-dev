# AG32VF303 开发工作区（AGM 遨格芯 RISC-V MCU + CPLD）

> 一台新电脑：装好环境 → `git clone` 本仓库 → 直接开发。私有仓库，配套交接文档见 [`docs/HANDOVER.md`](docs/HANDOVER.md)。

AGM **AG32** 系列把一颗 240MHz 级 RISC-V MCU 和 2K LE 的 CPLD 做进同一颗芯片，外设引脚全部经由 CPLD 布线区自由映射（`.ve` 文件定义）。本仓库是围绕 **AG32VF303**（目标芯片 AG32VF303KCU6，QFN-32）的完整开发工作区：环境配置记录、标准工程模板、MCU/纯 CPLD 两种流水灯实现、CAN/UART 复用测试、FOC 力反馈旋钮工程，以及官方例程归档。

## 仓库内容

```
├── AGENTS.md                        # ZCode/agent 工作区指令（含硬性规则速查）
├── docs/
│   ├── HANDOVER.md                  # ★ 权威交接文档：环境重现、烧录流程、排障表、纯 CPLD 三段式编译
│   ├── AGM_DAP_LINK_Rev2.51.pdf     # DAPLink 手册（p.12-13 = QFN32 完整引脚表）
│   ├── AG32_IDE开发环境搭建.pdf      # 官方环境搭建
│   └── AG32_MCU产品概览.pdf          # 产品线概览
├── projects/
│   ├── ag32vf303_flowled/           # 标准验证工程（本仓库的"模板工程"）
│   │   ├── platformio.ini           # 双环境：-e flow（MCU 版）/ -e cpldled（纯 CPLD 版）
│   │   ├── nano_board.ve            # 100 脚 demo 板引脚映射（LED + UART0）
│   │   ├── cpld_board.ve            # 纯 CPLD 版引脚映射（LED_D1..4 为 :OUTPUT 信号）
│   │   ├── src/flow_main.c          # MCU 版流水灯（软件计时）
│   │   ├── src/min_main.c           # 纯 CPLD 版的最小 MCU 宿主（空循环）
│   │   └── logic/                   # prelogic 生成的 Supra/Quartus 工程 + 用户 Verilog analog_ip.v
│   └── can_uart_test/               # CAN/UART 复用测试工程
├── foc/foc_knob/                    # FOC 力反馈旋钮工程（硬件 + host 上位机脚本）
├── example/                         # AGM 官方例程归档（勿改，接口约定与引脚定义的出处）
└── example_logic_led/               # 官方 CPLD LED 例程归档（勿改）
```

## 环境搭建（新电脑，约 30 分钟）

详细步骤与截图级说明见 [`docs/HANDOVER.md`](docs/HANDOVER.md) §2，概要：

1. **前置**：Windows 10/11 64 位，8G+ 内存；安装 [VSCode](https://code.visualstudio.com/) 与 [Python ≥3.10](https://www.python.org/)
2. **SDK**：百度网盘 `pan.baidu.com/s/17bp-zAnsYRuVMRTSSVHN5A`（提取码 `12ej`）下载最新 `AgRV_pio-x.x.x-win64-release.exe`，静默安装：
   ```bat
   AgRV_pio-1.8.10-win64-release.exe -s
   ```
   自动部署 PlatformIO Core + AgRV 平台 + RISC-V GCC + Supra + OpenOCD 到 `%USERPROFILE%\.platformio`
3. **VSCode 扩展**：`code --install-extension platformio.platformio-ide`
4. **硬件**：AGM 官方 DAPLink（CMSIS-DAP v2，Win10 免驱）+ 开发板；确认 DAPLink 上 **J3V 跳线连通**（排线给目标板供电）、J4 断开
5. **验证**：设备管理器出现 `CMSIS-DAP v2` + `USB 串行设备 (COMx)`；工程目录 `pio run -e flow` 编译通过

> 注意：SDK 与工程路径**不能含中文**；用户目录需为英文。

## 快速开始

```bash
pio="C:/Users/Administrator/.platformio/penv/Scripts/pio.exe"

# MCU 版流水灯（软件计时，GPIO4_1..4 → PIN_34/33/32/31，低电平点亮）
$pio run -e flow -t upload          # 编译 + 烧录（自动先校验/烧逻辑位流，再烧程序）
$pio run -e flow -t monitor         # 串口看 printf

# 纯 CPLD 版流水灯（硬件计数器，halt CPU 灯照常流）
$pio run -e cpldled -t prelogic     # ① 生成 Supra/Quartus 工程
cd logic
C:/altera/13.0sp1/quartus/bin64/quartus_sh.exe -t run_quartus.tcl   # ② Quartus 综合
cmd /c run_supra.bat                # ③ Supra 布局布线 → cpld_board.bin
cd ..
$pio run -e cpldled -t logic        # ④ 烧逻辑位流
$pio run -e cpldled -t upload       # ⑤ 烧最小 MCU 宿主
```

| | MCU 版（`-e flow`） | 纯 CPLD 版（`-e cpldled`） |
|---|---|---|
| 节拍来源 | C 代码软件计时 | fabric 内 32 位计数器（200MHz 硬件分频） |
| 改花样 | 改 C → 只重烧程序 | 改 Verilog → 三段式重烧逻辑 |
| CPU 依赖 | 停 CPU 灯停 | **halt CPU 灯照常流** |
| 用途 | 业务逻辑 | 独立指示灯 / 确定性时序 / 不占 CPU |

## 硬性规则（踩坑总结，务必遵守）

1. **`logic_device` 必须匹配封装**：100 脚 demo 板 = 默认 `AGRV2KL100`（不写即默认）；QFN32 KCU6 = `AGRV2KQ32`
2. **必须先烧 LOGIC 才能访问 MCU**（调试口也依赖 logic 路由；空 logic 板 `reset run` 卡 ROM）
3. **logic 地址陷阱**：压缩位流 `0x80034000`、未压缩 `0x80027000`，芯片选项字节记录 ROM 加载地址且 `-t logic` 不更新它——工程统一 `logic_compress = true`
4. **改 `.ve`** → 重走逻辑编译并烧 logic；只改 C → 仅 `upload`
5. DAPLink 供电靠 **J3V 跳线**（DPIDR 读回 0 = 板子没电，先查它）
6. 板载 LED：GPIO4_1..4 → die pads PIN_34/33/32/31，**低电平点亮**（接 VCC 侧）
7. 工程路径不能含中文；COM 口随 USB 口漂移
8. 用户 Verilog 必须写在 `logic/analog_ip.v` **module 内部**（Quartus 13 按 Verilog-2001 解析）
9. 给 af.exe 传参用 `.bat` 包装文件（内联引号会被打碎）

完整排障表（DPIDR=0、卡 ROM、device id 不符、引脚报错等）见 [`docs/HANDOVER.md`](docs/HANDOVER.md) §5。

## 换到 QFN32 自研板（AG32VF303KCU6）

1. `platformio.ini` 加 `logic_device = AGRV2KQ32`
2. 按 `docs/AGM_DAP_LINK_Rev2.51.pdf` **p.12-13** 的 QFN32 引脚表重写 `.ve`（可用 pad：1,2,3,5,7-15,18-23,26-29,31；PIN_24/25 = JTMS/JTCK 调试口不可挪用；PIN_20/21 留给 UART0）
3. DAPLink 接线只需四根：TCK→PIN_25、TMS→PIN_24、GND、VCC3V3
4. 重走逻辑编译 + 烧录

## 硬件与资料

- **开发板**：AGM 100 脚 demo 板（AG32VF303 级 die，256KB Flash / 128KB SRAM，device id `0x40200001`）
- **目标芯片**：AG32VF303KCU6 —— QFN-32，26 IO，RISC-V 200/248MHz + 2K LE CPLD，12bit ADC / 10bit DAC
- **下载器**：AGM 官方 DAPLink（CMSIS-DAP v2，VID:PID 0xcafe:0x1001）
- **官方渠道**：[tcx-micro.com](http://www.tcx-micro.com/)（资料站）、[agmsemi.com](http://www.agmsemi.com/)、QQ 群 379254175、tech@agmsemi.com
- 参考项目：[scottbez1/smartknob](https://github.com/scottbez1/smartknob)（未包含在本仓库）

---
*环境验收记录与踩坑过程详见 `docs/HANDOVER.md`。 maintained by [@ling99LL](https://github.com/ling99LL)*
