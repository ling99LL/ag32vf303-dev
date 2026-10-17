# SimpleFOCMini-v2 原理图连接网表

> 本文件由 EasyEDA Pro（嘉立创EDA专业版）当前原理图导出的原生网表自动转换生成，
> 按“网络 → 连接点”与“器件 → 引脚”双视图组织，供 AI/脚本直接解析。

## 元信息

| 字段 | 值 |
|---|---|
| 工程 | SimpleFOCMini-v2 |
| Project UUID | 006c64e3af004849a3d1d5db2d2dd88e |
| 网表版本 | 2.0.0（EasyEDA 原生格式） |
| 导出日期 | 2026-10-14 |
| 器件数 | 45 |
| 引脚总数 | 175 |
| 网络数 | 43 |
| 未连接引脚 | 13 |

**阅读约定**：连接点写作 `位号.引脚号 (引脚名)`；电源/地网络明细见第 2 节；
仅 1 个连接点的网络为单端网络（见第 6 节）。

## 1. 网络连接表（Net → 连接点）

| # | 网络名 | 引脚数 | 连接点 |
|---|---|---|---|
| 1 | $C1_1 | 2 | C1.1 (1)<br>U3.6 (CPL) |
| 2 | $C1_2 | 2 | C1.2 (2)<br>U3.7 (CPH) |
| 3 | $C2_2 | 2 | C2.2 (2)<br>U3.8 (CP) |
| 4 | 3V3 | 21 | 3V3.1 (1)<br>C3.1 (1)<br>C7.1 (1)<br>C8.2 (2)<br>C9.2 (2)<br>C10.2 (2)<br>C14.1 (1)<br>C18.2 (2)<br>D1.2 (K)<br>L1.2 (2)<br>OSC1.4 (VDD)<br>R1.1 (1)<br>R2.1 (1)<br>R7.1 (1)<br>U1.6 (VDDA33)<br>U1.16 (VDD33)<br>U1.32 (VDD33)<br>U3.25 (AVDD)<br>U3.37 (VREF/ILIM)<br>U5.13 (VDD)<br>U5.14 (MODE) |
| 5 | BOOT0 | 3 | R8.1 (1)<br>U1.30 (BOOT0)<br>U2.1 (1) |
| 6 | BOOT1 | 2 | R9.1 (1)<br>U1.15 (PIN_15) |
| 7 | CLK | 2 | OSC1.3 (OUT)<br>U1.1 (PIN_1) |
| 8 | DRV_CSN | 2 | U1.31 (PIN_31)<br>U3.36 (GAIN) |
| 9 | DRV_FLT | 3 | R2.2 (2)<br>U1.22 (PIN_22)<br>U3.22 (nFAULT) |
| 10 | DRV_MISO | 2 | U1.29 (PIN_29)<br>U3.33 (MODE) |
| 11 | DRV_MOSI | 2 | U1.19 (PIN_19)<br>U3.34 (SLEW) |
| 12 | DRV_SCK | 2 | U1.18 (PIN_18)<br>U3.35 (OCP/SR) |
| 13 | DRV_SLP | 3 | R1.2 (2)<br>U1.5 (PIN_5)<br>U3.23 (nSLEEP) |
| 14 | FB_BK | 3 | C15.2 (2)<br>R4.1 (1)<br>U3.3 (FB_BK) |
| 15 | GND | 40 | C3.2 (2)<br>C4.2 (2)<br>C5.2 (2)<br>C6.2 (2)<br>C7.2 (2)<br>C8.1 (1)<br>C9.1 (1)<br>C10.1 (1)<br>C11.1 (1)<br>C12.1 (1)<br>C13.2 (2)<br>C14.2 (2)<br>C15.1 (1)<br>C16.2 (2)<br>C17.2 (2)<br>C18.1 (1)<br>CN1.2 (2)<br>D1.1 (A)<br>GND.1 (1)<br>OSC1.2 (GND)<br>R3.2 (2)<br>R8.2 (2)<br>R9.2 (2)<br>U1.17 (GND)<br>U1.33 (EP)<br>U2.4 (4)<br>U2.6 (6)<br>U2.7 (7)<br>U3.2 (AGND)<br>U3.4 (GND_BK)<br>U3.12 (PGND)<br>U3.15 (PGND)<br>U3.18 (PGND)<br>U3.21 (DRVOFF)<br>U3.26 (AGND)<br>U3.41 (GND)<br>U5.16 (GND)<br>U5.17 (EP)<br>X1.2 (GND)<br>X1.4 (GND) |
| 16 | INL_ALL | 5 | R3.1 (1)<br>U1.28 (PIN_28)<br>U3.28 (INLA)<br>U3.30 (INLB)<br>U3.32 (INLC) |
| 17 | ISEN_A | 3 | C5.1 (1)<br>R10.2 (2)<br>U1.10 (PIN_10) |
| 18 | ISEN_B | 3 | C6.1 (1)<br>R11.2 (2)<br>U1.11 (PIN_11) |
| 19 | ISEN_C | 3 | C13.1 (1)<br>R12.2 (2)<br>U1.12 (PIN_12) |
| 20 | JTCK | 2 | CK.1 (1)<br>U1.25 (PIN_25) |
| 21 | JTDI | 1 | U1.26 (PIN_26) |
| 22 | JTDO | 1 | U1.27 (PIN_27) |
| 23 | JTMS | 2 | MS.1 (1)<br>U1.24 (PIN_24) |
| 24 | MOT_A | 3 | A.1 (1)<br>U3.13 (OUTA)<br>U3.14 (OUTA) |
| 25 | MOT_B | 3 | B.1 (1)<br>U3.16 (OUTB)<br>U3.17 (OUTB) |
| 26 | MOT_C | 3 | C.1 (1)<br>U3.19 (OUTC)<br>U3.20 (OUTC) |
| 27 | MT_CLK | 2 | U1.13 (PIN_13)<br>U5.7 (B) |
| 28 | MT_CSN | 2 | U1.14 (PIN_14)<br>U5.8 (Z) |
| 29 | MT_DO | 2 | U1.23 (PIN_23)<br>U5.6 (A) |
| 30 | NRST | 2 | R7.2 (2)<br>U1.4 (NRST) |
| 31 | OSC_IN | 3 | C12.2 (2)<br>U1.2 (PIN_2)<br>X1.1 (1) |
| 32 | OSC_OUT | 3 | C11.2 (2)<br>U1.3 (PIN_3)<br>X1.3 (3) |
| 33 | PWM_A | 2 | U1.7 (PIN_7)<br>U3.27 (INHA) |
| 34 | PWM_B | 2 | U1.8 (PIN_8)<br>U3.29 (INHB) |
| 35 | PWM_C | 2 | U1.9 (PIN_9)<br>U3.31 (INHC) |
| 36 | RX | 2 | U1.21 (PIN_21)<br>U2.2 (2) |
| 37 | SOA | 2 | R10.1 (1)<br>U3.40 (SOA) |
| 38 | SOB | 2 | R11.1 (1)<br>U3.39 (SOB) |
| 39 | SOC | 2 | R12.1 (1)<br>U3.38 (SOC) |
| 40 | SW_BK | 2 | R4.2 (2)<br>U3.5 (SW_BK) |
| 41 | TX | 2 | U1.20 (PIN_20)<br>U2.3 (3) |
| 42 | VCC | 2 | L1.1 (1)<br>U2.5 (5) |
| 43 | VM | 8 | C2.1 (1)<br>C4.1 (1)<br>C16.1 (1)<br>C17.1 (1)<br>CN1.1 (1)<br>U3.9 (VM)<br>U3.10 (VM)<br>U3.11 (VM) |

