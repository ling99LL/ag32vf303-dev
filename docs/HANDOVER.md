# AG32 开发环境交接文档

> 生成日期：2026-09-27 ｜ 环境：Windows 10 (10.0.22631) x64
> 适用芯片：AG32 系列（AGM 遨格芯 RISC-V MCU + 2K LE CPLD）
> 当前开发板：**AGM 100 脚 demo 板**（agrv2k_303 级芯片，LQFP100 封装，L100 逻辑器件）
> 目标芯片：AG32VF303KCU6（QFN-32）—— 同系列die，换封装时注意 §3.2 的器件名
> 工作区：`C:\Users\Administrator\Documents\AG32`
>
> **✅ 验收已完成：4 路 LED 流水灯已烧录并在板上运行**（`pio run -e flow -t upload` 即可复现）

---

## 1. 环境总览

### 1.1 芯片要点

| 项目 | 参数 |
|---|---|
| 内核 | RISC-V (RV32IMAFC，ilp32f)，SDK 默认 200MHz（板级 f_cpu，实测系列可到 248MHz+） |
| Flash / RAM | 256KB Flash（0x80000000 起始）/ 128KB SRAM（0x20000000） |
| 内置逻辑 | 2K LE CPLD（约 2112 LUT），与 MCU 通过 AHB 互联 |
| 模拟 | 12bit ADC、10bit DAC（位于 logic 的 analog_ip） |
| Debug ID | 0x40200001（SW-DP ID 0x2ba01477） |

### 1.2 软件组成与安装路径

| 组件 | 版本 | 路径 | 说明 |
|---|---|---|---|
| AGM SDK（AgRV_pio） | **1.8.10** | `C:\Users\Administrator\AgRV_pio` | 安装源（RAR 自解压 + setup.py）|
| PlatformIO Core | 6.2.0 | `C:\Users\Administrator\.platformio\penv\Scripts\pio.exe` | |
| AgRV 平台 | 1.8.10 | `C:\Users\Administrator\.platformio\platforms\AgRV` | boards/builder/etc/examples |
| RISC-V 工具链 | toolchain-agrv | `...\.platformio\packages\toolchain-agrv` | |
| Supra（logic 编译） | 随 SDK | `...\.platformio\packages\tool-agrv_logic\bin\Supra.exe` | 含 yosys |
| OpenOCD | AGM 定制版 | `...\.platformio\packages\tool-agrv_openocd\bin\openocd_cmd.bat` | 配 `agrv2k.cfg` |
| Downloader.exe | 随 SDK | `...\.platformio\packages\tool-agrv_logic\bin\Downloader.exe` | 串口/离线烧录 |
| VSCode + PlatformIO IDE | 1.102.1 / 3.3.4 | — | |
| Quartus II | 13.0sp1 64-bit | `C:\altera\13.0sp1` | 已有；日常流程用不到 |
| Python | 3.11.9 | — | 要求 ≥3.10 |

> 注意：`AgRV_pio`（安装源）与 `.platformio`（实际使用）内容重复。用户目录路径不能含中文。

### 1.3 硬件

| 设备 | 状态 |
|---|---|
| AGM 官方 DAP LINK（CMSIS-DAP v2，VID:PID=0xcafe:0x1001）| Win10 免驱；枚举为 `CMSIS-DAP v2` + `USB 串行设备 (COM26)` |
| AGM 100 脚 demo 板 | DAPLink 排线连接，由 DAPLink 供电 |

DAP LINK 模式（手册 Rev2.51）：**CMSIS-DAP 模式**（J4 跳线断开，D4 快闪 D3 常亮）= 本项目所用；USB Blaster 兼容模式（J4 连通）给 Altera 类器件；另有离线烧录模式。
**供电链**：目标板电源来自排线 VCC3V3 → **DAPLink 上 J3V 跳线必须连通**（本次调试曾因目标无电 DPIDR=0x00000000 卡住，接通后一切正常）。
**QFN32 接线**（将来换 KCU6 目标板用）：DAPLink JTAG 口的 TCK、TMS、GND、VCC3V3 四根线 → 芯片 PIN_25(JTCK)、PIN_24(JTMS)、GND、VDD（手册 p.12）。

