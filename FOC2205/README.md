# FOC2205

基于 **AG32VF303KCU6（QFN32）+ MT6701QT-STD + DRV8316C** 的 2205 电机力反馈旋钮驱动工程。与工作区其他旋钮工程独立。电机按 7 极对数配置。

2026-10-16 完成代码排查、控制层重构和测试文件整理。变更、构建结果及待验证事项见 [本轮排查报告](docs/refactor-audit-2026-10-16.md)。随后完成驱动未供电条件下的烧录与 COM26 联调，修复外设时钟翻倍，详见 [未供电联调记录](docs/unpowered-debug-2026-10-16.md)。此前调参和上板叙述保存在 [历史 README](experiments/notes/README-before-refactor-2026-10-16.md)，历史结果不能代表本轮固件实测。

## 当前实现

2026-10-16 通电调试：修复 SPI 超时误复位后，又定位并修复两处运动缺陷——本片 GPTIMER 的 MOE 1→0 写入会自置 BIF（正常停止被误判为 driver break），以及开环起步把电压矢量放在转子前方 90°（反向起步反抽）。修复后 [基础运动验收](docs/basic-motion-acceptance.md) 的 3/6/15 rpm 正反向各 5 圈六个组合各通过一次。随后用 DRV8316C 自身 SPI 故障（8-clock 帧）产生**真实 nFAULT**，在核心 halted 条件下确认硬件立即清 MOE、置位 `SR.BIF`，固件据此锁存 `driver break` 并可显式恢复（`PIN_22` 未引出排针，故用驱动自故障而非外部拉低）。闭环（位置伺服 `r`/`R`）首轮在 3 rpm 下 10 个单圈动作通过、1 次 `current ADC threshold` 过流跳闸中止；跳闸是真实过流还是采样离群值尚未定性，重复性、6/15 rpm、连续多圈和波形仍未验证。当前实测结果、镜像差异和未解决项见 [通电低速调试记录](docs/powered-debug-2026-10-16.md)。

- 电压调制模式：编码器换向、位置轨迹、混合换向、独立电角度开环、定时 q 轴指令和有超时的手动三相诊断。
- 显式 `foc2205_bringup` 环境开机只做驱动/编码器/ADC 自检，**功率输出关闭、不自动移动转子**。上位机“开始慢速校准”或串口 `a` 才会启动 3% 调制的可取消电角度校准；完成后自动释放输出。`A`/`s` 可取消。默认 `foc2205` 为禁用 CPLD 访问与采样 ISR 的恢复镜像。
- 停止、动作完成、故障均关闭功率输出。故障保持锁存，`z` 检查通过后只回待命，不自动续跑。启动标定失败保留查询通信，需处理原因后重启。
- 三相电流仅为 ADC 遥测；没有电流闭环、软件过流控制、母线电压测量或通信心跳。`vq` 为按 `v_limit_q=8192` 归一化的调制指令，**不能据此宣称实际相电压、力矩或电流已受控**。
- 位置轨迹使用相对起点的 64 位定点累加，位置累计使用 64 位；受阻或超时会故障释放，不把未到位伪装成完成。

## 目录

| 路径 | 用途 |
|---|---|
| `src/` | 启动、控制、运动、串口协议及外设驱动 |
| `logic/` | ADC×3、SPI 桥×2、生成工程、构建包装与位流 |
| `tools/` | 日常上位机、协议模型、串口抓取和复位工具 |
| `experiments/tests/` | 可重复的主机控制回归测试 |
| `experiments/probes/` | 历史 JTAG/烧录/寄存器探测脚本，原样归档 |
| `experiments/logs/` | 本机调参和构建日志，不入 Git |
| `experiments/notes/` | 历史调参叙述、资料文本提取、临时记录 |
| `docs/` | 接线、规格书、验收要求、架构决定及审查报告 |
| `FILE_INDEX.md` | 文件导航 |

## 构建

从本目录运行 PowerShell：

```powershell
$pio = 'C:/Users/Administrator/.platformio/penv/Scripts/pio.exe'
& $pio run -e foc2205 -t prelogic
cmd /c logic\build_steps.bat
cmd /c logic\run_supra.bat
& $pio run -e foc2205 -t buildlogic
& $pio run -e foc2205 -t clean
& $pio run -e foc2205
python experiments/tests/run_tests.py
```

Quartus 13 路径为 `C:/altera/13.0sp1/quartus/bin64`。包装脚本保留硬宏分区扫描及 `PARALLEL_SYNTHESIS OFF`，逐步检查新生成的 summary、三路 ADC 网表和 SHA256；已知 `0xC0000409` 退出只有在新报告验证通过时才允许继续。Supra 校验输入哈希并要求新位流及零错误摘要。`buildlogic` 在自定义 `logic_dir` 流程中只是已有位流的依赖别名，本轮输出为 up to date；它不执行独立 CRC 校验，也不能代替 Quartus/Supra。

