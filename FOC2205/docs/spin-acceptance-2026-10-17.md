# SPIN 与位置闭环验收（fw=20261017.5–.10）

> 后续修正（`fw=20261017.19`）：PWM 电流采样边沿由谷点改为峰值/低边导通窗口，过流阈值提高到 1800 LSB；开环 SPIN 增加软启动并将力度上限统一降为 20%。按修正后的真实电流测量，40% 开环在 1 rps 和 0.1 rps 均会过流，本文早期 `.5–.10` 的 40% 开环通过记录不应再作为当前能力依据；当前 20% 开环 V1–V4 正反向 8/8 见 [力反馈手感验收记录](haptic-modes-2026-10-17.md)。

> 闭环结论更新（`fw=20261017.24`）：SPIN 闭环已从“无限位置斜坡”改为编码器速度 PI + 同步换向前馈。闭环 20% V1–V4 正反向 8/8、40%/80% V2/V4 8/8，且与开环同级；本文 `.5–.10` 的闭环位置斜坡数据仅保留为历史证据。详见 [闭环速度控制与平滑验收](closed-loop-velocity-2026-10-17.md)。

2026-10-17 13:xx，COM26 115200 8N1。目标：在新增无限旋转 SPIN 后，验证不同速度/力度下旋转是否平滑、是否抖动或误跳闸，并复测位置闭环。

## 结论

1. **SPIN 24/24 通过**：20/40/60/80% × V1/V2/V3（3/6/15 rpm）× 正反方向。转速误差 −1.12%…+0.27%，巡航 cv 2.94%…12.47%，全部零失速、零反向步进、零编码器毛刺；电流计数最大 `maxrun=1`，未发生连续超阈跳闸。
2. **60 rpm V4 8/8 通过**（`fw=20261017.6`）：20/40/60/80% × 正反方向，实测 59.18–59.48 rpm，巡航 cv 3.24%…4.83%，零失速/零反向/零编码器毛刺；20% 正向有 122 次孤立 ADC 超阈（maxrun=1），未跳闸。
3. **60 rpm 角滤波分档（`fw=20261017.7`）**：高频抓取显示 60 rpm 的主要纹波峰在 7 Hz（1 rev/s × 7 极对）。1/64 角滤波把 `vq` 标准差 184→137、7 Hz 速度纹波峰 238→157；1/16 为 174、关闭为 218，均不如 1/64。V1–V3 继续使用 1/256；15 rpm 的 20/80% 正反 4/4 回归通过（cv 2.9%…4.7%，失联 PASS）。V4 8/8 复测通过（59.03–59.48 rpm，cv 3.19%…5.08%）。
4. **失联保护通过**：SPIN 运行中停止发送有效命令，3.5 s 窗口内（覆盖 1 s 看门狗 + 2 s 减速上限）自动回到 `mode=0,st=0,out=0`。
5. **位置闭环 force8 8/8 DONE**：0.05/0.10/0.25 圈/秒与 1013/1536/2048 力度切片全部到位；cv 3.9%…15.28%，无失速/反向/编码器毛刺。此前 `.3` 下 0.25 圈/秒反向 1013 档的单拍 `encoder invalid/field` 中止不再出现。
6. **编码器状态位策略**：CRC 有效时继续使用 MT6701 角度；`mg&0x0b` 异常需持续约 100 ms（20 kHz 下 2000 拍）才锁存故障。单拍/短时磁场面状态不再误停，持续异常仍会跳闸（主机回归覆盖单拍通过、2000 拍跳闸）。
7. **开环/闭环 SPIN 切换（`fw=20261017.10`）**：`#0` 闭环、`#1` 开环；开环关闭电流环、使用固定电压矢量，共用 V1–V4 速度、失联看门狗和减速释放。开环 V1/V2×20/40% 正反 8/8、V4 20/40% 正反 4/4 PASS（59.5 rpm 附近，cv 2.9–3.5%）；闭环回归 2/2 PASS。
8. **开环 40% 上限**：60 rpm/60% 开环反向触发 DRV `driver status`（STAT1/STAT2=0x80），因此开环固定 40% 上限；闭环仍保留 80%。校准调制从 3% 提升到 5%，可自动脱离端位/静摩擦区并通过 `calst=7`。

## 条件与证据边界

