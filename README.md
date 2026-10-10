# AG32VF303 开发工作区

AGM（遨格芯）AG32 系列把 RISC-V MCU 和 2K LE 的 CPLD 做进同一颗芯片。外设引脚不是固定的，经 CPLD 布局布线区自由映射，映射关系写在 `.ve` 约束文件里。

这个仓库围绕 AG32VF303KCU6（QFN-32）做了几个工程，也记录了开发环境是怎么搭起来的。各目录是独立工程，各有自己的 platformio.ini。

## 工程

- **`Logic/`** — 4 通道逻辑分析仪。CPLD 纯硬件同步采样，硬件触发加预触发，样本进 Block RAM，MCU 经总线读出来走 USB CDC。协议是 SUMP，PulseView 直接连。实测指标和协议分析见 [Logic/PERFORMANCE_REPORT.md](Logic/PERFORMANCE_REPORT.md)。
- **`FOC2205/`** — 三相 FOC 驱动板，2205 无刷电机的力反馈旋钮。MT6701QT 磁编码器（SSI）+ DRV8316C（3x PWM，SPI 配置）+ 三电阻电流采样，GPTIMER0 中心对齐 20kHz 控制环。和 `foc/foc_knob` 完全独立，不共用任何文件。
- **`projects/ag32vf303_flowled/`** — 流水灯验证工程。MCU 软件版（`-e flow`）和纯 CPLD 版（`-e cpldled`）各一个，platformio.ini 可以当配置范本。
- **`projects/can_uart_test/`** — CAN 与 UART 的引脚复用、回环测试。
- **`foc/foc_knob/`** — FOC 力反馈旋钮的早期原型，带 host 上位机和 probe/reset 脚本。
- **`example/`、`example_logic_led/`** — AGM 官方例程原件，只读，别改。
- **`docs/`** — 交接文档和官方 PDF。其中 [HANDOVER.md](docs/HANDOVER.md) 汇总了环境搭建、烧录流程、排障表，动手前先看它。

## 目录

```text
AGENTS.md                       工作区约定与硬性规则
docs/
  HANDOVER.md                   环境搭建、烧录流程、排障表、纯 CPLD 编译
  AGM_DAP_LINK_Rev2.51.pdf      DAPLink 手册（p.12-13 是 QFN32 完整引脚表）
Logic/                          逻辑分析仪
FOC2205/                        FOC 驱动板
projects/ag32vf303_flowled/     流水灯验证
projects/can_uart_test/         CAN/UART 复用测试
foc/foc_knob/                   力反馈旋钮原型
example/  example_logic_led/    官方例程（只读）
```

## 环境搭建

完整步骤见 [docs/HANDOVER.md](docs/HANDOVER.md) §2，这里只记要点。

Windows 10/11 64 位，装 VSCode 和 Python ≥3.10。SDK 从百度网盘下（`pan.baidu.com/s/17bp-zAnsYRuVMRTSSVHN5A`，提取码 `12ej`），拿到 `AgRV_pio-1.8.10-win64-release.exe` 后静默安装：

```cmd
AgRV_pio-1.8.10-win64-release.exe -s
```

装完 PlatformIO Core、AgRV 平台、RISC-V GCC、Supra、OpenOCD 都落在 `%USERPROFILE%\.platformio`。再给 VSCode 装 `platformio.platformio-ide` 扩展。

SDK 和工程路径**不能有中文和空格**，Quartus 13 在这种路径下会出问题。

## 常用命令

pio 建议加进 PATH，或者直接用 `%USERPROFILE%\.platformio\penv\Scripts\pio.exe`。

逻辑分析仪和 FOC 板的固件就是常规 upload：

```bash
cd Logic  && pio run -e logic_board -t upload
cd FOC2205 && pio run -e foc2205    -t upload
```

流水灯工程的纯 CPLD 版要走完整三段式（logic_dir 流程下 buildlogic 不出位流）：

```bash
cd projects/ag32vf303_flowled
pio run -e cpldled -t prelogic     # 生成 logic/ 工程
cd logic
quartus_sh -t run_quartus.tcl      # Quartus 综合
cmd /c run_supra.bat               # Supra 布局布线，出位流
cd ..
pio run -e cpldled -t logic        # 烧位流
pio run -e cpldled -t upload       # 烧最小 MCU 镜像
```

`run_quartus.tcl` / `run_supra.bat` 这两个包装脚本只在 flowled 工程里有。`FOC2205/logic/` 和 `Logic/logic/` 里只有原始的 `af_quartus.tcl` / `af_run.tcl`，得直接调 Quartus 和 Supra，完整命令见各自 README。

## 踩过的坑

- `logic_device` 要和封装对上。100 脚 Demo 板用默认的 AGRV2KL100（不写就行），QFN-32 必须显式写 `logic_device = AGRV2KQ32`。
- **logic 必须先烧，否则 MCU 调不通。** JTAG 调试脚同样走 CPLD 路由，logic 为空时 `reset run` 会卡 ROM，PC 停在 0x0001xxxx 附近。
- 位流地址有坑：压缩位流在 0x80034000，未压缩在 0x80027000，选项字节记着 ROM 加载地址，而 `-t logic` 不更新选项字节。格式或地址和之前不一致就会卡 ROM。工程统一 `logic_compress = true`。
- 改了 `.ve` 就得重跑逻辑生成并重烧位流；只改 C 代码的话 `upload` 就够了。
- DAPLink 返回 `DPIDR = 0x00000000` 说明目标板没上电，先查 J3V 跳线和供电。
- 用户的 Verilog 要写在 `logic/analog_ip.v` 的 module 内部（Quartus 13 按 Verilog-2001 解析）。重新 prelogic 会覆盖 top，但不覆盖 analog_ip.v。
- 给 af.exe 传参要用 .bat 包一层，Git Bash 内联传引号会被打碎。

## 参考

- 目标芯片 AG32VF303KCU6：QFN-32，RISC-V 248MHz + 2K LE CPLD，12-bit ADC
- 官方资料：[tcx-micro.com](http://www.tcx-micro.com/)、[agmsemi.com](http://www.agmsemi.com/)，技术支持 `tech@agmsemi.com`，QQ 群 `379254175`
- 参考项目：[scottbez1/smartknob](https://github.com/scottbez1/smartknob)
