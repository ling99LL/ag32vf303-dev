# 测试与杂项归档

2026-10-16 整理：`probes/` 保存原 tools 中 40 个已跟踪历史脚本和 1 个探测输出；`logs/` 保存 65 个历史串口日志；`notes/` 保存两个资料文本提取、空 ports 记录、历史 README 及旧生成构建记录。文件采用移动或原样复制，没有清除历史证据。

- `tests/run_tests.py` 是本轮维护的测试入口，编译实际 motion/foc/mt6701/console/control 源码配合硬件桩。使用 GCC（默认 PATH，其次 `C:/MinGW/bin/gcc.exe`），不打开串口、不烧录。
- `tests/test_panel_protocol.py` 测试宿主协议、数据有效性、超时及操作条件，由 run_tests.py 一并运行。
- `tests/hardware_unpowered.py COM26 --reset` 是实板驱动未供电负向测试，打开串口并复位；先验证故障与输出关闭，再检查命令拒绝及持续查询，不与面板同时使用。日常日志直接用 tools/uart_capture.py 或 uart_console.py 读取。
- `tests/nfault/` 是 nFAULT/硬件断路通道验证（2026-10-16 第三轮）：`nfault_inject.tcl` 用 DRV8316C 自身 SPI 故障（8-clock 帧）产生真实 nFAULT，`halt_check.tcl` 确认 halt 真冻结内核，`nfault_cycle.py` 跑 inject→resume→`?`→`f`→`z`→`?`→restore 全流程。不改固件、不重烧；`.bat` 须从 `FOC2205/` 根目录运行。说明见该目录 README。
- `tests/force_sweep/` 是力度档扫描（2026-10-16 第五轮）：`accept_force_sweep.py` 用调试探针精写 `g_motion_cfg.vq_max` 后单圈闭环运行、跳闸自动 `z` 恢复重试；`recover.py`（故障恢复）、`jog.py`（手动点动换位置）、`restore_cfg.py`（重烧后按档位表恢复运行态增益）。需要 `fw=20261016.7` 调试镜像与探针连接，结果与归因见 `docs/powered-debug-2026-10-16.md` 第五轮。
- `archive_manifest.csv` 记录 40 个历史脚本的旧路径、新路径、大小和 SHA256；本轮逐个与 Git HEAD 字节比对通过。
- `probes/` 是历史快照，包含固定 SRAM 地址、绝对路径、自动烧录/上电等待等操作；移动后原相对路径不作运行保证。需要调试时先核对当前 ELF、地址、接线与路径，日常入口使用 `tools/`。
- `logs/`、测试可执行文件以及 Python 缓存不入 Git。日志保留在当前工作区；需要分享时另行打包。
- `notes/README-before-refactor-2026-10-16.md` 是历史调参记录，其中旧结论、旧命令和“已实测”不代表新版本验证。
