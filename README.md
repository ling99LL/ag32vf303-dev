# AG32VF303 开发工作区（AGM 遨格芯 RISC-V MCU + CPLD）

本仓库是围绕 **AG32VF303**（目标芯片 AG32VF303KCU6，QFN-32）的完整工程与方案开发工作区：包含环境配置记录、CPLD 片上逻辑分析仪、FOC 电机驱动、标准工程模板、CAN/UART 复用测试及官方例程归档。

AGM **AG32** 系列将一颗 240MHz 级 RISC-V MCU 与 2K LE 的 CPLD 集成在单颗芯片内，外设引脚全部经由 CPLD 布线区自由映射（通过 `.ve` 约束文件定义）。

---

## 核心工程概览

| 模块 / 路径 | 目标芯片 / 封装 | 核心特性 / 功用 |
|---|---|---|
| **[`Logic/`](Logic/)** | AG32VF303KCU6 (QFN-32) | **4 通道 CPLD 硬件逻辑分析仪**：100MSa/s 硬件采样、Block RAM 缓冲、硬件边沿触发与预触发、实时 RLE 压缩，原生兼容 SUMP / PulseView。 |
| **[`FOC2205/`](FOC2205/)** | AG32VF303KCU6 (QFN-32) | **独立三相 FOC 驱动板**：MT6701 磁编码器 + DRV8316C 驱动 + 2205 无刷电机，三电阻电流采样与 SVPWM 控制。 |
| **[`projects/ag32vf303_flowled/`](projects/ag32vf303_flowled/)** | 100 脚 Demo / QFN-32 | **标准验证模板**：MCU 软件版 (`-e flow`) 与纯 CPLD 硬件版 (`-e cpldled`) 双流水灯参考。 |
| **[`projects/can_uart_test/`](projects/can_uart_test/)** | AG32VF303 | CAN 与 UART 引脚复用与回环测试工程。 |
| **[`foc/foc_knob/`](foc/foc_knob/)** | AG32 系列 | FOC 力反馈旋钮原型工程与 Host 上位机脚本。 |

---

## 目录结构

```text
├── AGENTS.md                        # AI Agent 工作区指令与硬性规则速查
├── docs/                            # 架构交接与芯片参考手册
│   ├── HANDOVER.md                  # ★ 权威交接文档：环境重现、烧录流程、排障表、纯 CPLD 编译
│   ├── AGM_DAP_LINK_Rev2.51.pdf     # DAPLink 手册（p.12-13 为 QFN32 完整引脚表）
│   ├── AG32_IDE开发环境搭建.pdf      # 官方环境搭建文档
│   └── AG32_MCU产品概览.pdf          # 产品线概览
├── Logic/                           # ★ CPLD 硬件逻辑分析仪工程 (PulseView/SUMP 原生支持)
├── FOC2205/                         # ★ 独立 FOC 驱动板工程 (DRV8316 + MT6701 + 2205 电机)
├── projects/
│   ├── ag32vf303_flowled/           # 标准验证工程（MCU/CPLD 双环境流水灯）
│   └── can_uart_test/               # CAN/UART 复用测试工程
├── foc/foc_knob/                    # FOC 力反馈旋钮验证工程
├── example/                         # AGM 官方例程归档（只读参考）
└── example_logic_led/               # 官方 CPLD LED 例程归档（只读参考）
```

---

## 环境搭建

详细步骤与图文说明见 [`docs/HANDOVER.md`](docs/HANDOVER.md) §2：