## 2. 电源/地网络明细

### 3V3（21 引脚）

- 3V3.1 — 1
- C3.1 — 1
- C7.1 — 1
- C8.2 — 2
- C9.2 — 2
- C10.2 — 2
- C14.1 — 1
- C18.2 — 2
- D1.2 — K
- L1.2 — 2
- OSC1.4 — VDD
- R1.1 — 1
- R2.1 — 1
- R7.1 — 1
- U1.6 — VDDA33
- U1.16 — VDD33
- U1.32 — VDD33
- U3.25 — AVDD
- U3.37 — VREF/ILIM
- U5.13 — VDD
- U5.14 — MODE

### GND（40 引脚）

- C3.2 — 2
- C4.2 — 2
- C5.2 — 2
- C6.2 — 2
- C7.2 — 2
- C8.1 — 1
- C9.1 — 1
- C10.1 — 1
- C11.1 — 1
- C12.1 — 1
- C13.2 — 2
- C14.2 — 2
- C15.1 — 1
- C16.2 — 2
- C17.2 — 2
- C18.1 — 1
- CN1.2 — 2
- D1.1 — A
- GND.1 — 1
- OSC1.2 — GND
- R3.2 — 2
- R8.2 — 2
- R9.2 — 2
- U1.17 — GND
- U1.33 — EP
- U2.4 — 4
- U2.6 — 6
- U2.7 — 7
- U3.2 — AGND
- U3.4 — GND_BK
- U3.12 — PGND
- U3.15 — PGND
- U3.18 — PGND
- U3.21 — DRVOFF
- U3.26 — AGND
- U3.41 — GND
- U5.16 — GND
- U5.17 — EP
- X1.2 — GND
- X1.4 — GND

