// motion.h — 手感/运动层（hand-feel layer）
//
// 定位：这是 main.c 里那句 "hold torque at 0 until the hand-feel layer drives
// g_foc.torque_q" 所说的手感层。它**只写 g_foc.torque_q**，完全不修改 foc.c
// 的控制逻辑（FOC 仍是电压模式 + 编码器反馈），因此可以随时摘掉而不影响
// 原有闭环。
//
// 两种动作：
//   1) 位置伺服转圈（motion_start_turns）：梯形斜坡 + P/速度阻尼 + 反电动势
//      前馈，目标是"转过 N 圈机械角然后停住并保持"。
//      关键点：位置必须按**累积量**（unwrap）计算 —— MT6701 只给 0..16383 的
//      绝对角，若用最短路径差，转整圈时起点=终点，误差恒为 0，电机不会动。
//   2) 开环扫掠（motion_openloop_start）：强制电压矢量以固定电角速度旋转，
//      不看编码器。用于区分"相序/零偏错"和"力矩不足"这两类不动的原因。
//      实现技巧：不改 foc.c，而是每拍偏移 g_foc.zero_electric_angle —— 在
//      foc.c 里电角度 = raw_e - zero，所以给 zero 减一个增量等价于把电压
//      矢量往前推同样的角度。
//
// 单位约定：
//   位置/误差  raw（16384 = 一机械圈）
//   速度       raw/s
//   力矩指令   Q12 电压（4096 = 1.0V 相电压幅值）
#ifndef MOTION_H
#define MOTION_H

#include <stdint.h>

typedef enum
{
  MOTION_IDLE  = 0,   // 力矩释放（torque_q = 0）
  MOTION_RUN   = 1,   // 圈数运动进行中
  MOTION_HOLD  = 2,   // 已到位，继续伺服保持
  MOTION_FAULT = 3    // 中止（失步 / 超时 / CRC 风暴），力矩已释放
} motion_state_t;

typedef struct
{
  float    kp;          // Q12 电压 / raw 位置误差
  float    kd;          // Q12 电压 / (raw/s) 速度误差
  float    kd_hold;     // 保持态阻尼倍率（HOLD 内 P 项被死区摘掉，只留阻尼，
                        // 这里把 kd 放大以便尽快收住收尾摆动）
  float    ki;          // Q12 电压 / (raw * 秒) 积分增益（带条件抗饱和）
  float    kff;         // Q12 电压 / (raw/s) 指令速度（反电动势前馈）
  float    kfric;       // Q12 电压 常量：库仑（干）摩擦前馈，按指令方向变号
  int32_t  vq_max;      // Q12 力矩（电压）限幅，绝不超过 g_foc.v_limit_q
  float    rev_per_s;   // 斜坡速度（机械圈/秒）
  float    err_follow;  // raw：指令相对转子的最大超前量（电子齿轮跟随带）
  float    err_limit;   // raw：|误差| 超过它就判失步并中止（防跑飞）
  int32_t  settle_raw;  // raw：到位带宽
  uint32_t timeout_ms;  // 单次动作超时
  // --- 混合换向（hybrid commutation）---
  // 换向角不再直接取编码器读数，而是由**指令**前馈推进（转速被电角频率钉死，
  // 转矩扰动只变成看不见的负载角摆动 = 开环的平顺），编码器只在滑差超出死区
  // 时以有限速率把它拉回来（= 闭环的可靠，防丢步）。
  float    hyb_slip_deg;    // 滑差死区（电角度）：换向角允许偏离转子的角度
  float    hyb_corr_pct;    // 滑差校正速率上限，占当前指令速率的比例
  float    hyb_corr_floor;  // 校正速率下限（rev/s）：保证 HOLD（指令速率 0）时
                            // 也能纠偏，不会僵在死区外
} motion_cfg_t;

extern motion_cfg_t g_motion_cfg;

void motion_init(void);
// 用实测的 PWM 更新中断频率喂进来（ISR 里的计时与斜坡都靠它换算）
void motion_set_isr_rate(uint32_t hz);
// 必须在 foc_step_isr() **之后**调用：用刚更新的角度算下一拍的 torque_q
void motion_step_isr(void);

// 位置伺服：turns 为带符号圈数（+1 = 正转一圈，-1 = 反转一圈）
int  motion_start_turns(float turns, float rev_per_s, int32_t vq_max_q12);
// 释放力矩并回到 IDLE
void motion_stop(void);
// 开环扫掠：vq_q12 固定电压、以 rev_per_s 旋转电压矢量，持续 ms 毫秒
int  motion_openloop_start(float rev_per_s, int32_t vq_q12, uint32_t ms);
// 力矩保持（诊断用）：绕开位置环，直接把恒定 q 轴电压按住 ms 毫秒。
// 用来回答"给电压到底出不出力/转不转"——转子若被拉动，说明相序与零偏没问题，
// 剩下的就是位置环增益的事；若纹丝不动，问题在功率级或电角度零偏。
int  motion_torque_hold(int32_t vq_q12, uint32_t ms);