1. **操作系统**：Windows 10/11 64 位；安装 [VSCode](https://code.visualstudio.com/) 与 [Python ≥3.10](https://www.python.org/)。
2. **SDK 安装**：
   从百度网盘 `pan.baidu.com/s/17bp-zAnsYRuVMRTSSVHN5A`（提取码 `12ej`）下载最新版 `AgRV_pio-x.x.x-win64-release.exe`，静默安装：
   ```cmd
   AgRV_pio-1.8.10-win64-release.exe -s
   ```
   自动部署 PlatformIO Core、AgRV 平台、RISC-V GCC、Supra 与 OpenOCD 到 `%USERPROFILE%\.platformio`。
3. **VSCode 插件**：安装 `platformio.platformio-ide` 扩展。
4. **硬件连接**：
   - 使用 AGM 官方 DAPLink（CMSIS-DAP v2）。
   - 确认 DAPLink 上的 **J3V 跳线短接**（通过排线为目标板供电），**J4 跳线断开**。
5. **验证环境**：
   设备管理器中出现 `CMSIS-DAP v2` 与 `USB 串行设备 (COMx)`；在终端中 `pio` 命令可正常调用。

> **注意**：SDK 与工程所在路径**严禁包含中文或空格**。

---

## 快速上手与常用命令

建议在命令行中将 PlatformIO 加入系统环境变量（PATH），或直接调用 `%USERPROFILE%\.platformio\penv\Scripts\pio.exe`：

### 1. CPLD 硬件逻辑分析仪 (`Logic/`)
```bash
cd Logic
pio run -e logic_board -t upload     # 编译固件并烧录
pio run -e logic_board -t monitor    # 查看运行日志 (USB CDC / UART)
```
- 配合上位机：PulseView 选用 Openbench Logic Sniffer (OLS) 驱动连接，采样率最高可达 100 MSa/s。

### 2. FOC 2205 电机驱动工程 (`FOC2205/`)
```bash
cd FOC2205
pio run -e foc2205 -t upload         # 烧录固件
pio run -e foc2205 -t monitor        # 监听 115200 调试输出
```

### 3. 流水灯验证模板 (`projects/ag32vf303_flowled/`)
```bash
cd projects/ag32vf303_flowled

# MCU 软件流水灯 (GPIO4_1..4 -> PIN_34/33/32/31)
pio run -e flow -t upload

# 纯 CPLD 硬件分频流水灯 (CPU 挂起仍正常运行)
pio run -e cpldled -t prelogic
cd logic
quartus_sh -t run_quartus.tcl
cmd /c run_supra.bat
cd ..
pio run -e cpldled -t logic          # 烧录 CPLD 位流
pio run -e cpldled -t upload         # 烧录最小 MCU 镜像
```

---

## 芯片开发硬性规则

1. **`logic_device` 匹配封装**：
   - 100 脚 Demo 板：默认 `AGRV2KL100`。
   - QFN-32 (AG32VF303KCU6)：必须显式声明 `logic_device = AGRV2KQ32`。
2. **必须先烧录 LOGIC 才能调试 MCU**：JTAG 调试引脚同样经过 CPLD 路由；逻辑为空时 MCU 处于未配置状态。
3. **位流压缩配置**：工程统一采用 `logic_compress = true`（压缩位流烧录地址 `0x80034000`）。
4. **管脚修改规则**：只要修改 `.ve` 约束文件，必须重新执行完整的逻辑生成与位流烧录流程；单纯修改 C 代码只需 `upload`。
5. **DAPLink 供电排查**：若 DAPLink 返回 `DPIDR = 0x00000000`，代表目标板未上电，请检查 J3V 跳线与目标板连接。

---

## 硬件与参考资源

- **目标芯片**：AG32VF303KCU6（QFN-32，26 可用 IO，RISC-V 248MHz + 2K LE CPLD，12-bit ADC）
- **官方渠道**：[tcx-micro.com](http://www.tcx-micro.com/)（资料站）、[agmsemi.com](http://www.agmsemi.com/)、官方支持邮箱 `tech@agmsemi.com`、QQ 技术群 `379254175`
- **参考项目**：[scottbez1/smartknob](https://github.com/scottbez1/smartknob)

---
*环境排障指南与完整调试步骤请查阅 [`docs/HANDOVER.md`](docs/HANDOVER.md)。*