### VCC（2 引脚）

- L1.1 — 1
- U2.5 — 5

### VM（8 引脚）

- C2.1 — 1
- C4.1 — 1
- C16.1 — 1
- C17.1 — 1
- CN1.1 — 1
- U3.9 — VM
- U3.10 — VM
- U3.11 — VM

## 3. 器件清单（BOM 摘要）

| 位号 | 型号 | 厂家 | LCSC 编号 | 封装 | 引脚数 |
|---|---|---|---|---|---|
| 3V3 |  |  |  | Test-Point-0.5mm | 1 |
| A |  |  |  | Test-Point-0.5mm | 1 |
| B |  |  |  | Test-Point-0.5mm | 1 |
| C |  |  |  | Test-Point-0.5mm | 1 |
| C1 | CC0603KRX7R9BB473 | YAGEO(国巨) | C107093 | 0603 | 2 |
| C2 | CL10A105KO8NNNC | SAMSUNG(三星) | C1592 | 0603 | 2 |
| C3 | FCC0603B104K500CT | FOJAN(富捷) | C5137636 | 0603 | 2 |
| C4 | CGA0805X5R226M250MT | HRE(芯声) | C6119899 | 0805 | 2 |
| C5 | CL10C220JB8NNNC | SAMSUNG(三星) | C1653 |  | 2 |
| C6 | CL10C220JB8NNNC | SAMSUNG(三星) | C1653 |  | 2 |
| C7 | FCC0603B104K500CT | FOJAN(富捷) | C5137636 | 0603 | 2 |
| C8 | FCC0603B104K500CT | FOJAN(富捷) | C5137636 | 0603 | 2 |
| C9 | FCC0603B104K500CT | FOJAN(富捷) | C5137636 | 0603 | 2 |
| C10 | FCC0603B104K500CT | FOJAN(富捷) | C5137636 | 0603 | 2 |
| C11 | CL10C220JB8NNNC | SAMSUNG(三星) | C1653 |  | 2 |
| C12 | CL10C220JB8NNNC | SAMSUNG(三星) | C1653 |  | 2 |
| C13 | CL10C220JB8NNNC | SAMSUNG(三星) | C1653 |  | 2 |
| C14 | FCC0603B104K500CT | FOJAN(富捷) | C5137636 | 0603 | 2 |
| C15 | CGA0805X5R226M250MT | HRE(芯声) | C6119899 | 0805 | 2 |
| C16 | CGA0805X5R226M250MT | HRE(芯声) | C6119899 | 0805 | 2 |
| C17 | CGA0805X5R226M250MT | HRE(芯声) | C6119899 | 0805 | 2 |
| C18 | CGA0805X5R226M250MT | HRE(芯声) | C6119899 | 0805 | 2 |
| CK |  |  |  | Test-Point-0.5mm | 1 |
| CN1 | XH-2AW | HCTL(华灿天禄) | C2908611 | 弯插,P=2.5mm | 2 |
| D1 | SMF5.0CA | R+O(宏嘉诚) | C19077498 | SOD-123FL | 2 |
| GND |  |  |  | Test-Point-0.5mm | 1 |
| L1 | BLM21PG121SN1D | muRata(村田) | C79382 | 0805 | 2 |
| MS |  |  |  | Test-Point-0.5mm | 1 |
| OSC1 | OT2EL4C4JI-111OLP-50M | YXC(扬兴晶振) | C5203552 | SMD3225-4P | 4 |
| R1 | FRC0603J103 TS | FOJAN(富捷) | C2930027 | 0603 | 2 |
| R2 | FRC0603J103 TS | FOJAN(富捷) | C2930027 | 0603 | 2 |
| R3 | FRC0603J103 TS | FOJAN(富捷) | C2930027 | 0603 | 2 |
| R4 | 0603WAF220JT5E | UNI-ROYAL(厚声) | C23345 | 0603 | 2 |
| R7 | FRC0603J103 TS | FOJAN(富捷) | C2930027 | 0603 | 2 |
| R8 | FRC0603J103 TS | FOJAN(富捷) | C2930027 | 0603 | 2 |
| R9 | FRC0603J103 TS | FOJAN(富捷) | C2930027 | 0603 | 2 |
| R10 | RC0603FR-07330RL | YAGEO(国巨) | C105881 | 0603 | 2 |
| R11 | RC0603FR-07330RL | YAGEO(国巨) | C105881 | 0603 | 2 |
| R12 | RC0603FR-07330RL | YAGEO(国巨) | C105881 | 0603 | 2 |
| U1 | AG32VF303KCU6 | AGM(遨格芯微) | C41397171 | QFN-32-EP(4x4) | 33 |
| U2 | WAFER-GH1.25-5PWB | XUNPU(讯普) | C3029380 | SMD,P=1.25mm,卧贴 | 7 |
| U3 | DRV8316CTRGFR | TI(德州仪器) | C6602057 | VQFN-40(5x7) | 41 |
| U4 |  |  |  | JLC-QRCODE-5x5 | 0 |
| U5 | MT6701QT-STD | NOVOSENSE(纳芯微) | C2913974 |  | 17 |
| X1 | XL2EL89COI-111YLC-8M | YXC(扬兴晶振) | C2973805 | SMD3225-4P | 4 |