### 1.4 100 脚 demo 板关键引脚（本次验证）

| 功能 | VE 写法 | 说明 |
|---|---|---|
| **4 个 LED**（**低电平点亮**，接 VCC 侧）| `GPIO4_1 PIN_34` / `GPIO4_2 PIN_33` / `GPIO4_3 PIN_32` / `GPIO4_4 PIN_31` | 来自官方例程 example_board.ve |
| UART0 调试口 | `UART0_UARTRXD PIN_69` / `UART0_UARTTXD PIN_68` | 是否通到 DAPLink 串口取决于用户接线 |
| 主晶振 | HSECLK 8（PIN_2/3 区域，die pad 级） | 8MHz 已验证起振 |
| RTC 晶振 | die pad PIN_1 | 32.768kHz（扫描观测到振荡）|

**QFN32（AGRV2KQ32，将来用）速查**：可作 IO 的 pad：1,2,3,5,7-15,18-23,26-29,31；PIN_24=JTMS、PIN_25=JTCK（调试口，不可挪用）；PIN_4=NRST；PIN_30=BOOT0；PIN_20/21=UART0 建议保留。完整表见 `docs/AGM_DAP_LINK_Rev2.51.pdf` p.12-13。

---

## 2. 环境重现步骤（换机可复现）

1. 安装 VSCode、Python ≥3.10
2. 百度网盘下载 SDK：`https://pan.baidu.com/s/17bp-zAnsYRuVMRTSSVHN5A` 提取码 `12ej`（选最新 `AgRV_pio-x.x.x-win64-release.exe`）
3. 静默安装：`AgRV_pio-1.8.10-win64-release.exe -s`（自动完成 `.platformio` 部署；完成后可能残留 python 进程跑 pip，无碍）
4. `code --install-extension platformio.platformio-ide`
5. 验证：`pio --version` → 6.2.0；插 DAPLink 看设备管理器

---

## 3. 日常开发流程

### 3.1 标准工程结构

```
projects/ag32vf303_flowled/
├── platformio.ini      # 唯一配置文件
├── nano_board.ve       # 引脚映射（当前：LED×4 + UART0）
├── src/flow_main.c     # 4 路流水灯固件（已验收）
└── .pio/
    ├── build/flow/led_flow.bin    # MCU 程序
    └── logic/nano_board.bin       # LOGIC 压缩位流（Supra 自动生成，~3.5KB）
```

### 3.2 platformio.ini 关键配置

```ini
[setup]
board = agrv2k_303             # 303 级 die（256KB flash / device id 0x40200001）
[setup_logic]
logic_ve = nano_board.ve
# ★ 100 脚 demo 板：不写 logic_device（默认 AGRV2KL100）
# ★ QFN32 KCU6 目标板：必须 logic_device = AGRV2KQ32
logic_compress = true          # 压缩位流落在 0x80034000（与芯片选项字节一致）
[setup_upload]
protocol = cmsis-dap-openocd   # AGM DAPLink
[setup_monitor]
monitor_port = COM26           # 换 USB 口会变
```

**器件名规则**（`logic_device`）：`AGRV2KL100(H)`=LQFP100 / `AGRV2KL64(H)`=LQFP64 / `AGRV2KL48`=LQFP48 / `AGRV2KQ32`=QFN32。选错会报引脚不存在或管脚功能异常。

### 3.3 构建 / 烧录 / 监控（工程目录执行）

```bash
PIO="C:/Users/Administrator/.platformio/penv/Scripts/pio.exe"

$PIO run -e flow                 # 编译 MCU 固件
$PIO run -e flow -t buildlogic   # 编译 LOGIC 位流（Supra 自动，约 5 秒）
$PIO run -e flow -t logic        # ★ 单独烧 LOGIC 位流（改了 .ve 后执行）
$PIO run -e flow -t upload       # ★ 一键烧录（logic 校验 + MCU bin）
$PIO run -e flow -t monitor      # 串口 printf
```

