# FOC2205/docs/hardware/ — 板级硬件资料

QFN32 自研 FOC 驱动板的原理图、网表、器件规格书与原理图审查导出。
**板子组成**：AG32VF303KCU6（QFN32）+ MT6701QT-STD 磁编码器 + DRV8316CRRGFR 三相驱动 + OT2EL4C4JI 50 MHz 有源晶振 + USBLC6-2P6 ESD + GL0603UG01 LED。
嘉立创（EasyEDA Pro）工程名：**SimpleFOCMini-v2**。

## 目录

| 路径 | 用途 |
|---|---|
| `FOC驱动板原理图.pdf` | 完整原理图（工作区 `docs/` 迁入） |
| `SimpleFOCMini-v2_netlist.md` | EasyEDA 原生网表转换版：网络→连接点 / 器件→引脚 双视图（导出日期 2026-10-14） |
| `datasheets/` | 器件规格书与商城页存档，见下 |
| `easyeda-review/` | EasyEDA 原理图审查的原始 JSON 导出（组件/属性/焊盘/全量提取）；**不入库**（`.gitignore`） |

## datasheets/

| 文件 | 器件 | 备注 |
|---|---|---|
| `C5447274_DRV8316CRRGFR_规格书_WJ487025.PDF` | DRV8316CRRGFR | 板载驱动芯片规格书（**C 版**） |
| `DRV8316_TI-SLVSF16B_datasheet.pdf` / `..._text.txt` | DRV8316 | TI 原厂手册（**非 C 版**），历史参考，勿与上件混淆 |
| `DRV8316C_datasheet_text.txt` | DRV8316C | 手册逐页文本提取，供检索/引用 |
| `C2913974_MT6701QT-STD_规格书_WJ1878447.PDF` | MT6701QT-STD | 磁编码器规格书 |
| `OT2EL4C4JI-111OLP-50M_datasheet.pdf` + `_page1..4.png` + `_lcsc-C5203552.html` | YXC YSO110TR 50 MHz | OSC1（CLK → PIN_1）；截图为手册页面 |
| `USBLC6-2P6_datasheet.pdf` / `USBLC6-2P6_text.txt` | USBLC6-2P6 | ESD 保护（SOT-563） |
| `GL0603UG01_LED_datasheet.pdf` + `_page4.png` + `_lcsc-54645989.html` | 桂光光电 GL0603UG01 | 板载 LED（0603） |

## 相关文档（上级 docs/）

- `../FOC2205_元件引脚连接网表.md` — 信号互联网表（画原理图以此为准）
- `../FOC2205_QFN32芯片引脚评估与分配规范.md` — 引脚分配规范（当前 V3.1）
- `../DRV8316+MT6701_FOC驱动板接线设计.md` — 接线设计
- `../FOC2205_审查结果交付文档.md` — 审查整改历史

> 现行引脚一律以 `FOC2205/foc2205.ve` 为准。上位机/固件入口见 [../../FILE_INDEX.md](../../FILE_INDEX.md)。