## 4. 器件引脚明细（Device → 引脚 → 网络）

### 3V3 — (无型号)

封装: Test-Point-0.5mm

| 引脚号 | 引脚名 | 网络 |
|---|---|---|
| 1 | 1 | 3V3 |

### A — (无型号)

封装: Test-Point-0.5mm

| 引脚号 | 引脚名 | 网络 |
|---|---|---|
| 1 | 1 | MOT_A |

### B — (无型号)

封装: Test-Point-0.5mm

| 引脚号 | 引脚名 | 网络 |
|---|---|---|
| 1 | 1 | MOT_B |

### C — (无型号)

封装: Test-Point-0.5mm

| 引脚号 | 引脚名 | 网络 |
|---|---|---|
| 1 | 1 | MOT_C |

### C1 — CC0603KRX7R9BB473

厂家: YAGEO(国巨) · LCSC: C107093 · 封装: 0603

| 引脚号 | 引脚名 | 网络 |
|---|---|---|
| 1 | 1 | $C1_1 |
| 2 | 2 | $C1_2 |

### C2 — CL10A105KO8NNNC

厂家: SAMSUNG(三星) · LCSC: C1592 · 封装: 0603

| 引脚号 | 引脚名 | 网络 |
|---|---|---|
| 1 | 1 | VM |
| 2 | 2 | $C2_2 |

### C3 — FCC0603B104K500CT

厂家: FOJAN(富捷) · LCSC: C5137636 · 封装: 0603

| 引脚号 | 引脚名 | 网络 |
|---|---|---|
| 1 | 1 | 3V3 |
| 2 | 2 | GND |

### C4 — CGA0805X5R226M250MT

厂家: HRE(芯声) · LCSC: C6119899 · 封装: 0805

| 引脚号 | 引脚名 | 网络 |
|---|---|---|
| 1 | 1 | VM |
| 2 | 2 | GND |

### C5 — CL10C220JB8NNNC

厂家: SAMSUNG(三星) · LCSC: C1653

| 引脚号 | 引脚名 | 网络 |
|---|---|---|
| 1 | 1 | ISEN_A |
| 2 | 2 | GND |

### C6 — CL10C220JB8NNNC

厂家: SAMSUNG(三星) · LCSC: C1653

| 引脚号 | 引脚名 | 网络 |
|---|---|---|
| 1 | 1 | ISEN_B |
| 2 | 2 | GND |

### C7 — FCC0603B104K500CT

厂家: FOJAN(富捷) · LCSC: C5137636 · 封装: 0603

| 引脚号 | 引脚名 | 网络 |
|---|---|---|
| 1 | 1 | 3V3 |
| 2 | 2 | GND |

### C8 — FCC0603B104K500CT

厂家: FOJAN(富捷) · LCSC: C5137636 · 封装: 0603

| 引脚号 | 引脚名 | 网络 |
|---|---|---|
| 1 | 1 | GND |
| 2 | 2 | 3V3 |

