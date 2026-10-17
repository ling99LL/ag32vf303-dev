# 通电调试记录 2026-10-17：过流判别遥测与电流环首轮

承接 [docs/powered-debug-2026-10-16.md](powered-debug-2026-10-16.md)。10-16 闭环首轮出现过 1 次 `current ADC threshold` 跳闸，"真实过流还是采样离群"未定性；本轮先把跳闸判据改成"连续 N 拍 + 峰值/快照"遥测，再加入电流环 PI，最后在历史坏窗口做决定性 E/D 实验定性。10-17 深夜第二轮的闭环平滑扩展（运动环 kp=8、五连圈验收、力度上限表，并更正本文 A/B 段时长判读）见 [smoothness-2026-10-17.md](smoothness-2026-10-17.md)。

固件：`fw=20261017.1`（真实断电重上电后实测，hz≈20008）。串口证据全部来自 COM26 115200 8N1 串口脚本；没有做示波器/相电流波形测量，本记录中的电流均为 ADC LSB（1 LSB≈1.34 mA，跳闸线 200 LSB≈269 mA）。

## 结论速览

1. **坏窗口原跳闸定性为孤立采样毛刺**（不是持续过流）。在 ang≈7371–7386（10-16 记录中 109 ms 单拍跳闸处）原地起 1 圈：
   - 电压模式：`MOVE DONE` 998/1000 圈，19 次超阈全部孤立（`maxrun=1`），不跳闸；
   - 旧"单拍即跳"逻辑在此必然误杀（这 19 次都会触发中止）。
2. **新判别机制双向有效**：孤立毛刺 → 计 glitch、保快照、不中止；真实连续超阈 → 照常跳闸。当日别处捕捉到真实 `MOVE ABORT: current ADC threshold C n=3` 一次（间歇性）。
3. **电流环首轮可用**：从同一坏窗口原地起圈，环 ON（badpos 档）整圈完成、`maxrun=1`，峰值 `|vq|` 与速度抖动均低于电压模式；在 3 rpm 档保持全速（badpos=hyb0，设备报 20052 ms 即真实 20.05 s/圈）。
4. 未做：相电流/功率波形（无此类测量，不作物理幅值结论）。
5. **当晚接力更正（见 [smoothness-2026-10-17.md](smoothness-2026-10-17.md)）**：A/B 段"变慢"根因是混合换向（hyb=1）把控制 ISR 从 20 kHz 降到 ~12 kHz，与电流环无关（§二已更正）；`n=3` 现场快照已在 kp=16 用例捕获；B 段"配置敏感性"作废；重复性、6/15 rpm、多圈与电流环参数首轮扫描已在 hyb=0 下补做。

## 一、固件变更摘要（fw=20261017.1）

- **过流判别（foc.c/foc.h）**：`CURRENT_TRIP_LSB=200`（≈269 mA），`FOC_OC_TRIP_COUNT=3`；同一相连续 3 拍超阈才 `motion_trip("current ADC threshold ... n=N")`。孤立单拍超阈计入 glitch 计数，并做峰值捕获 + 事件前 8 拍冻结快照。状态帧新增 `cl,id,iq,iref,ipa,ipb,ipc,ocn,ocmx,ocg`。
- **`F` 命令（console.c）**：读取并清除过流捕获：`OC: pkA/pkB/pkC over/maxrun/glitch last=...`，若有事件再打印 `OC snap: kind=(trip|glitch) run= mask=` 与 8 行三相原始样本。
- **电流环（foc.c）**：PI 作用在实测 id/iq 上（默认 `kp=8 ki=100`，滤波 1/4，输出 cap 4096），`iref=torque_q/12`（50% 调制档时 2048/12≈170 LSB≈228 mA）。开关 `l`（仅待机且输出关闭时可切，开机默认关：`FOC_CURRENT_LOOP_DEFAULT=0`），整定档 `K`（kp）/`I`（ki）。
- **捕获分段语义（motion.c:154）**：每段动作开始都 `foc_oc_reset()`。计数与快照是"单次动作"粒度；取证必须在该动作结束后、下一次动作开始前用 `F` 读取，否则会被下一动作清掉（本轮曾因此丢掉一次 trip 快照）。
- 上电自检、故障恢复、`z` 语义不变；`r`/`R` 位置轨迹与开环模式不变。

## 二、验收档 A/B 段（2026-10-17 00:38，日志 `experiments/logs/powered-20261017/003807-currentloop-accept.txt`）

条件：默认验收配置（kp=2、kd=0.02、ki=1.5、follow=500、vel_win=256、ang_filt=1/64、hyb=1、vq_max=2048）、0.05 rev/s。

