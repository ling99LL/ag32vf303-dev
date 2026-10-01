---
name: ag32-dev
description: AG32/AGRV2K (AGM 遨格芯 RISC-V MCU+CPLD) development assistant. Use when building, flashing, debugging, or configuring AG32 chips (AG32VF303/AG32VF407/AGRV2K), editing .ve pin-mapping files, running PlatformIO AgRV builds, using Supra/AGM DAPLink/OpenOCD flashing, or troubleshooting AG32 upload errors.
---

# AG32 (AGM 遨格芯) 开发助手

本机 AG32 环境已配好并完成流水灯验收。权威细节看 `docs/HANDOVER.md`；本文只放高频操作。

## 环境速查

- PIO CLI: `C:/Users/Administrator/.platformio/penv/Scripts/pio.exe`
- 标准工程: `C:\Users\Administrator\Documents\AG32\projects\ag32vf303_flowled`（流水灯已验收）
- 参考例程（用户提供，勿删）: `Documents\AG32\example\`（agrv2k_407 板）、`Documents\AG32\example_logic_led\`（CPLD LED 例程）
- OpenOCD: `...\.platformio\packages\tool-agrv_openocd\bin\openocd_cmd.bat` + `...\.platformio\platforms\AgRV\etc\agrv2k.cfg`
- SDK 例程库: `...\.platformio\platforms\AgRV\examples\`（18 个）

## 高频命令（工程目录下执行）

```bash
pio="C:/Users/Administrator/.platformio/penv/Scripts/pio.exe"
$pio run -e flow                 # 编译 MCU 固件
$pio run -e flow -t buildlogic   # 编译 LOGIC 位流（Supra 自动，约 5s）
$pio run -e flow -t logic        # 单独烧 LOGIC 位流（改 .ve 后必须）
$pio run -e flow -t upload       # 一键烧录（logic 校验 + 程序 bin）
$pio run -e flow -t monitor      # 串口 printf（COM26@115200）
```

## 硬性规则

1. **logic_device 必须匹配封装**：100 脚 demo 板 = 默认 AGRV2KL100（不写即默认）；**QFN32 KCU6 = AGRV2KQ32**。可选 L48/L64(H)/L100(H)。
2. **必须先有 LOGIC 才能访问 MCU**（调试口也依赖 logic 路由 TAP；空 logic 板子 reset run 卡 ROM，PC≈0x0001xxxx）。
3. **改 .ve → buildlogic + logic + upload；只改 C → upload**。
4. DAPLink 用 `protocol = cmsis-dap-openocd`；目标板供电靠 DAPLink **J3V 跳线**（DPIDR=0 = 没电，先查它和 J4 跳线）。
5. **logic 地址陷阱**：压缩位流在 0x80034000、未压缩在 0x80027000（flash 顶-48K/-100K），选项字节记录 ROM 加载地址；`-t logic` 不更新选项字节，格式/地址与之前不一致会卡 ROM。统一用 `logic_compress = true`。
6. 100 脚 demo 板 LED：GPIO4_1..4 → PIN_34/33/32/31，**低电平点亮（接 VCC 侧，实测确认；GPIO 写 0 = 亮）**。QFN32 可用 pad：1,2,3,5,7-15,18-23,26-29,31；PIN_24/25=JTMS/JTCK 不可挪用。**QFN32 JTAG 家族坑（实测）：AG32VFxxxK 的 pad 26/27/28 = JTDI/JTDO/JNTRST，其中 27（JTDO）被调试 TAP 占用，GPIO/CPLD 输入永远收不到信号**（.ve 映射合法、位流正确也没用，实测霍尔输入死在 27）；26/28 实测可作输入。信号线优先用纯 IO pad 18/19/29/31。SDK 有 `SYS_DisableJTDO()` 等（SYS->SWJ_CNTL，system.h:235，置位=释放该脚给 GPIO）可解，rgb.c 例程有 `SWJ_CNTL = JTDI|JTDO|NJTRST` 用法。
7. 工程路径纯英文；COM 口随 USB 口漂移。

## VE 语法

```
SYSCLK 200 / HSECLK 8
GPIO4_1   PIN_34          # MCU功能 → 引脚
LED_D3    PIN_23:OUTPUT   # CPLD信号 → 引脚
UART1_UARTTXD txd_chn     # MCU功能 → CPLD内部信号
```
用户逻辑写 analog_ip.v / 自定义 ip，top 的 *_board.v 由 VE 自动生成勿手改。

## 无串口调试技巧（JTAG 直读）

固件把结果写到 SRAM 固定地址（如 0x20008000，避开 BSS/栈），然后：
```bash
openocd_cmd.bat -s <.../platforms/AgRV/etc> -c "variable ADAPTER_SPEED 10000" \
  -c "variable ADAPTER cmsis-dap" -f agrv2k.cfg \
  -c "init; halt; mem2array x 32 0x20008000 8; echo \"V=\$x(0)\"; shutdown"
