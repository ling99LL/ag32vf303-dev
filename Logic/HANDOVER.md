# Logic 4 通道逻辑分析仪 — 交接快照（2026-10-11）

## 当前版本

- **固件 / 上位机脚本**：git commit `d1818b3`（分支 `foc2205`，本地 **ahead 1，尚未推送**）
  - `feat(logic): raise self-test square wave to 10/25/50 MHz + on-board loopback verification`
- **板上已烧录**：固件 = `d1818b3`；CPLD logic 位流 = 上一次重建（commit `bcda1f2` 起未再改动 `.ve`，压缩位流加载地址 `0x80034000`）
- **自测波档位表**（`Logic/src/main.c`）：div=0 → **50 MHz**、div=1 → **25 MHz**、div≤4 → **10 MHz**、其余 → 20 kHz；`f = 100MHz/(TEST_DIV+1)`
- **SUMP 扩展命令**：`0x83` 手动覆盖 TEST_DIV（payload 低 16 位，`0xFFFF` = 自动档位表）；`0x00` 复位时自动恢复 AUTO

## 硬件与接口

- 芯片：AG32VF303，QFN32（`logic_device = AGRV2KQ32`，**不可改**）
- 引脚：CH0~CH3 = PIN_7/8/9/10（输入，弱下拉）；TEST_OUT = PIN_11；LED = PIN_12/13/14/18（低电平点亮）
- 接口：USB 2.0 FS CDC = **COM33**（SUMP/OLS，PulseView 直连）；UART0 调试 = COM26；烧录用 DAPLink `cmsis-dap-openocd`
- 自测回环：**PIN_10 ↔ PIN_11 跳线（2026-10-11 实物实测在接、验证通过）**

## 实测结论（均上板实测，非纸面）

- `live_hardware_test.py` 全套 **100% PASS**：8 档采样率绝对时基校验、硬件电平触发、8192 满载上传（~1.0 MB/s 净吞吐）
- 高频自测波：50 MHz @100MSa/s（2 点/周期严格 1010）、25 MHz @4 点、10 MHz @10 点等 6 项沿数与理论值精确吻合
- 稳定性：6 组高频配置 × 60 轮 = 360 次捕获 **0 失败**
- 详细数据见 `Logic/PERFORMANCE_REPORT.md` §2.1 / §2.1b

## 常用命令（工作目录 `Logic/`）

```bash
pio run -e logic_analyzer -t upload      # 只改 C：编译 + DAPLink 烧录（不重建 logic）
pio run -e logic_analyzer -t buildlogic  # 改 .ve：重新生成 logic 位流
# 改 .ve 必须三段式：prelogic → logic/run_quartus.tcl → logic/run_supra.bat → -t logic + -t upload
python live_hardware_test.py             # 上板回归（COM33）
```

## 交接注意事项 / 待办

- `d1818b3` **未推送**；`Logic/benchmark_usb.py` 及根目录若干散件仍未 git 跟踪（历史遗留）
- PulseView GUI 实际抓取未实证（协议层 SUMP 已实测）；边沿触发使用 SUMP 非标准位（mask bit4 → ctrl bit12）扩展实现
- 50 MHz 自测波处于 100 MSa/s 奈奎斯特边缘（2 点/周期），数字级验证通过，但波形形态需示波器确认
- 换引脚自测波/采样通道时：改 `Logic/logic_board.ve` 的 PIN 声明，需重走三段式并重烧 logic；避开 PIN_24/25(JTAG)、PIN_22/23(USB DM/DP)、PIN_1(晶振)