- **A 段（电压模式，cl=0）**：好位置 11185 起 1 圈，`MOVE DONE +16299 raw`，设备内报 20052 ms；`up=` 实测真实 33.5 s（≈1.79 rpm——hyb=1 降频所致，见备注），峰值 vq=192。`OC: over=101 maxrun=1 glitch=101` —— 101 次超阈**全部孤立**，未跳闸；快照为单相单拍尖峰（`ib=-210`，邻拍 ±2 内）。这正是"采样毛刺"特征。
- **B 段（电流环 ON，紧接下一圈）**：完成 0.997 圈，`up=` 实测 34.6 s（≈1.73 rpm，与 A 段同为 hyb=1 降频，与电流环无关）；peak_vq=320；`iq∈[-35,83]`、`iref∈[-24,26]`；`ocn=1473 ocmx=2 ocg=1469`；毛刺峰值 pkB=-626（约为电压模式的 2.4 倍）。全部仍是 0/1–2 连拍，从未 3 连拍，未跳闸。
- 备注（10-17 深夜更正）：A/B 段真实时长 33.5/34.6 s 均为混合换向 hyb=1 令控制 ISR 从 20 kHz 降到 ~12 kHz 所致（对照实验 hyb0 20.1 kHz / hyb1 12.1 kHz，`up=` 实时钟证据）；与电流环无关，D 段（badpos=hyb0）因此未复现。详见 [smoothness-2026-10-17.md](smoothness-2026-10-17.md) §2。

## 三、坏窗口 E/D 决定性实验（01:10 前后）

### 定位与配置对齐

- 目标窗口：ang≈7371–7386（10-16 `235017-poscheck-5pct-at-badpos.txt`：ang=7371 起 `r`，109 ms 即单拍跳闸；`235033-jog-mask1.txt`：7372 手动点动 7 ms 触发 encoder invalid/field）。
- 定位方法（脚本化）：磁吸跳步（手动 mask 短保持）粗定位 + 闭环 1 圈走位随机游走细定位。本机构磁平衡簇使 snap 落点离散（267/540/1576/2931/5103/8580…），最终第 99 次 snap 落到 7353，微走位后停在 7402，再走一步 `r` 到 **7343** 作为 E 起点（snap 段全记录见 `010042-snap-walk2.txt`）。
- E/D 配置对齐原坏位置实验：`hyb=0、ang_filt=1/1024、kp=4 kd=0 ki=10 follow=800 vel_win=64、vq_max=400`（cfg `ref=0.098`，原实验 410/`ref=0.100`）、速度 0.05。
- 起点几何：`r` 为"上升方向整圈"，从 7343 起飞后第 28–43 raw 处扫过窗口 [7371,7386]（B 相毛刺集中区）；若起点在 [7386,7436] 则整圈不会扫过该区，注意换向。

### E 段（电压模式，cl=0）：`011002-window-E.txt`

- 起点 7343 → `MOVE DONE +16356 raw (998/1000 圈) / 20052 ms`，残差 +28 raw；无中止。
- `OC[E] over=19 maxrun=1 glitch=19`；快照 `kind=glitch run=1 mask=2`，峰值样本 `(-111, 205, -109)`，邻拍回到 ±4 内。
- 幅度特征：peak|vq|=236、jitter peak 17507 raw/s、|iq| max 50、|ib| max 209（即毛刺本身）。
- 判读：坏窗口整圈 → **零次连续超阈**。旧单拍逻辑会在这里误杀 19 次；新逻辑全部正确地放过。

### D 段（电流环 ON，同起点）：`011036-window-D.txt`

- `l` 置 ON（`curloop=1` 已核验），起点 7338（与 E 差 5 raw）。
- `MOVE DONE +16377 raw (999/1000 圈) / 20052 ms`；无中止。
- `OC[D] over=33 maxrun=1 glitch=33`；快照 `kind=glitch mask=2`，峰值样本 `(-88, 213, -122)`。
- 幅度特征：peak|vq|=**193**（<E 的 236）、jitter peak **10629**（<E 的 17507）、|iq| max 26（iref max 16）。
- 判读：电流环在坏窗口**没有**把毛刺推成 ≥3 连拍；反而降低了调制峰值与速度抖动，整圈保持全速。

### 补充整圈扫描（电压/电流环各若干次）

- 电压模式整圈 `R`：TRIP1–4（`011118/011201/011225/011250-window-TRIP*.txt`）均完成，`over` 0–5、`maxrun=1`。
- 电流环整圈 `R`：LOOPR1/2（`011326/011351-window-LOOPR*.txt`）均完成，`over=9/8`、`maxrun=1`，jitter peak 10316/7815。
- 合计当日约 10 个整圈内，仅 walk1 一次触发 `n=3`（见下），其余全部孤立毛刺 —— 说明这类连续超阈事件稀少且间歇。

## 四、真实 n≥3 过流正样本（捕捉到一次）

日志 `005652-snap-walk.txt:271`（当时配置也是坏位置档对齐、电压模式）：

```
MOVE ABORT: current ADC threshold C n=3 (err=-22 raw, vel=-649 raw/s, vq=0, t=8426 ms)
```