### C9 — FCC0603B104K500CT

厂家: FOJAN(富捷) · LCSC: C5137636 · 封装: 0603

| 引脚号 | 引脚名 | 网络 |
|---|---|---|
| 1 | 1 | GND |
| 2 | 2 | 3V3 |

### C10 — FCC0603B104K500CT

厂家: FOJAN(富捷) · LCSC: C5137636 · 封装: 0603

| 引脚号 | 引脚名 | 网络 |
|---|---|---|
| 1 | 1 | GND |
| 2 | 2 | 3V3 |

### C11 — CL10C220JB8NNNC

厂家: SAMSUNG(三星) · LCSC: C1653

| 引脚号 | 引脚名 | 网络 |
|---|---|---|
| 1 | 1 | GND |
| 2 | 2 | OSC_OUT |

### C12 — CL10C220JB8NNNC

厂家: SAMSUNG(三星) · LCSC: C1653

| 引脚号 | 引脚名 | 网络 |
|---|---|---|
| 1 | 1 | GND |
| 2 | 2 | OSC_IN |

### C13 — CL10C220JB8NNNC

厂家: SAMSUNG(三星) · LCSC: C1653

| 引脚号 | 引脚名 | 网络 |
|---|---|---|
| 1 | 1 | ISEN_C |
| 2 | 2 | GND |

### C14 — FCC0603B104K500CT

厂家: FOJAN(富捷) · LCSC: C5137636 · 封装: 0603

| 引脚号 | 引脚名 | 网络 |
|---|---|---|
| 1 | 1 | 3V3 |
| 2 | 2 | GND |

### C15 — CGA0805X5R226M250MT

厂家: HRE(芯声) · LCSC: C6119899 · 封装: 0805

| 引脚号 | 引脚名 | 网络 |
|---|---|---|
| 1 | 1 | GND |
| 2 | 2 | FB_BK |

### C16 — CGA0805X5R226M250MT

厂家: HRE(芯声) · LCSC: C6119899 · 封装: 0805

| 引脚号 | 引脚名 | 网络 |
|---|---|---|
| 1 | 1 | VM |
| 2 | 2 | GND |

### C17 — CGA0805X5R226M250MT

厂家: HRE(芯声) · LCSC: C6119899 · 封装: 0805

| 引脚号 | 引脚名 | 网络 |
|---|---|---|
| 1 | 1 | VM |
| 2 | 2 | GND |

### C18 — CGA0805X5R226M250MT

厂家: HRE(芯声) · LCSC: C6119899 · 封装: 0805

| 引脚号 | 引脚名 | 网络 |
|---|---|---|
| 1 | 1 | GND |
| 2 | 2 | 3V3 |

### CK — (无型号)

封装: Test-Point-0.5mm

| 引脚号 | 引脚名 | 网络 |
|---|---|---|
| 1 | 1 | JTCK |

### CN1 — XH-2AW

厂家: HCTL(华灿天禄) · LCSC: C2908611 · 封装: 弯插,P=2.5mm

| 引脚号 | 引脚名 | 网络 |
|---|---|---|
| 1 | 1 | VM |
| 2 | 2 | GND |

### D1 — SMF5.0CA

厂家: R+O(宏嘉诚) · LCSC: C19077498 · 封装: SOD-123FL

| 引脚号 | 引脚名 | 网络 |
|---|---|---|
| 1 | A | GND |
| 2 | K | 3V3 |

### GND — (无型号)

封装: Test-Point-0.5mm

| 引脚号 | 引脚名 | 网络 |
|---|---|---|
| 1 | 1 | GND |

### L1 — BLM21PG121SN1D

厂家: muRata(村田) · LCSC: C79382 · 封装: 0805

| 引脚号 | 引脚名 | 网络 |
|---|---|---|
| 1 | 1 | VCC |
| 2 | 2 | 3V3 |

### MS — (无型号)

封装: Test-Point-0.5mm

| 引脚号 | 引脚名 | 网络 |
|---|---|---|
| 1 | 1 | JTMS |

### OSC1 — OT2EL4C4JI-111OLP-50M

厂家: YXC(扬兴晶振) · LCSC: C5203552 · 封装: SMD3225-4P

| 引脚号 | 引脚名 | 网络 |
|---|---|---|
| 1 | Tri-state | — |
| 2 | GND | GND |
| 3 | OUT | CLK |
| 4 | VDD | 3V3 |

