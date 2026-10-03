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
├── docs/              硬件接线设计、QFN32 引脚规范、审查交付记录
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

构建验证记录（2026-10-03，v6.1 INL_EN→PIN_28 复测）：固件编译通过（Flash 14.1KB，RAM 3.8KB，含
sincos LUT）；prelogic 0 错 0 警；Quartus 0 errors；Supra 0 errors；`logic/foc2205.bin`
22.4KB（22985 字节，压缩位流，含 PIN_28/22/23 布局，GPIO2_2=PIN_28 网表已核）。

## 项目文档与审查

- [硬件接线设计（docs/DRV8316+MT6701_FOC驱动板接线设计.md）](docs/DRV8316+MT6701_FOC驱动板接线设计.md)（**v6.1**：INL_EN=PIN_28/JNTRST（2 线 DAPLink 零影响）、BOOT1 纯净 10k 下拉、独立 LDO 电源架构、BRK/DO 移至 PIN_22/23）
- [QFN32 芯片引脚评估与分配规范（docs/FOC2205_QFN32芯片引脚评估与分配规范.md）](docs/FOC2205_QFN32芯片引脚评估与分配规范.md)（V3.1：原生定义经 DAPLink 手册逐脚核对，含 INL_EN=PIN_28 复用记录）
- [审查结果交付文档（docs/FOC2205_审查结果交付文档.md）](docs/FOC2205_审查结果交付文档.md)：两轮审查整改交付记录。

> 两轮审查报告（P0/P1/P2 共 10 项、D-1~D-6 共 6 项）与逐条裁定整改记录已于 2026-10-03 移出仓库树，结论均已落地到代码与接线设计；原文可在 git 历史追溯（引入于 29bc30d / 2aa56b1）。

## 上板记录

（待填：位流版本 / 首帧 CRC 结果 / 对齐 zero offset 与 direction / 电流零点 / 手感参数）