- 该动作：从 ang=7086 发 `R`（下降方向整圈），8.426 s 时跳闸；停机位置 ang=275；帧内 `ocn=5 ocmx=3 ocg=2`、锁存 `fault=current ADC threshold C n=3`；`z` 恢复成功。
- 复现尝试：随后 6 次同配置整圈（TRIP1–4、LOOPR1/2 及微走位）未再触发 → 真实但**间歇**；机制可判定，不代表可稳定复现。
- 快照缺口：当时脚本在故障后先走了恢复流程，trip 快照被下一动作的 `foc_oc_reset()` 清除。新脚本 `run_window_move.py` 已改为"动作结束立即 F"，下次触发即可取到 `kind=trip` 的 8 拍冻结窗。
- 观察（假设，未验证）：跳闸停机点 ang≈275 与近零磁平衡簇（267–540）重合，可能是机械粘滞点；若属实属于机构-位置相关效应，与坏窗口同为磁平衡簇。

## 五、结论

1. 10-16 的"坏窗口 109 ms 单拍中止"与新固件坏窗口整圈数据合并判读：**原跳闸是采样毛刺**（单拍、孤立、20 kHz 下 50 µs 级），单拍判据会误杀正常动作；连续 3 拍判据在同样位置全部放过，且保住了毛刺统计与快照。
2. 判别机制双向有效：孤立 → 不跳闸（E/D/A/B 全部）；连续 3 拍 → 跳闸（C 相 n=3 样本）。
3. 电流环首轮可用：同起点不恶化（无 ≥3 连拍），峰值调制与抖动更低；iref=torque/12 时整圈电流参考 ≤170 LSB（<跳闸线 200）。
4. 证据边界：全部为串口帧/固件计数证据 + 编码器机械角；没有相电流波形，不宣称物理电流幅值；"毛刺 vs 过流"的判定基于连续拍数，不是幅值物理定标。

## 六、复现命令（COM26，115200）

```powershell
cd FOC2205/experiments/tests/current_loop
python set_preset.py --preset accept      # 验收档配置
python snap_walk2.py                      # 磁吸+走位停到 7378±(8..24)
python walk_one.py --cmd r --lo 7300 --hi 7365   # 校准到窗口下方起点
python set_preset.py --preset badpos      # 对齐坏位置档（hyb=0/filt 1/1024/vq~400/kp4/kd0/ki10）
python run_window_move.py --tag E --cmd r          # E 段：电压模式
python run_window_move.py --tag D --cmd r --loop on  # D 段：电流环
python final_state.py                     # 收尾：环 OFF、回缺省配置
```

脚本（`experiments/tests/current_loop/`）：`accept_current_loop.py`（A/B 段）、`snap_walk2.py`/`walk_one.py`（定位）、`set_preset.py`/`prep_ED.py`/`set_badpos_cfg.py`（配置）、`run_window_move.py`（单步取证）、`final_state.py`（收尾）。`snap_walk.py` 为 v1 版本，保留参考。

关键日志（`experiments/logs/powered-20261017/`，不入 Git）：

| 文件 | 内容 |
|---|---|
| `003807-currentloop-accept.txt` | A/B 段全帧 |
| `005652-snap-walk.txt` | walk1 `n=3` 跳闸现场 |
| `010042-snap-walk2.txt` | 坏窗口定位 99 次 snap 全记录 |
| `010906-walk-one.txt` | 进入 7343 起点的那一步 |
| `011002-window-E.txt` / `011036-window-D.txt` | E/D 决定性实验 |
| `011118..011351-window-TRIP*/LOOPR*.txt` | 补充整圈扫描 |
| `final-state-ED.txt` | 收尾状态（环 OFF、缺省配置、角 7415、idle） |

## 七、遗留事项

- 相电流/功率波形测量（示波器），给连续拍判别做物理定标参考。
- `n=3` 跳闸快照现场——已捕获：`020207-smooth-tune1.txt`（kp=16 用例，`kind=trip run=3 mask=4`，C 相 -217/-228/-217 LSB）。
- B 段"变慢"——已定性为混合换向 hyb=1 的 ISR 降频（smoothness 文档 §2），本项关闭。
- 重复性、6/15 rpm、多圈——已在 hyb=0 下完成（smoothness 文档 §4–§6）；开环六组合的重复性仍未做。
- 电流环参数扫描——首轮完成：kp 4/16 否决、保持默认 8；ki 一轮（50/200）因 hyb=1 污染作废待重扫；`ref_div` 与跟随手感基线未做。
- 新增：hybrid 每拍执行开销优化（`.11` 已把 `MOTION_HYBRID_DEFAULT` 改为 0；每拍优化仍未做）。
- 位置轨迹起步/收尾：`.12` 已加入 0.75 圈/秒² 梯形加减速；0.25/1536 10/10 DONE、0.50/1013 与 0.50/768 各 10/10 DONE，补充 1536/2048 各 2/2 DONE，无 n=3 或 encoder 中止；高力度 0.50 仍有较大 cv，详见 [位置轨迹加减速记录](position-accel-2026-10-17.md)。