- 力度是调制/电流请求上限，不等于仪器标定的物理力矩；本轮没有示波器相电流/母线波形。
- 平滑度来自编码器角度差分与固件状态帧：`cv`、100 ms 步进、失速/反向计数、`F` 峰值与连续超阈计数。
- 80% 仅用于 SPIN；普通位置动作仍受 `MOTION_POWER_PCT_MAX=25` 限制。80% 档只验证了当前空载旋钮，不能外推为任意负载。

## 关键日志

| 文件 | 内容 |
|---|---|
| `experiments/logs/powered-20261017/131327-v5-spin.json` | SPIN 24 档汇总（24/24 PASS） |
| `experiments/logs/powered-20261017/131327-v5-spin.txt` | SPIN 全帧与逐档 `F` 快照 |
| `experiments/logs/powered-20261017/132147-v5-disconnect.json` | 3.5 s 失联保护 PASS |
| `experiments/logs/powered-20261017/132217-smooth-v5-position.json` | 位置闭环 force8 8/8 DONE |
| `experiments/logs/powered-20261017/132217-smooth-v5-position.txt` | 位置闭环全帧、`MOVE` 与 `F` 记录 |
| `experiments/logs/powered-20261017/134005-v6-v4-low2.json` | 60 rpm 20/40% 正反 4/4 PASS |
| `experiments/logs/powered-20261017/134101-v6-v4-high.json` | 60 rpm 60/80% 正反 4/4 PASS |
| `experiments/logs/powered-20261017/135848-v7-v4.json` | `.7` 60 rpm 8/8 PASS |
| `experiments/logs/powered-20261017/140003-vib-v7-v4-w80.json` | `.7` 60 rpm/80% 高频纹波（1/64） |
| `experiments/logs/powered-20261017/134624-vib2-v4-w80.json` | `.6` 60 rpm/80% 高频纹波（1/256 对照） |
| `experiments/logs/powered-20261017/140058-v7-v3-reg.json` | `.7` 15 rpm 20/80% 正反 4/4 回归 |
| `experiments/logs/powered-20261017/140954-v8-open-low.json` | 开环 V1/V2 20/40% 8/8 PASS（`.8`） |
| `experiments/logs/powered-20261017/141057-v8-open-v4low.json` | 开环 60 rpm 20/40% 4/4 PASS（`.8`） |
| `experiments/logs/powered-20261017/142310-v10-open-v4.json` | `.10` 开环 60 rpm 20/40% 4/4 PASS |
| `experiments/logs/powered-20261017/142358-v10-closed-reg.json` | `.10` 闭环模式回归 2/2 PASS |

## 烧录与复位备注

- `agrv32flash` 串口写 MCU 必须 `-S 0x80000000`，写 CPLD 必须 `-S 0x80034000`；`-w` 会擦全片，因此顺序必须是 MCU 先、CPLD 后。
- 串口 `-K 0X80034000 -M foc2205.bin` 与压缩布局不兼容，会报假 checksum；应回读 `0x80034000:28604`，确认 `+0x1100` 起的位流与文件一致。
- DAPLink `nRST` 已接 PIN_4，可触发 SRST/DAP 复位，但不能保证 ROM 重新加载 CPLD；复位后仍可能无串口输出。可复用的 SWD 恢复是在同一 OpenOCD 会话内完成 `NDM reset → write CPLD+MCU → NDM reset → resume`；本机 10 MHz 偶发 Flash 写超时，5 MHz 稳定。
- 2026-10-17 进一步实测：WDOG 复位（unlock 0x40011C00、load、CTRL=RESET_EN、resume）能重新启动 `.9/.10` 并恢复串口，之后无需手动断电；SWD 写 Flash 在 5 MHz 仍偶发超时，2.5 MHz 稳定。

## 复现命令

```powershell
cd FOC2205
python experiments/tests/calibrate.py --port COM26
python experiments/tests/spin/accept_spin.py --port COM26 --tag v5-spin
python experiments/tests/spin/accept_spin.py --port COM26 --tag v5-disconnect --disconnect-only
python experiments/tests/spin/accept_spin.py --port COM26 --tag v6-v4 --speeds V4 --forces 20,40,60,80
python experiments/tests/current_loop/smoothness_sweep.py --blocks force8 --tag v5-position
```
