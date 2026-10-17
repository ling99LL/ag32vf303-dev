# FOC2205 文件导航

更新：2026-10-18（在 m0–m4 与闭环速度 PI 基础上新增连续 rpm 滑块、三相电流高频显示、立即急停和上位机滚动布局）。工作区总索引见根目录 `INDEX.md`。硬件和功能入口见 README；最新闭环结论见 `docs/closed-loop-velocity-2026-10-17.md` 与 `docs/foc2205-fw-20261017.25-release.md`，重构与复查证据见 `docs/refactor-audit-2026-10-16.md`、`docs/code-audit-2026-10-16.md`，历史平滑与通电记录见 `docs/smoothness-2026-10-17.md` 与 `docs/powered-debug-2026-10-17.md`。历史调参快照在 `experiments/notes/`，不用于判断当前功能。

| 文件或目录 | 用途 |
|---|---|
| `platformio.ini`、`foc2205.ve` | PIO 环境（bringup 调试镜像含 25% 力度上限 flag）、QFN32 器件、压缩格式和引脚分配 |
| `src/main.c` | 上电自检、对齐、ISR 注册、主循环及结果上报 |
| `src/console.c/h` | UART 命令（兼容旧单字符、m0–m4、`rpm <3-60>`、`estop` 与 `vp/vi/vff/vfr` 参数行）、高频 `$T` 遥测（含三相电流）、v3 状态帧 |
| `src/control.c/h` | ISR 故障检测、驱动状态轮询和显式恢复检查 |
| `src/control_lock.h` | 保存/恢复 RISC-V 全局中断状态的短临界区 |
| `src/motion.c/h` | 动作状态机、定点位置轨迹、闭环 SPIN 速度 PI + 同步换向前馈、开环换向、手动/SPIN/手感看门狗 |
| `src/foc.c/h` | 电压模式调制（逆 Park/Clarke→SVPWM）、编码器有效帧缓存、环形零偏标定；电流仅用于跳闸与遥测 |
| `src/calibration.c/h` | 电角度零偏校准状态机（3% 调制扫角，stage 0–9，可取消） |
| `src/current.c/h` | 三 ADC 启动、截止等待、零点校准及遥测 |
| `src/drv8316.c/h` | DRV8316 SPI 帧、寄存器配置及故障清除 |
| `src/mt6701.c/h` | MT6701 SSI 帧、CRC6 和桥完成检查 |
| `src/pwm3ph.c/h` | PWM/谷底 ISR、BRK、统一输出使能与释放 |
| `src/app_io.c/h` | GPIO/SPI 初始化、限时单相 SPI 传输、延时 |
| `src/analog_ip.h` | CPLD ADC 与外设寄存器定义 |
| `src/build_config.h` | 构建期安全门：默认镜像禁止访问 0x6000xxxx CPLD 窗口 |
| `src/haptic.c/h` | m0 自由 / m1 阻尼 / m2 惯性 / m3 原生连续角挡位 / m4 有界回拉，统一 Q12 力矩算法与状态 |
| `logic/analog_ip.v` | 三 ADC 硬宏、AHB/APB 外设和 SPI 桥实例 |
| `logic/spi_mode_wrap.v` | SPI 重定时、接收锁存、APB 状态 |
| `logic/ahb2apb.v`、`logic/reg_ctrl.v` | SDK 总线与寄存器桥 |
| `logic/build_steps.bat/ps1` | Quartus 分步构建，新报告/硬宏/时序校验 |
| `logic/run_supra.bat/ps1`、`logic/build_helpers.ps1` | 输入哈希校验、原生命令日志、Supra 布局布线 |
| `logic/foc2205.v`、`*.qsf/qpf/sdc/vex/asf`、`af_*.tcl`、`analog_ip_tmpl.v` | prelogic/工具生成文件；顶层勿手改 |
| `logic/foc2205.bin/inc`、`foc2205_batch.bin`、`foc2205_routed.v` | 本轮生成的位流、C 数组、批量包和布线网表 |
| `logic/quartus_validated.json`、`quartus_logs/`、`alta_db/`、`*.log` | 本地构建证据与数据库，忽略入库 |
| `tools/foc_panel.py`、`run_foc_panel.bat` | 协议 v3 完整调试台：设备/动作/SPIN/手动/手感页；3–60 rpm 连续滑块、3/6/15/60 快捷键、A/B/C 电流显示、全宽急停、闭环速度环参数、100 Hz 实时曲线与独立 CSV |
| `tools/foc_protocol.py` | 协议 v3 状态、速度环字段、12/13/17 字段紧凑 `$T` 遥测解析（含 `ia/ib/ic/adcok`）与面板状态模型，供上位机与测试共用（无串口 I/O） |
| `tools/uart_console.py`、`uart_capture.py` | 字符命令与串口记录 |
| `tools/reset_run.bat`、`soft_reset.bat` | DAPLink 运行和软件复位 |
| `tools/probe_state.bat` | 内核无法 halt 时绕过 examine 直读 DMI（dmstatus/sbcs），判定 AHB 总线挂起 |
| `tools/uart_flash_probe.bat`、`uart_flash_all.bat` | UART ISP：BOOT0=3V3+断电重启后探测 / 全量重烧（先 logic 后程序） |
| `experiments/tests/run_tests.py`、`control_regression.c`、`stubs/` | 主机回归入口：GCC 编译实际控制源码+硬件桩，覆盖闭环速度 PI、m0–m4、看门狗、协议与 Python 语法 |
| `experiments/tests/test_panel_protocol.py` | 协议 v3、速度环字段、`cl/open` 强类型、手感状态门控、`$T` 错帧与操作条件单元测试 |
| `experiments/tests/gui_spin_smoke.py`、`gui_position_smoke.py` | 隐藏 Tk 实连 COM26：闭环 SPIN 6→12 rpm 连续改速、三相电流显示、`estop` 释放时延，以及 `rot ±360` 面板按钮端到端验收 |
| `experiments/tests/haptic/` | m0–m4 自动验收：`haptic_mode_probe.py`、`haptic_wall_probe.py`、串口/指标公共模块；输出 summary JSON、逐例 CSV 和串口日志 |
| `experiments/tests/hardware_unpowered.py` | 实板负向测试：驱动未供电时验证故障上报与命令拒绝 |
| `experiments/tests/ahb2apb_tb.v` | AHB2APB 桥 Verilog 测试台 |
| `experiments/tests/accept_openloop.py` | 开环验收运行器：绝对设定调制/速度档，跑 5 圈并逐帧展开编码器机械角 |
| `experiments/tests/nfault/` | nFAULT/硬件断路验证：DRV 自故障注入、halt 冻结确认、全流程脚本与说明 |
| `experiments/tests/calibrate.py` | 校准运行器：`s`→`a`→轮询 `calst=7/9`，兼作校准链路看门狗喂狗 |
| `experiments/tests/accept_closedloop.py` | 闭环验收运行器：连发 N 个单圈位置伺服，逐圈报告位移/误差/调制/反向步进/glitch |
| `experiments/tests/spin/` | 无限旋转验收：`accept_spin.py` 跑开/闭环速度×力度×方向矩阵并验证 3.5 s 失联释放；`capture_spin.py` 支持开/闭环、速度环参数注入、20 Hz 稳态遥测/FFT；`wait_and_run.py` 与 `flash_then_auto.py` 负责冷启动/烧录接续 |
| `experiments/tests/current_loop/` | 电流环/过流取证：`accept_current_loop.py`（A/B 段）、`snap_walk2.py`+`walk_one.py`（坏窗口定位）、`set_preset.py`/`prep_ED.py`（配置对齐）、`run_window_move.py`（单步 E/D 取证）、`final_state.py`（收尾）；平滑扫描：`smoothness_sweep.py`（速度×力度/调参/候选/验收矩阵，`--blocks matrix,slow,ref,repeat,gains,tune,cand,candmat,candrep,kiscan,slow2,fast,edges12,posgain,accept5,accept8,force8,slow8,soak` 选择）、`hyb_rate_test.py`（hybrid-ISR 速率对照）、`session_close.py`（候选确认收尾）、`smooth_analyze.py`（日志离析） |
| `experiments/tests/force_sweep/` | 力度档扫描：探针精写 `vq_max` 后单圈运行、跳闸自动 `z` 恢复重试；`recover.py`/`jog.py`/`restore_cfg.py` 辅助 |
| `experiments/probes/`、`archive_manifest.csv` | 40 个历史探测脚本与 1 个 APB_CLKEN 探测输出原样归档 + 路径/大小/SHA256 清单；相对路径不作运行保证 |
| `experiments/notes/` | 历史调参叙述、规格书文本提取、旧 README；不代表当前版本 |
| `experiments/logs/` | 本机调参、构建与串口日志（含 powered-20261016/ 镜像备份），不入 Git |
| `experiments/` | 测试、日志、历史探针与资料提取；详见其 README 和归档清单 |
| `.pio/` | MCU 构建数据库、ELF/BIN/HEX 及上次 logic 备份，不入库 |
| `CONTEXT.md` | 领域术语 |
| `docs/adr/` | 模块交付和宿主接口决策；目标不等同于已实现 |
| `docs/basic-motion-acceptance.md` | 基础运动验收矩阵；六个开环组合已于 2026-10-16 各通过一次；闭环速度×力度平滑扫描与候选配置见 `docs/smoothness-2026-10-17.md` |
| `docs/refactor-audit-2026-10-16.md` | 第一阶段问题清单、构建和回归结果 |
| `docs/code-audit-2026-10-16.md` | 第二轮代码复查：烧录复测被 SWD 无法 halt 阻塞、剩余风险清单 |
| `docs/unpowered-debug-2026-10-16.md` | 外设时钟修正、烧录、未供电诊断与上位机实测记录 |
| `docs/powered-debug-2026-10-16.md` | 通电调试：SPI 超时修复、总线桥验证、停止 BRK 与起步反抽的根因和修复、六组合五圈验收、nFAULT 硬件断路通道验证、闭环首轮与过流跳闸、力度档扫描 5–25% 与起步跳闸按起始电角度归因 |
| `docs/powered-debug-2026-10-17.md` | 过流判别（连续 3 拍+峰值/快照）与电流环首轮：坏窗口 E/D 决定性实验、真实 n=3 跳闸样本、定位/取证脚本与日志清单 |
| `docs/smoothness-2026-10-17.md` | 闭环平滑扫描（hyb=0）：速度×力度矩阵与重复性、hybrid 致 ISR 20 kHz→~12 kHz 定性、运动 kp=8 + kd60 + filt256 推荐配置与开机序列、kp=2/kp=8 五连圈验收、力度上限表、24 圈 soak、30 rpm 起步失败模式 |
| `docs/openloop-repeat-2026-10-17.md` | `fw=20261017.11` 开环六组合重复性：3/6/15 rpm 正反向各 5 圈，全部通过，零反向步进/零 glitch |
| `docs/position-accel-2026-10-17.md` | `fw=20261017.12` 位置轨迹加减速：0.25/1536 10/10、0.50/1013/768 各 10/10、0.50/1536/2048 各 2/2，全部 DONE，无起步跳闸 |
| `docs/closed-loop-velocity-2026-10-17.md` | `fw=20261017.24` 闭环速度 PI + 同步换向前馈：根因、SimpleFOC 参考、V1–V4/40%/80% 矩阵、开环/电流环对照、GUI/位置实连与 WDOG 恢复 |
| `docs/foc2205-fw-20261017.24-release.md` | GitHub 发布备注：`fw=20261017.24`、tag `foc2205-fw-20261017.24`、闭环 PASS、验证矩阵与上位机结论 |
| `docs/foc2205-fw-20261017.25-release.md` | GitHub 发布备注：`fw=20261017.25`、连续 rpm、三相电流遥测、立即急停、GUI 实连与自动回归结论 |
| `docs/ui-speed-current-estop-2026-10-18.md` | `.25` 上位机速度滑块、三相电流显示、急停时延、构建/上传/COM26 证据与未测边界 |
| `docs/haptic-modes-2026-10-17.md` | `fw=20261017.23` m0–m4 实现、PWM 采样边沿修复、1800 LSB 过流阈值、开环软启动/20% 上限、`rot ±360` 安全位置/低抖动档、高频原始角遥测、自动矩阵与人工体感边界 |
| `docs/spin-acceptance-2026-10-17.md` | `fw=20261017.5` SPIN 24 档与位置闭环 force8 验收：24/24 PASS、失联保护、编码器状态位 100 ms 判据、串口烧录顺序与 nRST 结论 |
| `docs/*接线设计.md`、`*引脚*.md`、`*网表.md` | 硬件设计资料；当前引脚以 VE 为准 |
| `docs/hardware/` | **板级硬件资料总目录**：原理图、EasyEDA 网表、器件规格书（详见其 README） |
| `docs/hardware/FOC驱动板原理图.pdf`、`docs/hardware/SimpleFOCMini-v2_netlist.md` | 自研板原理图与 EasyEDA 原生网表（工程名 SimpleFOCMini-v2） |
| `docs/hardware/datasheets/` | 器件规格书：MT6701QT-STD、DRV8316CRRGFR、DRV8316(TI)、50MHz 晶振、USBLC6-2P6 ESD、GL0603UG01 LED + 商城页存档 |
| `docs/hardware/easyeda-review/` | EasyEDA 原理图审查原始 JSON 导出（不入库） |
| `docs/电机参数.jpg/md` | 电机参数（2205/2804）原图与文本转录 |
| `docs/FOC2205_审查结果交付文档.md` | 先前审查整改历史 |