// 手动强制三相（调试用）：让 A/B/C 各自固定为"高"或"低"，用于硬件排查
//   —— 测哪一相通、哪一相开路、转子会不会被吸到某个位置。
// 实现要点：不关 PWM 中断（关了角度就停更），而是在每拍 ISR 末尾用手动值覆盖
// foc 刚写进去的 CCR；这样角度、电流采样照常刷新，只有输出被强制。
// mask: bit0=A bit1=B bit2=C，1=高(接 VM) 0=低(接 GND)
// pct : 驱动强度 0..100 —— 100 表示高=100%/低=0%（直通，电流大）；
//       50 表示高=75%/低=25%（压差减半）。调试建议先用小强度。
// 安全：超时无命令会自动退出（默认 30 s），避免长时间直流通电烧电机。
void motion_manual_start(uint8_t mask, int32_t pct);
void motion_manual_set(uint8_t mask, int32_t pct);
void motion_manual_stop(void);
int  motion_manual_active(void);
uint8_t motion_manual_mask(void);
int32_t  motion_manual_pct(void);
// 一次性标志：读到 1 表示"刚刚因超时自动退出过"，读后清零
int  motion_manual_timed_out(void);

// ---------------------------------------------------------------------------
// 混合换向（hybrid commutation）—— 串口 'y' 键开关
//
// 背景（2026-10-15 A/B 判决）：同电机同速下开环速度波动 ±4.9%、闭环 ±19.4%。
// 机理是**转速有没有被锁死**：
//   * 闭环：换向角 = 编码器读数，转子是自由的 → 转矩扰动直接变成转速波动；
//   * 开环：换向角 = 内部累加器，平均转速必须等于电角频率 → 同样的扰动只
//     变成看不见的负载角（滑差）摆动。
// 混合换向取两者之长：换向角由**指令位移**前馈推进（= 开环的刚性），编码器
// 只在"滑差超出死区"时以**有限速率**把它拉回来（= 闭环的防丢步）。高频的
// 编码器噪声因此进不了换向角 —— 死区之内它根本不参与，死区之外它的作用
// 速率还被钳住。
// ---------------------------------------------------------------------------
void motion_hybrid_enable(int on);
int  motion_hybrid_enabled(void);
// 滑差 = 换向角 - 真实转子角，折算回机械 raw（正 = 换向角超前 = 负载角为正）。
// 这是混合换向的"健康指标"：稳态应稳定在死区量级，越界说明快丢步了。
int32_t  motion_slip_raw(void);
// 滑差校正动作的累计拍数（诊断：看看纠偏是在持续工作还是偶尔触发）
uint32_t motion_slip_corr(void);
// 速度估计窗口（拍）。越小阻尼越及时但噪声越大；越大越平滑但阻尼迟滞。
// 'u' 键切换，用于 A/B 找"阻尼及时性 vs 噪声"的平衡点。
void     motion_set_vel_window(uint16_t win);
uint16_t motion_vel_window(void);

// 只读状态（供 main 打印 / JTAG 观察）
motion_state_t motion_state(void);
int32_t  motion_error_raw(void);    // 指令位置 - 实际位置（raw）
int32_t  motion_final_err_raw(void);// 本次动作收尾时离目标还差多少 raw
int32_t  motion_vel_rawps(void);    // 平滑后的速度（raw/s，带符号）
int32_t  motion_vel_meas_rawps(void); // 窗口差分的原始速度（诊断用）
// 编码器假跳变计数：单拍位移被"物理上限"钳位的次数（正/负向）。
// 这两个数在动的时候持续上涨 = 编码器读数被干扰，速度估计天然不可信。
uint32_t motion_jump_hi(void);
uint32_t motion_jump_lo(void);
int32_t  motion_cmd_q12(void);      // 实际下发的力矩指令（Q12）
// 抖动量化：动作期间速度估计绝对值（raw/s）的均值 / 峰值。
// 真实速度只有 819 raw/s @0.05 rev/s，所以这个值越小越平顺 —— 它是本次
// 优化的主指标（开环基线很小，闭环修好前是 ±20000~40000）。
int32_t  motion_vib_mean(void);
int32_t  motion_vib_peak(void);
// 1 = 保持态已松手（停稳 1.5 s 后把输出降到 0）。这是收尾摆动的根治手段。
int      motion_hold_relaxed(void);
int32_t  motion_iacc_q12(void);     // 积分项当前值（Q12，观察抗饱和是否生效）
uint32_t motion_elapsed_ms(void);   // 本次动作已用时
int32_t  motion_travelled_raw(void);// 本次动作已走的累积位移（带符号）
// 1 = 收尾阶段被静摩擦顶住（力矩已打满却推不动），已按"尽力到位"收尾。
// 这不是故障，只是 10% 出力下的物理极限；读到后清零。
int      motion_settled_stuck(void);
// 出力硬上限（占 FOC 安全电压上限 g_foc.v_limit_q 的百分比）。
// v_limit_q = 8192 Q12 = 2.0V 相电压幅值，故 10% = 819 Q12 ≈ 0.20V。
// ⚠ 20% = 1638 Q12 ≈ 0.40V。2026-10-15 实测：10% 下闭环 |vm| 已降到
// 852 raw/s（理想 819），但末端约 10 机械度的静摩擦残余推不动 —— 那是力矩
// 不足而非控制问题，故按用户要求放开到 20%。
// 这仍是"防跑飞闸门"：motion_step_isr 的下发限幅、motion_start_turns 的入参、
// 串口 +/- 的调参上限全部以它为准，任何路径都出不了这个圈。
#ifndef MOTION_POWER_PCT_MAX
#define MOTION_POWER_PCT_MAX 20
#endif

// 当前硬上限对应的 Q12 电压（= g_foc.v_limit_q * MOTION_POWER_PCT_MAX / 100）
int32_t motion_vq_limit(void);

const char *motion_fault_msg(void);

#endif