### R1 — FRC0603J103 TS

厂家: FOJAN(富捷) · LCSC: C2930027 · 封装: 0603

| 引脚号 | 引脚名 | 网络 |
|---|---|---|
| 1 | 1 | 3V3 |
| 2 | 2 | DRV_SLP |

### R2 — FRC0603J103 TS

厂家: FOJAN(富捷) · LCSC: C2930027 · 封装: 0603

| 引脚号 | 引脚名 | 网络 |
|---|---|---|
| 1 | 1 | 3V3 |
| 2 | 2 | DRV_FLT |

### R3 — FRC0603J103 TS

厂家: FOJAN(富捷) · LCSC: C2930027 · 封装: 0603

| 引脚号 | 引脚名 | 网络 |
|---|---|---|
| 1 | 1 | INL_ALL |
| 2 | 2 | GND |

### R4 — 0603WAF220JT5E

厂家: UNI-ROYAL(厚声) · LCSC: C23345 · 封装: 0603

| 引脚号 | 引脚名 | 网络 |
|---|---|---|
| 1 | 1 | FB_BK |
| 2 | 2 | SW_BK |

### R7 — FRC0603J103 TS

厂家: FOJAN(富捷) · LCSC: C2930027 · 封装: 0603

| 引脚号 | 引脚名 | 网络 |
|---|---|---|
| 1 | 1 | 3V3 |
| 2 | 2 | NRST |

### R8 — FRC0603J103 TS

厂家: FOJAN(富捷) · LCSC: C2930027 · 封装: 0603

| 引脚号 | 引脚名 | 网络 |
|---|---|---|
| 1 | 1 | BOOT0 |
| 2 | 2 | GND |

### R9 — FRC0603J103 TS

厂家: FOJAN(富捷) · LCSC: C2930027 · 封装: 0603

| 引脚号 | 引脚名 | 网络 |
|---|---|---|
| 1 | 1 | BOOT1 |
| 2 | 2 | GND |

### R10 — RC0603FR-07330RL

厂家: YAGEO(国巨) · LCSC: C105881 · 封装: 0603

| 引脚号 | 引脚名 | 网络 |
|---|---|---|
| 1 | 1 | SOA |
| 2 | 2 | ISEN_A |

### R11 — RC0603FR-07330RL

厂家: YAGEO(国巨) · LCSC: C105881 · 封装: 0603

| 引脚号 | 引脚名 | 网络 |
|---|---|---|
| 1 | 1 | SOB |
| 2 | 2 | ISEN_B |

### R12 — RC0603FR-07330RL

厂家: YAGEO(国巨) · LCSC: C105881 · 封装: 0603

| 引脚号 | 引脚名 | 网络 |
|---|---|---|
| 1 | 1 | SOC |
| 2 | 2 | ISEN_C |

### U1 — AG32VF303KCU6

厂家: AGM(遨格芯微) · LCSC: C41397171 · 封装: QFN-32-EP(4x4)

| 引脚号 | 引脚名 | 网络 |
|---|---|---|
| 1 | PIN_1 | CLK |
| 2 | PIN_2 | OSC_IN |
| 3 | PIN_3 | OSC_OUT |
| 4 | NRST | NRST |
| 5 | PIN_5 | DRV_SLP |
| 6 | VDDA33 | 3V3 |
| 7 | PIN_7 | PWM_A |
| 8 | PIN_8 | PWM_B |
| 9 | PIN_9 | PWM_C |
| 10 | PIN_10 | ISEN_A |
| 11 | PIN_11 | ISEN_B |
| 12 | PIN_12 | ISEN_C |
| 13 | PIN_13 | MT_CLK |
| 14 | PIN_14 | MT_CSN |
| 15 | PIN_15 | BOOT1 |
| 16 | VDD33 | 3V3 |
| 17 | GND | GND |
| 18 | PIN_18 | DRV_SCK |
| 19 | PIN_19 | DRV_MOSI |
| 20 | PIN_20 | TX |
| 21 | PIN_21 | RX |
| 22 | PIN_22 | DRV_FLT |
| 23 | PIN_23 | MT_DO |
| 24 | PIN_24 | JTMS |
| 25 | PIN_25 | JTCK |
| 26 | PIN_26 | JTDI |
| 27 | PIN_27 | JTDO |
| 28 | PIN_28 | INL_ALL |
| 29 | PIN_29 | DRV_MISO |
| 30 | BOOT0 | BOOT0 |
| 31 | PIN_31 | DRV_CSN |
| 32 | VDD33 | 3V3 |
| 33 | EP | GND |

