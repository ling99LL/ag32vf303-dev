# FOC2205

AG32VF303KCU6 (QFN32) + MT6701QT-STD + DRV8316C 三芯片 FOC 驱动板 —— 力反馈旋钮（2205 电机）。

**完全独立工程**，与 `foc\foc_knob` 零交叉（不包含、不引用其任何文件）。

| 项 | 值 |
|---|---|
| MCU | AG32VF303KCU6，QFN32，`logic_device = AGRV2KQ32` |
| 磁编码器 | MT6701QT-STD，SSI 24clk @12.5MHz（1.92µs/帧），CRC6 每帧校验，Mg[2]=按压 |
| 电机驱动 | DRV8316CRRGFR，3x PWM 模式，SPI 配置 @6.25MHz，三电阻电流采样 |
| 控制环 | GPTIMER0 中心对齐 20kHz，更新中断里准同时采电流+读角度 |
| 调试串口 | UART0 @115200（PIN_20=TX / PIN_21=RX，不占 15 个可分配脚） |

## 目录

```
FOC2205/
├── platformio.ini     构建配置（foc2205 env）
├── foc2205.ve         引脚映射（改它必须 buildlogic + logic + upload）
├── docs/              硬件接线设计文档
├── logic/             CPLD 逻辑：analog_ip（ADC×3）+ spi_mode_wrap（mode-1 桥×2）
└── src/               固件：board / pwm3ph / drv8316 / mt6701 / current / foc / main
```

## 构建（全部实测通过）

```bash
pio="C:/Users/Administrator/.platformio/penv/Scripts/pio.exe"
$pio run -e foc2205                 # 编译固件
$pio run -e foc2205 -t prelogic     # 生成 logic 工程（改 .ve 后必跑）
cd logic
cmd //c "C:\altera\13.0sp1\quartus\bin64\quartus_sh.exe -t af_quartus.tcl"   # Quartus 综合
cmd //c "C:\Users\Administrator\.platformio\packages\tool-agrv_logic\bin\af_cmd.bat -f af_run.tcl"  # Supra P&R -> foc2205.bin
cd ..
$pio run -e foc2205 -t buildlogic   # 位流校验
$pio run -e foc2205 -t logic        # 烧 logic 位流（接板后）
$pio run -e foc2205 -t upload       # 烧固件（自动校验 logic）
$pio run -e foc2205 -t monitor      # 串口 printf (COM@115200)
```

构建验证记录（2026-10-02）：固件 2.83s 编译通过（Flash 12.9KB）；prelogic 0 错 0 警；
Quartus 0 errors；Supra 0 errors（setup slack +1.03ns @5ns 约束，hold 全正，覆盖 99.3%）；
`logic/foc2205.bin` 22.6KB（压缩位流）。


## 项目文档与审查

- [硬件接线设计（docs/DRV8316+MT6701_FOC驱动板接线设计.md）](docs/DRV8316+MT6701_FOC驱动板接线设计.md)（**v4 审查整改版**：新增 PIN_15=INL_EN、独立 LDO 电源架构、MT6701 改挂 3.3V 主轨）
- [项目审查与风险排查报告（docs/FOC2205_项目审查与风险排查报告.md）](docs/FOC2205_项目审查与风险排查报告.md)：详列 P0/P1/P2 共 10 项软硬件隐患及修复指南。
- [审查问题解决方案与整改记录（docs/FOC2205_审查问题解决方案与整改记录.md）](docs/FOC2205_审查问题解决方案与整改记录.md)：逐条裁定（含对报告 4 处修法的修正）+ 规格书页码证据 + 落地状态。

## 上板记录

（待填：位流版本 / 首帧 CRC 结果 / 对齐 zero offset 与 direction / 电流零点 / 手感参数）

## 上板记录

（待填：位流版本 / 首帧 CRC 结果 / 电流零点 / 手感参数）
