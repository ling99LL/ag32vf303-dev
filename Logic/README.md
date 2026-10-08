# AG32VF303 4通道逻辑分析仪项目 (QFN-32版)

本项目基于 AGM 遨格芯 **AG32VF303**（RISC-V 248MHz 内核 + 2K LE 片上 CPLD），实现了一款即插即用的 **4通道硬件逻辑分析仪**。
完全兼容 **SUMP / Openbench Logic Sniffer (OLS)** 协议，原生无缝对接 **PulseView / Sigrok** 上位机。

---

## 1. 硬件引脚分配表 (针对 QFN-32 封装: AGRV2KQ32)

本项目根据《AGM DAPLink 手册》QFN-32 封装规范严格规划，避开了调试口（PIN_24 JTMS, PIN_25 JTCK）、复位口（PIN_4 NRST）及启动口（PIN_30 BOOT0）：

| 通道 / 功能 | 芯片物理管脚 | VE 绑定网络 | 内部外设映射 | 信号电气方向与用途 |
|---|---|---|---|---|
| **CH0 (通道 0)** | **第 7 脚** | PIN_7 | GPIO2_0 | **输入** (3.3V LVTTL/LVCMOS 逻辑输入) |
| **CH1 (通道 1)** | **第 8 脚** | PIN_8 | GPIO2_1 | **输入** (3.3V LVTTL/LVCMOS 逻辑输入) |
| **CH2 (通道 2)** | **第 9 脚** | PIN_9 | GPIO2_2 | **输入** (3.3V LVTTL/LVCMOS 逻辑输入) |
| **CH3 (通道 3)** | **第 10 脚** | PIN_10 | GPIO2_3 | **输入** (3.3V LVTTL/LVCMOS 逻辑输入) |
| **TEST_OUT** | **第 11 脚** | PIN_11 | GPIO2_7 | **输出** (自检信号方波，可跳线短接至通道引脚自测) |
| **LED1 (Ready)** | **第 12 脚** | PIN_12 | GPIO4_1 | **输出** (低电平点亮，自检/跑马指示) |
| **LED2 (Armed)** | **第 13 脚** | PIN_13 | GPIO4_2 | **输出** (低电平点亮，等触发指示) |
| **LED3 (Capturing)**| **第 14 脚** | PIN_14 | GPIO4_3 | **输出** (低电平点亮，采样指示) |
| **LED4 (Uploading)**| **第 18 脚** | PIN_18 | GPIO4_4 | **输出** (低电平点亮，发数指示) |
| **USB D- / D+** | **第 22 / 23 脚** | PIN_22 / 23 | USB0 | 原生 USB 2.0 Full-Speed CDC 虚拟串口数据流 |
| **UART0 TX / RX** | **第 20 / 21 脚** | PIN_20 / 21 | UART0 | 调试/备用控制串口 |

---

## 2. 状态指示灯与动态效果

- **上电自检 (POST)**：芯片复位启动时，顺次点亮 IO12 -> IO13 -> IO14 -> IO18（每个 150ms），随后 4 颗灯同步闪烁 2 次。
- **待机跑马灯 (Idle Flow)**：在空闲待机期间，4 颗 LED 每 250ms 顺次流动点亮，直观确认芯片心跳与所有 LED 正常工作。
- **采集状态抢占 (Active State)**：当 PulseView 发起采样时，跑马灯自动暂停，精准反映 Armed（PIN_13）、Capture（PIN_14）、Upload（PIN_18）工作状态。

---

## 3. 实测性能与验证结果

- **采样深度**：最高 **64 KB**（单次 Burst 采样达 **65,536 个点**）。
- **实测有效上传带宽**：**~827.3 KB/s**（原生 USB 2.0 FS CDC-ACM），上传 64KB 采样数据仅需 **77.3 ms**，波形近乎实时刷新。
- **硬件电气验证**：通过物理跳线将 PIN_11 方波分别接入 PIN_7、PIN_8、PIN_9、PIN_10，PulseView 均 100% 精准捕获到对应通道的翻转方波，四通道完全物理隔离独立。

---

## 4. 上位机连接方式 (PulseView / Sigrok)

本项目使用官方 PulseView 64 位版本（已配置中文支持）：

### 终端一键直连：
`powershell
& 'C:\Program Files\sigrok\PulseView\pulseview.exe' -D -d 'ols:conn=COM33'
`

### 图形界面手动连接：
1. 打开 **PulseView**；
2. 点击顶部设备选择下拉框 -> **Connect to Device**；
3. **Step 1 (Driver)**: 选择 Openbench Logic Sniffer & SUMP compatibles (ols)；
4. **Step 2 (Interface)**: 选择 Serial Port，端口选择 COM33，波特率填 115200；
5. 点击 **Scan for devices using driver above**，识别到 AG32-LA4 后点击确定；
6. 顶部点击 **Run** 即可开始抓取波形，并可自由添加 I2C / SPI / UART / 1-Wire 等数十种协议解码器。

---

## 5. 项目工程结构

`
Logic/
├── logic_board.ve       # CPLD 引脚与时钟路由约束文件 (QFN-32 定制版)
├── platformio.ini       # PlatformIO 构建配置 (配置 logic_device = AGRV2KQ32)
├── src/
│   ├── main.c           # 4 通道逻辑分析仪固件 (SUMP 协议引擎 + LED 状态机)
│   ├── tusb_config.h    # TinyUSB 配置文件
│   └── usb_descriptors.c# USB CDC-ACM 描述符定义
├── run_la.py            # Python 命令行交互式抓波与 VCD 导出工具
├── verify_performance.py# 吞吐量与协议握手全自动审计脚本
├── capture_and_visualize.py # ASCII 字符波形绘制与 VCD 生成脚本
└── README.md            # 项目技术文档 (本文档)
`

---

## 6. 构建与烧录命令 (PIO CLI)

`ash
# 1. 重新综合与布局布线 CPLD 位流:
pio run -t buildlogic

# 2. 烧录 CPLD 压缩位流到 0x80034000 并烧录 MCU 固件到 0x80000000:
pio run -t logic -t upload
`