- **AG32 必须先有 LOGIC 才能访问 MCU**（SWD/JTAG 调试口也依赖 logic 把调试 TAP 路由到引脚——空 logic 的板子 `reset run` 会卡在 ROM，PC=0x0001xxxx）
- 改 `.ve` → `buildlogic` + `logic` + `upload`；只改 C → `upload`
- VSCode PlatformIO 图形按钮等价

**⚠️ logic 地址陷阱（本次踩过）**：压缩位流在 flash 顶部 -48KB = `0x80034000`，未压缩在 -100KB = `0x80027000`。芯片选项字节（0x81000030 的 FPGA_CONFIG_ADDR）记录了 ROM 该去哪加载 logic。**用 `-t logic` 烧位流不会改写选项字节**——如果之前板上位流的格式/地址与现在不同，ROM 会加载到垃圾并卡死。对策：统一用 `logic_compress = true`（与出厂一致）。

### 3.4 VE 引脚映射语法

```
SYSCLK 200                # 主频（须与板级 f_cpu 一致）
HSECLK 8                  # 外部晶振
GPIO4_1   PIN_34          # MCU功能 → 引脚
LED_D3    PIN_23:OUTPUT   # CPLD信号 → 引脚（OUTPUT/INPUT/INOUT，缺省INOUT）
UART1_UARTTXD txd_chn     # MCU功能 → CPLD内部信号
@ FAST_OUTREG:ON:PIN_23   # 电气属性（1.3.0+）
```

改 VE 后 Prepare 会生成 `*_tmpl.v`（不覆盖用户逻辑），top `*_board.v` 会被覆盖——用户逻辑写在 analog_ip.v / 自定义 ip，别写在 top。

### 3.5 调试与"无串口"调试技巧（本次实战沉淀）

- VSCode F5 / `pio debug`：cortex-debug + OpenOCD，断点默认 main
- **串口没接线时，用 SRAM 传数据**：固件把结果写到固定地址（如 `0x20008000`，避开 BSS/栈），然后：
  ```bash
  openocd_cmd.bat -s <platforms/AgRV/etc> -c "variable ADAPTER_SPEED 10000" \
    -c "variable ADAPTER cmsis-dap" -f agrv2k.cfg \
    -c "init; halt; mem2array x 32 0x20008000 8; echo \"V=\$x(0)\"; shutdown"
  ```
  注意：`mem2array`+`echo` 才有输出；`mdw` 在此包装脚本下可能静默无输出；读运行态目标必须先 `halt`。
- **不烧录直接驱动引脚**：halt 后 `mww 0x40014400 0xFF`（GPIO0 DIR）、`mww 0x400143FC 0xFF`（DATA[0xFF]=全 1）可手工点亮引脚验证硬件。GPIO 基址：GPIO0=0x40014000、GPIO1=0x40015000、GPIO2=0x40016000、GPIO3=0x40017000、**GPIO4=0x40018000**；DATA[0xFF]=base+0x3FC，DIR=base+0x400
- FCB 可在运行时改引脚上下拉/驱动强度（`FCB_ReadIOConfig`→`FCB_SetPinConfig`→`FCB_WriteIOConfig`），但本次实测**上下拉配置对读数无预期效果**（疑似需 FCB_ACTIVATE 或仅复位生效），勿依赖

---

## 4. 流水灯实现（已验收 ✅）

- **引脚**：GPIO4_1..GPIO4_4 → PIN_34/33/32/31，**低电平点亮**（接 VCC 侧，实测确认）
- **实现**：`src/flow_main.c`，200ms/步循环点亮（单灯移动式流水）
- **验证**：烧录后 JTAG 采样 GPIO4 输出寄存器，读到 0x2→0x8→0x4→0x10 循环（即 LED1→LED3→LED2→LED4 依序点亮），板上流水灯运行中
- 复现：`pio run -e flow -t upload` 后自动复位运行

---

## 5. 排障速查