```
要点：必须先 `halt`；用 `mem2array`+`echo`（`mdw` 在此脚本下可能静默）；GPIO 基址 GPIO0-4 = 0x40014000 + n*0x1000，DATA[0xFF]=base+0x3FC（地址即位掩码），DIR=base+0x400；可 halt 后 `mww` 直接驱动引脚验证硬件。

## 排障速查

| 错误 | 处理 |
|---|---|
| DPIDR=0x00000000 / cannot read DP | 目标没电或线不通：J3V 跳线、排线、板电源 |
| reset run 卡 ROM（PC=0x0001xxxx） | logic 位流地址/格式与选项字节不符 → 重烧 `-t logic`（见规则 5）|
| check_device_id 失败 | board/器件配置不符（303 die=0x40200001/256KB）|
| logic 引脚编译错误 | logic_device 与封装不符或 PIN 编号不存在 |
| 找不到 CMSIS-DAP | DAPLink 在 Blaster 模式（J4 连通）或被占用 |

## 关键事实

- 303 die：256KB Flash(0x80000000)/128KB SRAM(0x20000000)，Debug ID 0x40200001，SW-DP 0x2ba01477
- 官方资料：网盘 `pan.baidu.com/s/17bp-zAnsYRuVMRTSSVHN5A`（码 `12ej`）；tcx-micro.com；QQ 群 379254175
- 本地手册：`docs/AGM_DAP_LINK_Rev2.51.pdf`（p.12-13 QFN32 引脚表：PIN_24/25=JTMS/JTCK，PIN_20/21=UART0）

## 纯 CPLD（用户 Verilog）流程

参考 `[env:cpldled]` + `logic/analog_ip.v`（纯硬件流水灯，已验收）。三段式编译，**logic_dir 流程下 buildlogic 不产位流**：

```bash
$pio run -e cpldled -t prelogic                                  # ① 生成 logic/ 工程
cd logic
C:/altera/13.0sp1/quartus/bin64/quartus_sh.exe -t run_quartus.tcl # ② Quartus 综合 → simulation/modelsim/*.vo
cmd /c run_supra.bat                                             # ③ Supra 布局布线 → cpld_board.bin
cd ..
$pio run -e cpldled -t logic && $pio run -e cpldled -t upload    # ④⑤ 烧录
```

规则：用户逻辑写在 `analog_ip.v` **module 内部**（Quartus 13 是 V2001 解析）；VE 里 `LED_D1 PIN_34:OUTPUT` 声明 CPLD 信号，prelogic 自动把端口加进 analog_ip 模板并连到 top；重新 prelogic 覆盖 top 但不覆盖 analog_ip.v，改 VE 端口后要手动合并。传参给 af.exe 用 .bat 文件（Git-Bash 内联引号会碎）。证明纯硬件：OpenOCD halt CPU，LED 继续流。