### U2 — WAFER-GH1.25-5PWB

厂家: XUNPU(讯普) · LCSC: C3029380 · 封装: SMD,P=1.25mm,卧贴

| 引脚号 | 引脚名 | 网络 |
|---|---|---|
| 1 | 1 | BOOT0 |
| 2 | 2 | RX |
| 3 | 3 | TX |
| 4 | 4 | GND |
| 5 | 5 | VCC |
| 6 | 6 | GND |
| 7 | 7 | GND |

### U3 — DRV8316CTRGFR

厂家: TI(德州仪器) · LCSC: C6602057 · 封装: VQFN-40(5x7)

| 引脚号 | 引脚名 | 网络 |
|---|---|---|
| 1 | NC | — |
| 2 | AGND | GND |
| 3 | FB_BK | FB_BK |
| 4 | GND_BK | GND |
| 5 | SW_BK | SW_BK |
| 6 | CPL | $C1_1 |
| 7 | CPH | $C1_2 |
| 8 | CP | $C2_2 |
| 9 | VM | VM |
| 10 | VM | VM |
| 11 | VM | VM |
| 12 | PGND | GND |
| 13 | OUTA | MOT_A |
| 14 | OUTA | MOT_A |
| 15 | PGND | GND |
| 16 | OUTB | MOT_B |
| 17 | OUTB | MOT_B |
| 18 | PGND | GND |
| 19 | OUTC | MOT_C |
| 20 | OUTC | MOT_C |
| 21 | DRVOFF | GND |
| 22 | nFAULT | DRV_FLT |
| 23 | nSLEEP | DRV_SLP |
| 24 | VSEL_BK | — |
| 25 | AVDD | 3V3 |
| 26 | AGND | GND |
| 27 | INHA | PWM_A |
| 28 | INLA | INL_ALL |
| 29 | INHB | PWM_B |
| 30 | INLB | INL_ALL |
| 31 | INHC | PWM_C |
| 32 | INLC | INL_ALL |
| 33 | MODE | DRV_MISO |
| 34 | SLEW | DRV_MOSI |
| 35 | OCP/SR | DRV_SCK |
| 36 | GAIN | DRV_CSN |
| 37 | VREF/ILIM | 3V3 |
| 38 | SOC | SOC |
| 39 | SOB | SOB |
| 40 | SOA | SOA |
| 41 | GND | GND |

### U4 — (无型号)

封装: JLC-QRCODE-5x5

| 引脚号 | 引脚名 | 网络 |
|---|---|---|

### U5 — MT6701QT-STD

厂家: NOVOSENSE(纳芯微) · LCSC: C2913974

| 引脚号 | 引脚名 | 网络 |
|---|---|---|
| 1 | NC | — |
| 2 | NC | — |
| 3 | NC | — |
| 4 | NC | — |
| 5 | PUSH | — |
| 6 | A | MT_DO |
| 7 | B | MT_CLK |
| 8 | Z | MT_CSN |
| 9 | W | — |
| 10 | NC | — |
| 11 | U | — |
| 12 | V | — |
| 13 | VDD | 3V3 |
| 14 | MODE | 3V3 |
| 15 | OUT | — |
| 16 | GND | GND |
| 17 | EP | GND |

### X1 — XL2EL89COI-111YLC-8M

厂家: YXC(扬兴晶振) · LCSC: C2973805 · 封装: SMD3225-4P

| 引脚号 | 引脚名 | 网络 |
|---|---|---|
| 1 | 1 | OSC_IN |
| 2 | GND | GND |
| 3 | 3 | OSC_OUT |
| 4 | GND | GND |

## 5. 未连接引脚

- OSC1.1 (Tri-state)
- U3.1 (NC)
- U3.24 (VSEL_BK)
- U5.1 (NC)
- U5.2 (NC)
- U5.3 (NC)
- U5.4 (NC)
- U5.5 (PUSH)
- U5.9 (W)
- U5.10 (NC)
- U5.11 (U)
- U5.12 (V)
- U5.15 (OUT)

## 6. 单端网络（仅 1 个连接点，需人工确认）

- JTDI — U1.26 (PIN_26)
- JTDO — U1.27 (PIN_27)