| 现象 | 原因与处理 |
|---|---|
| DPIDR=0x00000000 / `cannot read DPR` | 目标没电或 JTAG 线不通：查 **J3V 跳线**（排线供电）、排线方向、板上电源 |
| `reset run` 后卡死（PC=0x0001xxxx 在 ROM） | logic 位流地址/格式与选项字节不符（见 §3.3 陷阱）；或 logic 为空。重烧 `-t logic` |
| `check_device_id` 失败 | 器件 id/flash 大小不符：303 级 die=0x40200001+256KB；确认 board 选择 |
| logic 编译报引脚不存在 | `logic_device` 与封装不符，或 VE 用了不存在的 PIN 编号 |
| 找不到 CMSIS-DAP | DAPLink 进了 Blaster 模式（J4 连通）或被占用；拔插 USB |
| COM26 打不开 | 串口号随 USB 口漂移，设备管理器确认后更新 platformio.ini |
| 烧完没反应 | 先确认两个 bin 都烧了（logic + 程序）；BOOT0 电平 |
| 中文路径报错 | SDK/PIO 不支持中文路径 |

---

## 6. 官方资料索引

| 资料 | 位置 |
|---|---|
| SDK 百度网盘 | `pan.baidu.com/s/17bp-zAnsYRuVMRTSSVHN5A` 提取码 `12ej` |
| 官网 | tcx-micro.com（资料站，有反爬）/ agmsemi.com / agm-micro.com / ag32mcu.com |
| 代理商 | hizyuan.com（海振远，DAPLink 制造商）|
| 官方技术群 | QQ 群 379254175；tech@agmsemi.com |
| 本地文档 | `docs/AGM_DAP_LINK_Rev2.51.pdf`（p.12-13 QFN32 引脚表）、`docs/AG32_IDE开发环境搭建.pdf`、`docs/AG32_MCU产品概览.pdf` |
| **用户提供的官方例程** | `C:\Users\Administrator\Documents\AG32\example\`（agrv2k_407 板 + analog_ip 综合例程）、`C:\Users\Administrator\Documents\AG32\example_logic_led\`（CPLD LED 例程：LED_D2/D3 → PIN_31/32）|
| SDK 内例程 | `.platformio\platforms\AgRV\examples\`（18 个）|

---

## 7. 工作区交付物

| 文件 | 说明 |
|---|---|
| `projects/ag32vf303_flowled/` | 标准工程（流水灯已验收）|
| `docs/HANDOVER.md` | 本文档 |
| `docs/*.pdf` | 官方手册归档 |
| `.zcode/skills/ag32-dev/SKILL.md` | ZCode 项目级 skill |
| `example/`、`example_logic_led/` | 用户提供的 AGM 官方参考例程（保留勿删）|

## 8. 待办 / 后续

- [ ] 换 QFN32 KCU6 自研板时：`logic_device = AGRV2KQ32` + 重写 VE（§1.4 QFN32 pad 表）+ 重新 `buildlogic`/`logic`/`upload`
- [ ] 如需 MCU+CPLD 联合开发（自定义逻辑），参考 `example_logic_led`（logic 目录含完整 Supra/Quartus Tcl 流程）和官网《联合编程教程》
- [ ] 需要串口日志时：确认 UART0（PIN_68/69）到 DAPLink 串口的实际接线

---

## 9. 纯 CPLD 流水灯实现（✅ 已烧录运行）

第二种实现：流水节拍完全由 CPLD 用户 Verilog 产生，MCU 只跑空循环（甚至 halt CPU 灯照常流）。

### 9.1 环境与文件

| 文件 | 说明 |
|---|---|
| `platformio.ini [env:cpldled]` | `logic_ve = cpld_board.ve`、`ip_name = analog_ip`、`logic_dir = logic`、`program = cpld_flow` |
| `cpld_board.ve` | LED 以 **CPLD 信号**声明：`LED_D1 PIN_34:OUTPUT` … `LED_D4 PIN_31:OUTPUT`（不映射任何 MCU 功能）|
| `logic/analog_ip.v` | 用户硬件逻辑（见 §9.2）|
| `logic/cpld_board.v` | prelogic 自动生成的 top（把 analog_ip 实例和 pad 连起来，勿手改）|
| `src/min_main.c` | 最小 MCU 宿主（board_init + 空循环），不碰任何 LED |

### 9.2 用户 Verilog（logic/analog_ip.v 模块体内）

```verilog
reg [31:0] flow_cnt;
reg [3:0]  flow_pos;
always @(posedge sys_clock) begin        // sys_clock = 200MHz
  if (!resetn)              { flow_cnt, flow_pos } <= {32'd0, 4'b0001};
  else if (flow_cnt == 32'd66999999) begin // 67M cycles ≈ 335ms
    flow_cnt <= 32'd0;
    flow_pos <= {flow_pos[2:0], flow_pos[3]};  // one-hot 循环移位
  end else flow_cnt <= flow_cnt + 32'd1;
end
assign LED_D1 = flow_pos[0];  // …D2/D3/D4 同理
```

### 9.3 编译流水线（自定义逻辑 = prelogic + Quartus + Supra 三段式）

```bash
PIO="C:/Users/Administrator/.platformio/penv/Scripts/pio.exe"
$PIO run -e cpldled -t prelogic      # ① 生成 logic/ 工程（top + qsf + af_*.tcl）
cd logic
# ② Quartus 综合（Cyclone IV E 代理目标）→ simulation/modelsim/cpld_board.vo
C:/altera/13.0sp1/quartus/bin64/quartus_sh.exe -t run_quartus.tcl
# ③ Supra 布局布线 + 出压缩位流 → logic/cpld_board.bin
cmd /c run_supra.bat
cd ..
$PIO run -e cpldled -t logic         # ④ 烧位流（0x80034000）
$PIO run -e cpldled -t upload        # ⑤ 烧最小 MCU 宿主
```

`run_quartus.tcl`/`run_supra.bat` 是本工程自带的无头编译脚本（见下）。**不推荐 GUI 手动跑**：官方 af_quartus.tcl 里的 af_ip.tcl（分区提示脚本）在无头模式会因未打开工程而报错，但那些 assignment 只是优化提示、非功能必需，故 run_quartus.tcl 绕过了它。

```tcl
# logic/run_quartus.tcl（已存在）
load_package flow
project_open cpld_board
execute_flow -compile
```
```bat
rem logic/run_supra.bat（已存在）——参数必须照官方日志原样传
af.exe --batch -X "set QUARTUS_SDC true" -X "set FITTING Auto" -X "set FITTER full" ^
  -X "set EFFORT high" -X "set HOLDX default" -X "set SKEW basic" ^
  -X "set MODE QUARTUS" -X "set FLOW ALL" -F ./af_run.tcl
```

### 9.4 证明"与软件无关"的方法

JTAG 暂停 MCU 后 LED 继续流水（节拍来自 fabric 内的计数器，PLL 时钟独立于 CPU）：

```bash
openocd_cmd.bat -s <etc> -c "variable ADAPTER_SPEED 10000" -c "variable ADAPTER cmsis-dap"   -f agrv2k.cfg -c "init; halt; shutdown"     # CPU 停止，灯继续流
```

改流水速度/花样：只改 `logic/analog_ip.v`（如改 `66999999` 或把 one-hot 移位换成约翰逊计数器）→ 重复 §9.3 的 ②③④⑤。**不需要重新编译 MCU 固件。**

### 9.5 踩坑记录

- `pio run -t buildlogic` 在 logic_dir 流程下**不生成位流**（它只把已有 bin 当输入）——自定义逻辑必须走 §9.3 的手动三段式
- 用户逻辑必须写在 `analog_ip.v` 的 **module 内部**（Quartus 13 是 Verilog-2001 解析，module 外声明寄存器报 SystemVerilog 错误）
- 传参给 af.exe 时**不要经 Git-Bash 的 cmd //c 内联引号**（会碎成空词导致 MODE 回落 QUARTUS 且参数丢失），用 .bat 包装文件
- prelogic 重新生成时 top（cpld_board.v）会被覆盖，但 analog_ip.v 不会（生成器跳过已有文件）——改 VE 端口后需手动把新端口合并进 analog_ip.v