仅修改 C 时不需要重建 CPLD。2026-10-16 已实际烧录 logic 和固件并通过字节校验。后续上板时，logic 与固件分别用 `-t logic`、`-t upload`，完成后按实际探针连接复位运行。压缩位流保持 `logic_compress=true`，QFN32 器件保持 `AGRV2KQ32`。工具路径和串口号按本机环境核对。

### 串口烧录恢复路径

当芯片已经进入 ROM UART loader 时，可绕过 OpenOCD 通过 COM26 烧录 MCU 固件：

```powershell
$env:AGM_PIO_UPLOAD_PROTOCOL = 'serial'
& $pio run -e foc2205 -t upload -p COM26
```

该路径会调用 SDK 的 `agrv32flash`，执行设备识别、擦除、写入和校验。2026-10-16 实测 `COM26 @460800 8E1` 成功，识别 `0x40200001`，固件校验通过并自动复位。日志中的 `Checking logic configuration at 0x80034000` 只校验已有 CPLD 位流，不会重写 CPLD；CPLD 仍需单独使用 `-t logic` 或生产 batch 烧录。复位后安全镜像报告 `stage=90`、`out=0`，没有启动校准或电机动作。

## 串口控制

UART0，115200 8N1；引脚 PIN_20=TX、PIN_21=RX。`python tools/foc_panel.py` 打开协议 v2 面板，需要 `pyserial` 和 `tkinter`。面板要求 `proto=2,diag=1` 诊断扩展，需配套固件。新增就绪门控、故障原因、数据有效性、2 秒通信超时、CSV 自动记录与导出；手动不自动保活。日志采集和断言优先使用串口脚本；窗口操作仅用于必要的界面验收。

| 命令 | 行为 |
|---|---|
| `?` / `h` / `d` / `f` | 状态帧 / 帮助 / 配置 / 驱动故障寄存器 |
| `s`、空格、`g`、`n` | 停止并关闭功率输出；不清除故障 |
| `z` | 检查驱动、16 帧编码器 CRC、ADC 零点和 BRK 后请求恢复至待命 |
| `a` / `A` | 手动开始 / 取消慢速电机校准；开机不会自动校准 |
| `r` / `R` | 正/反向位置轨迹 1 圈 |
| `o` / `O` | 正/反向开环电矢量推进 1 圈时长 |
| `b` / `B` | 正/反向开环电矢量推进 5 圈时长；实际机械圈数必须另行核验 |
| `t` / `T` | 正/负 q 轴调制指令，3 秒后释放 |
| `m`、`x0`…`x7` | 进入中性手动模式，再选择 A/B/C 掩码 |
| `w1`…`w4` | 手动占空比差 5/10/15/20%；30 秒无有效手动操作自动释放 |
| `+` / `-` | 调制上限按比例调节，封顶 20% 参考值 |
| `v` | 速度档 0.02/0.05/0.10/0.25/0.50 圈/秒 |
| `k/i/j/c/q/y/e/u` | 位置增益、积分、阻尼、跟随带、角度滤波、混合换向、滑差死区、测速窗口 |

状态帧以 `#FOC,proto=2,` 开头。`st=0/1/3/4` 分别为待命/运行/故障/完成；`2` 保留，当前没有主动 HOLD 模式。`ia/ib/ic` 单位为 ADC LSB，只有 `cal=1` 时表示已减标定零点；`cal=0` 为未标定原始值。`encok/adcok` 标记当前采样有效性，`drvok/aligned/ready` 表示驱动与运动条件，`fault/stage/out/brk` 提供故障、启动阶段和使能诊断。当前是诊断字符协议，ADR 中的完整宿主协议和心跳目标尚未实现。

## 引脚与证据边界

SPI0/1 均为 3.125MHz；DRV 桥 DEPTH32，MT 桥 DEPTH12、下降沿采样。MCU PCLK 显式分频至 100MHz；VE BUSCLK 与其独立。PWM 配置 20kHz，更新 IRQ 按谷底门控，本板 mcycle 实测约20,008Hz；固件以该频率用于计时。

PIN_28 为 INL_ALL，同时是 JNTRST；固件仅释放 NJTRST。若探针电缆把 nTRST 拉低，通电驱动时可能冲突，空闲拉低不能消除运动期间的布线冲突。PIN_24/25 保持调试用途，26/27 留空，BOOT1/PIN_15 保持启动下拉。

本轮已完成 MCU 编译、Quartus/Supra 构建、位流烧录校验，验证了通电条件下的 DRV 配置读回、编码器 CRC，完成 [基础运动验收矩阵](docs/basic-motion-acceptance.md) 六个组合各一次通过（编码器累计角度单调、无失步、停止无 BRK），并验证 nFAULT 硬件断路通道（真实故障 → 硬件清 MOE/置 BIF → 固件 driver break → 显式恢复）。真实相电流及功率波形未测量，重复性验收与闭环待做；烧录后偶发的首次 CPLD 访问卡死仍未定位。
