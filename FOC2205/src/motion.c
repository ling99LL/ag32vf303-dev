// motion.c — 手感/运动层实现（见 motion.h 的契约说明）
//
// 设计约束：
//   * 绝不修改 foc.c —— 只写 g_foc.torque_q（电压模式下的"力矩"指令）。
//   * 全程带失步/超时/CRC 保护：宁可中止也不要让电机在大误差下跑飞。
//   * ISR 里跑，运算保持轻量（几个 float 乘加；foc.c 本身已在用 float 的
//     sincos，量级相当）。
#include "motion.h"
#include "foc.h"
#include "pwm3ph.h"
#include "app_io.h"

#define TWO_PI_F      6.28318530718f
#define PI_F          3.14159265359f
#define RAW_PER_TURN  16384.0f
#define RAW_HALF      8192

motion_cfg_t g_motion_cfg = {
  .kp         = 2.0f,    // 20% 闸门(1638 Q12)下 err 到 819 raw 才打满；而
                         // err_follow 把它卡在 500 raw —— 即跟随段永远不会
                         // 打满限幅，这才是"不抖"的结构性保证
  .kd         = 0.02f,   // 阻尼；速度估计受磁干扰不可信（可达 +-25000 raw/s），
                         // 阻尼项已在 ISR 里单独限幅到 25% 上限，这里取小值
  .kd_hold    = 0.0f,    // 保持态阻尼倍率：默认 0（关）。
                         //
                         // ⚠ 不是越大越好（2026-10-15 实测）：取 8 时 vq 在
                         // -626/+819 之间来回打，摆动反而更凶。原因是速度估计
                         // 的滞后（窗口 6.4 ms + IIR 25 ms ≈ 30 ms）对 80 Hz
                         // 量级的抖动意味着相位完全随机 —— 增益越大，"阻尼"
                         // 往系统里灌的能量越多。能可靠阻尼的只有 5 Hz 以下。
  .ki         = 1.5f,    // 积分（Q12/(raw*s)）：吃掉稳态滞后，带条件抗饱和
  .kff        = 0.125f,  // 反电动势前馈（粗估，够抵消匀速段的静差）
  .kfric      = 150.0f,  // 库仑摩擦前馈：干摩擦与速度大小无关、只随方向变号，
                         // 没有它 P 项得自己"憋"出这个电压才动 -> 稳态滞后
  .vq_max     = 6144,    // 起步值；motion_init() 会把它压到 MOTION_POWER_PCT_MAX
  .rev_per_s  = 0.05f,   // 慢速起步最稳（'v' 可调 0.02 ~ 0.5 rev/s）
  .err_follow = 500.0f,  // 指令最多超前转子 500 raw（11.0 机械度）——见 ISR 说明
                         //
                         // ⚠ 上限不是随便定的：7 极对数下 1 机械度 = 7 电角度，
                         // 负载角超过 90 电角度（= 12.86 机械度 = 585 raw）电压
                         // 矢量就跑到产生**负力矩**的半边，直接失步。旧值 800
                         // raw（123 电角度）已经越界 —— 力矩小时误差正好卡在
                         // 危险区。留 15% 余量取 500。
  .err_limit  = 2048.0f, // 45 机械度（315 电角度）：超过即判失步。旧值 4096
                         // （90 机械度）意味着已经转过 2 个半电周期才报错，
                         // 转子早就在原地抽搐了，收紧一半。
  .settle_raw = 200,     // 到位带宽：+-200 raw = 4.4 机械度。20% 出力下过冲小、
                         // 静摩擦也能推动，带宽可以比 10% 时（400）收得更紧。
  .timeout_ms = 10000u,  // 起步值，**不是**实际上限：motion_start_turns() 会按
                         // "指令时长 x2 + 5 s" 自适应抬高（0.05 rev/s 一圈要
                         // 20 s -> 抬到 45 s），所以慢速档不会被误中止。
  // --- 混合换向 ---
  .hyb_slip_deg   = 15.0f, // 死区 15 电角度：cos15=0.966，力矩只损失 3.4%，
                           // 折合机械 97 raw 的"游隙"留给扰动吸收
  .hyb_corr_pct   = 0.35f, // 校正速率上限 = 指令速率的 35%
  .hyb_corr_floor = 0.05f  // 下限 0.05 rev/s：HOLD（指令速率 0）时也能纠偏
};

// 速度估计窗口：每 s_vel_win 拍取一次位置差求平均。
// 单拍位移只有 0/1 raw，量化噪声 = isr_hz / win（64 拍 @40kHz -> +-625
// raw/s），比"每拍差分 x isr_hz"（+-40000）好 64 倍。
// ⚠ 这是"阻尼及时性"与"噪声"的取舍：窗口越长越平滑，但 kd 看到的速度越
// 滞后，高频振荡就压不住。'u' 键切换以便 A/B。
static uint16_t s_vel_win = 256u;
#define VEL_WIN s_vel_win

// 混合换向默认开关（串口 'y' 可随时切换做 A/B）。
// 1 = 默认启用：这是闭环抖动的根治方案（见 hybrid_step 的说明）。
#ifndef MOTION_HYBRID_DEFAULT
#define MOTION_HYBRID_DEFAULT 1
#endif

// 出力硬上限：g_foc.v_limit_q(8192 Q12 = 2.0V) 的 MOTION_POWER_PCT_MAX%。
// 5% -> 410 Q12 ≈ 0.10V 相电压幅值。所有下发路径都在这里被收口。
int32_t motion_vq_limit(void)
{
  int32_t lim = (int32_t)(((int64_t)g_foc.v_limit_q * (int64_t)MOTION_POWER_PCT_MAX) / 100);
  if (lim < 32) lim = 32;            // 别让它退化成 0
  return lim;
}

static motion_state_t s_state = MOTION_IDLE;
static uint32_t s_isr_hz = 40000u;     // 启动后被 main 实测值覆盖
static const char *s_fault = "";

// --- 位置环状态 ---
static int      s_have_last;
static uint16_t s_last_raw;
static int32_t  s_pos_unwrap;   // 累积位置（跨圈，raw）
static float    s_cmd_f;        // 斜坡指令位置（float 累加，避免小步长被截断）
static float    s_target_f;     // 终点
static float    s_start_f;
static float    s_inc;          // 每拍指令增量（带符号）
static int32_t  s_err;
static int32_t  s_final_err;    // 收尾时离目标还差多少（cmd 落到实际位置后
                                // s_err 会归零，这个保留真实残差）
static int32_t  s_vel;          // 平滑后的速度估计（raw/s）
static int32_t  s_vel_meas;     // 窗口差分的原始速度（raw/s）
static int32_t  s_vel_win_pos;  // 上一个窗口边界的累积位置
static uint16_t s_vel_win_cnt;  // 窗口内已计拍数
static int32_t  s_iacc;         // 积分项当前值（Q12，只读观察用）
static float    s_iacc_f;       // 积分项浮点累积（每拍增量极小，必须 float）
static int32_t  s_cmd_q12;
static uint32_t s_ticks;        // 本次动作已用 ISR 拍数
static uint32_t s_start_ticks;  // 起点（用于算 travelled）
static int32_t  s_pos_at_start;
static uint32_t s_inband;       // 连续在到位窗内的拍数
static uint32_t s_crc0;
static uint8_t  s_dir;          // 0 = 负向，1 = 正向
static int      s_stuck_flag;   // 收尾被静摩擦顶住（读到后清零）
// 保持态"松手"：静止够久就把输出降到 0（见 motion_step_isr 第 7 段）
static uint32_t s_hold_quiet;   // HOLD 内连续静止的拍数
static uint8_t  s_hold_relax;   // 1 = 已松手（u 强制为 0）

static uint32_t s_jump_hi;      // 单拍位移被正向钳位的次数（编码器假跳变计数）
static uint32_t s_jump_lo;      // 单拍位移被负向钳位的次数

// --- 抖动量化：动作期间速度估计的绝对值的均值/峰值（raw/s）---
// 这是本次优化的主指标：真实速度（0.05 rev/s）只有 819 raw/s，测出来的
// |vm| 越小越平顺。开环基线约 46 raw 峰峰对应 |vm| 量级很小，闭环原先是
// ±20000~40000。串口 MOVE DONE 行会打印它。
static uint64_t s_vib_acc;
static uint32_t s_vib_n;
static int32_t  s_vib_peak;

// --- 收尾"受阻"检测：指令已到终点、力矩打满、位置却不再变化 ---
static int32_t  s_stuck_pos;
static uint32_t s_stuck_cnt;
static uint32_t s_stuck_sat;    // 力矩连续饱和的拍数

// --- 手动强制三相（调试） ---
static uint8_t  s_manual;
static uint8_t  s_man_mask;
static int32_t  s_man_pct = 50;
static uint32_t s_man_ticks;
static uint32_t s_man_timeout_ticks;
static int      s_man_timedout;

#define MAN_TIMEOUT_MS 30000u
static uint8_t  s_th;
static int32_t  s_th_vq;
static uint32_t s_th_ticks_max;

// --- 开环状态 ---
static uint8_t  s_ol;
static float    s_ol_acc;       // 已推进的电角度（rad，wrap 到 [0,2pi)）
static float    s_ol_zero0;     // 进入开环前的零偏，退出时还原
static int8_t   s_ol_dir0;      // 进入开环前的 sensor_direction，退出时还原
static float    s_ol_inc;       // 每拍电角增量
static int32_t  s_ol_vq;
static uint32_t s_ol_ticks_max;

// --- 混合换向状态（见 motion.h 的说明）---
static uint8_t  s_hyb;          // 1 = 启用（'y' 键切换）
static float    s_hy_acc;       // 换向电角度（rad，wrap 到 [0,2pi)）
static int      s_hy_init;      // 是否已用编码器角对齐（每次启用都要重新对齐）
static float    s_hy_cmdprev;   // 上一拍的指令位置（取指令增量做前馈）
static float    s_hy_slip;      // 最近一次滑差（rad 电角度，正=换向角超前）
static uint32_t s_hy_corr;      // 校正动作计数
static uint32_t s_hy_slip_abort;// 丢步（滑差 > 80 电角度）中止次数

// ===========================================================================
// 混合换向（hybrid commutation）
//
// 为什么需要它（2026-10-15 A/B 判决，同一电机、同一 0.05 rev/s）：
//   闭环  速度波动 +-19.4%、抖动峰峰 250 raw(5.5 机械度)
//   开环  +-4.9%              、46 raw(1.0 机械度)
// 差别不在力矩大小、不在 kp、也不在编码器噪声 —— 而在于**转速有没有被锁死**：
//   * 闭环的换向角 = 编码器读数，转子爱多快多快，转矩扰动全部变成转速波动；
//   * 开环的换向角 = 内部累加器，转子平均转速必须等于电角频率，同样的扰动只
//     变成看不见的负载角（滑差）摆动。
// 混合换向 = 用指令前馈推进换向角（开环的刚性）+ 编码器慢速滑差校正（闭环的
// 防丢步）。换向角不再被编码器的每一个毛刺牵着走 —— 死区之内编码器根本不
// 参与，死区之外它的作用速率还被钳住。
// ===========================================================================

// 编码器换算出的电角度，与 foc.c 里 ang_e 同一坐标系（未经低通）
static void abort_move(const char *why);   // 定义在下面，这里提前声明给 hybrid_step 用

static float hybrid_encoder_elec(void)
{
  uint16_t raw = (uint16_t)(foc_last_angle() & 0x3FFFu);
  float raw_e = TWO_PI_F *
                (float)(((uint32_t)raw * g_foc.pole_pairs) & 0x3FFFu) / 16384.0f;
  float a = (raw_e - g_foc.zero_electric_angle) * (float)g_foc.sensor_direction;
  while (a < 0.0f)     a += TWO_PI_F;
  while (a >= TWO_PI_F) a -= TWO_PI_F;
  return a;
}

static float wrap_pm_pi(float x)
{
  while (x >  PI_F) x -= TWO_PI_F;
  while (x < -PI_F) x += TWO_PI_F;
  return x;
}

// 退出混合换向：把换向权交回 foc.c（编码器换向），并强制下次重新对齐
static void hybrid_off(void)
{
  if (g_foc.comm_override) {
    g_foc.comm_override = 0;
    s_hy_init = 0;
  }
}

void motion_hybrid_enable(int on)
{
  s_hyb = on ? 1 : 0;
  if (!s_hyb) {
    hybrid_off();
  } else {
    s_hy_init = 0;      // 下次进 ISR 时重新与编码器对齐
  }
}

int      motion_hybrid_enabled(void) { return (int)s_hyb; }
uint32_t motion_slip_corr(void)      { return s_hy_corr; }

int32_t motion_slip_raw(void)
{
  // 电角度 -> 机械 raw：1 机械圈 = pole_pairs 个电周期
  float k = TWO_PI_F * (float)g_foc.pole_pairs / RAW_PER_TURN;
  return (int32_t)(s_hy_slip / k);
}

// 每拍推进一次换向角。cmd_now = 本拍的指令位置（机械 raw，跨圈累积）。
// 返回 0 = 正常；返回非 0 = 已判丢步并中止（调用方直接 return）。
static int hybrid_step(float cmd_now)
{
  const float pp_f  = (float)g_foc.pole_pairs;
  const float k_el  = TWO_PI_F * pp_f / RAW_PER_TURN;   // rad 电角度 / 机械 raw
  float ang_enc = hybrid_encoder_elec();

  if (!s_hy_init) {
    // 接管时必须从"与转子完全对齐"起步，否则第一拍就会带着几百度的滑差
    // 猛推一下，轻则抖一下、重则直接丢步。
    s_hy_acc     = ang_enc;
    s_hy_cmdprev = cmd_now;
    s_hy_slip    = 0.0f;
    s_hy_init    = 1;
    g_foc.comm_angle_e = s_hy_acc;
    g_foc.comm_override = 1;
    return 0;
  }

  // 1) 指令前馈：换向角按**指令位移**推进。
  //    这是"转速被钉死"的来源 —— 指令走多快，电压矢量就转多快，与转子无关。
  //
  //    ⚠ 指令增量必须限幅。收尾时 settle_to_hold() 会把指令**瞬跳**回实际
  //    位置（语义是"停在这"，不是死守终点），那一跳可达数百 raw；不钳住的
  //    话换向角会在一拍里甩过几十个电角度，电机当场"咯噔"一下。正常运行时
  //    每拍增量只有 0.02 raw（0.05 rev/s），限幅根本不会触发。
  float dcmd = cmd_now - s_hy_cmdprev;
  {
    float si = (s_inc >= 0.0f) ? s_inc : -s_inc;
    float dmax = si * 2.0f + 8.0f;      // 正常步长的 2 倍 + 8 raw 余量
    if (dcmd >  dmax) dcmd =  dmax;
    if (dcmd < -dmax) dcmd = -dmax;
  }
  s_hy_cmdprev += dcmd;                 // 只记已兑现的部分，剩下的逐拍补上
  float dth = (float)g_foc.sensor_direction * dcmd * k_el;
  s_hy_acc += dth;

  // 2) 滑差校正：只在死区外动作，且速率被钳住。
  //    slip > 0 = 换向角超前转子（负载角为正）。cos(slip) 就是有效力矩系数，
  //    所以死区直接决定了"允许损失多少力矩"：15 度 -> 3.4%。
  float slip = wrap_pm_pi(s_hy_acc - ang_enc);
  s_hy_slip  = slip;
  float db = g_motion_cfg.hyb_slip_deg * PI_F / 180.0f;
  if (db < 1.0f * PI_F / 180.0f) db = 1.0f * PI_F / 180.0f;
  if (db > 60.0f * PI_F / 180.0f) db = 60.0f * PI_F / 180.0f;

  float ex = 0.0f;                       // 超出死区的部分
  if (slip >  db) ex = slip - db;
  if (slip < -db) ex = slip + db;
  if (ex != 0.0f) {
    // 校正速率上限 = 指令速率的 hyb_corr_pct + 固定下限（HOLD 时指令速率为 0，
    // 没有下限就永远纠不回来，转子被外力推动时会一路滑到丢步）。
    float adth   = (dth >= 0.0f) ? dth : -dth;
    float cmd_rps = adth * (float)s_isr_hz / (TWO_PI_F * pp_f);
    float max_rps = g_motion_cfg.hyb_corr_pct * cmd_rps +
                    g_motion_cfg.hyb_corr_floor;
    float cmax = max_rps * TWO_PI_F * pp_f / (float)s_isr_hz;  // rad/拍
    // 超出死区 20 电角度 -> 满速校正（饱和比例律，没有积分器不会 windup）
    float g = ex / (20.0f * PI_F / 180.0f);
    if (g >  1.0f) g =  1.0f;
    if (g < -1.0f) g = -1.0f;
    s_hy_acc -= g * cmax;                // slip 为正 -> 减小换向角
    ++s_hy_corr;
  }

  // 3) 丢步保护：滑差超过 80 电角度时 cos 已经掉到 0.17、力矩几乎没了，
  //    再往前就是滑极失步。宁可中止，也不要在大负载角下乱推。
  if (slip > 1.4f || slip < -1.4f) {
    ++s_hy_slip_abort;
    hybrid_off();
    abort_move("pole slip (hybrid)");
    return 1;
  }

  while (s_hy_acc < 0.0f)      s_hy_acc += TWO_PI_F;
  while (s_hy_acc >= TWO_PI_F) s_hy_acc -= TWO_PI_F;
  g_foc.comm_angle_e  = s_hy_acc;
  g_foc.comm_override = 1;
  return 0;
}

void motion_set_vel_window(uint16_t win)
{
  if (win < 8u)   win = 8u;
  if (win > 4096u) win = 4096u;
  s_vel_win = win;
  s_vel_win_cnt = 0;                 // 换档后第一个窗口不要拿旧边界算
  s_vel_win_pos = s_pos_unwrap;
}

uint16_t motion_vel_window(void) { return s_vel_win; }

// ---- 手动强制三相（调试） ----

// 把 mask/pct 换算成三个 CCR：高 = 中心 + pct/2，低 = 中心 - pct/2
static void manual_apply_pwm(void)
{
  float d = (float)s_man_pct / 200.0f;          // pct=100 -> 0.5 (100%/0%)
  int32_t c_hi = (int32_t)((float)PWM3PH_ARR * (0.5f + d));
  int32_t c_lo = (int32_t)((float)PWM3PH_ARR * (0.5f - d));
  pwm3ph_set((s_man_mask & 1u) ? c_hi : c_lo,
             (s_man_mask & 2u) ? c_hi : c_lo,
             (s_man_mask & 4u) ? c_hi : c_lo);
}

void motion_manual_start(uint8_t mask, int32_t pct)
{
  // 先结束任何进行中的动作（含开环的零偏还原），再接管输出
  motion_stop();
  s_manual = 1;
  s_man_mask = mask & 0x7u;
  if (pct >= 0) s_man_pct = pct;
  if (s_man_pct > 100) s_man_pct = 100;
  if (s_man_pct < 0)   s_man_pct = 0;
  s_man_ticks = 0;
  s_man_timeout_ticks = (uint32_t)((uint64_t)MAN_TIMEOUT_MS * s_isr_hz / 1000u);
  s_man_timedout = 0;
  drv_inl_high();      // 手动强制三相也要开下桥，否则绕组没有回路（见 begin_common）
}

void motion_manual_set(uint8_t mask, int32_t pct)
{
  if (!s_manual) {
    return;                     // 必须先 'm' 进入手动模式
  }
  if (mask != 0xFFu) s_man_mask = mask & 0x7u;
  if (pct  >= 0) {
    s_man_pct = pct;
    if (s_man_pct > 100) s_man_pct = 100;
  }
  s_man_ticks = 0;              // 每次操作都算"保活"，重新计时
}

void motion_manual_stop(void)
{
  s_manual = 0;
  drv_inl_low();       // 见 begin_common() 的说明
}

int      motion_manual_active(void) { return (int)s_manual; }
uint8_t  motion_manual_mask(void)   { return s_man_mask; }
int32_t  motion_manual_pct(void)    { return s_man_pct; }

int motion_manual_timed_out(void)
{
  int r = s_man_timedout;
  s_man_timedout = 0;
  return r;
}

void motion_init(void)
{
  s_state = MOTION_IDLE;
  s_have_last = 0;
  s_cmd_q12 = 0;
  s_iacc = 0;
  s_iacc_f = 0.0f;
  s_vel = 0;
  s_vel_meas = 0;
  s_vel_win_pos = s_pos_unwrap;  // 必须从当前位置起算，否则第一个窗口会把
                                 // 启动以来的累积位移当成"一瞬间的速度"
  s_vel_win_cnt = 0;
  s_stuck_cnt = 0;
  s_stuck_sat = 0;
  s_stuck_flag = 0;
  g_foc.torque_q = 0;
  hybrid_off();
  s_hyb     = MOTION_HYBRID_DEFAULT ? 1 : 0;
  s_hy_init = 0;
  s_hy_slip = 0.0f;
  // 起步出力压到硬上限（默认 = v_limit_q 的 10%），别用编译期的 6144。
  g_motion_cfg.vq_max = motion_vq_limit();
}

void motion_set_isr_rate(uint32_t hz)
{
  if (hz >= 1000u && hz <= 200000u) {
    s_isr_hz = hz;
  }
}

// 把两个绝对角之差折算到 (-8192, +8192]，即"最短路径增量"
static int32_t raw_delta(uint16_t now, uint16_t prev)
{
  int32_t d = (int32_t)now - (int32_t)prev;
  if (d >  RAW_HALF) d -= 16384;
  if (d < -RAW_HALF) d += 16384;
  return d;
}

static void abort_move(const char *why)
{
  s_fault = why;
  s_state = MOTION_FAULT;
  g_foc.torque_q = 0;
  s_cmd_q12 = 0;
  s_iacc = 0;
  s_iacc_f = 0.0f;
  drv_inl_low();                    // 见 begin_common() 的说明：中止即释放下桥
  hybrid_off();                     // 换向权交回 foc.c
  if (s_ol) {                      // 开环中断也要还原零偏/方向，否则闭环零位被污染
    g_foc.zero_electric_angle = s_ol_zero0;
    g_foc.sensor_direction = s_ol_dir0;
    s_ol = 0;
  }
  s_th = 0;
}

static void begin_common(void)
{
  //
  // ⚠ INL_ALL（PIN_28）改为"只在运动期间拉高"（2026-10-15 硬件冲突修复）。
  //
  //   PIN_28 同时是 **JNTRST** 焊盘，而 DAPLink 把它的 nTRST 持续驱动为低
  //   （openocd 日志里恒为 `nTRST = 0`）。固件一旦把这个 pad 释放成 GPIO 并
  //   驱动**高**电平，就与 DAP 的 nTRST 低电平在同一根线上顶牛：SWD 线上
  //   读回来的全是 `SWD ack not OK @ 0 JUNK`，openocd 报
  //   `Error connecting DP: cannot read IDR`，**从此再也烧不进去**，只能拆
  //   线或重新上电碰运气。
  //
  //   让 INL 在空闲/中止/松手时保持低电平（与 DAP 的 nTRST 一致）就没有
  //   冲突，SWD 随时可用。副作用全是正面的：空闲时下桥关断 —— 不发热、
  //   不啸叫、不消耗电流，也更安全。
  drv_inl_high();
  s_ticks = 0;
  s_inband = 0;
  s_iacc = 0;
  s_iacc_f = 0.0f;
  s_stuck_cnt = 0;
  s_stuck_sat = 0;
  s_stuck_pos = s_pos_unwrap;
  s_crc0 = foc_crc_errors();
  s_pos_at_start = s_pos_unwrap;
  s_fault = "";
  s_vib_acc = 0;
  s_vib_n = 0;
  s_vib_peak = 0;
  s_hold_quiet = 0;
  s_hold_relax = 0;
}

// 开环/力矩保持到期后的收尾：就地切换成闭环位置保持，避免松手回弹
static void finish_to_hold(void)
{
  s_cmd_f = s_target_f = (float)s_pos_unwrap;
  s_inc = 0.0f;
  s_state = MOTION_HOLD;
}

// 到位/受阻收尾：先记下离目标还差多少（供上位机如实报告残差），再把指令
// 落到**实际位置** —— 保持态的语义是"停在这"，不是"死守终点"。死守终点的话，
// 残留的那几百 raw 误差会让控制器一直全功率去拉（10% 力矩又拉不动），
// vq 长期打满，白白发热还抖。
static void settle_to_hold(void)
{
  s_final_err = s_err;
  finish_to_hold();
}

int motion_start_turns(float turns, float rev_per_s, int32_t vq_max_q12)
{
  if (s_state == MOTION_RUN) {
    return 0;                      // 不打断进行中的动作
  }
  if (rev_per_s <= 0.0f) rev_per_s = g_motion_cfg.rev_per_s;
  if (vq_max_q12 <= 0)   vq_max_q12 = g_motion_cfg.vq_max;

  g_motion_cfg.rev_per_s = rev_per_s;
  g_motion_cfg.vq_max    = vq_max_q12;
  if (g_motion_cfg.vq_max > g_foc.v_limit_q) {
    g_motion_cfg.vq_max = g_foc.v_limit_q;   // 永不超过 FOC 的安全上限
  }
  {
    int32_t hard = motion_vq_limit();        // 再压一道：全局出力闸门（默认 5%）
    if (g_motion_cfg.vq_max > hard) g_motion_cfg.vq_max = hard;
  }

  // 超时必须随指令时长自适应：0.05 rev/s 一圈要 20 s，固定 15 s 的超时会在
  // 慢速档下必然失败。按"指令时长 x2 + 5 s"兜底。
  {
    float mag = (turns < 0.0f) ? -turns : turns;
    uint32_t need_ms = (uint32_t)(1000.0f * mag / rev_per_s) * 2u + 5000u;
    if (g_motion_cfg.timeout_ms < need_ms) {
      g_motion_cfg.timeout_ms = need_ms;
    }
  }

  float dist = turns * RAW_PER_TURN;
  s_dir   = (dist >= 0.0f) ? 1 : 0;
  s_inc   = (s_dir ? 1.0f : -1.0f) * (rev_per_s * RAW_PER_TURN / (float)s_isr_hz);
  s_start_f  = (float)s_pos_unwrap;
  s_cmd_f    = s_start_f;
  s_target_f = s_start_f + dist;
  begin_common();
  s_state = MOTION_RUN;
  return 1;
}

int motion_torque_hold(int32_t vq_q12, uint32_t ms)
{
  if (s_state == MOTION_RUN) {
    return 0;
  }
  if (vq_q12 >  g_foc.v_limit_q) vq_q12 =  g_foc.v_limit_q;
  if (vq_q12 < -g_foc.v_limit_q) vq_q12 = -g_foc.v_limit_q;

  s_th = 1;
  s_th_vq = vq_q12;
  s_th_ticks_max = (uint32_t)((uint64_t)ms * s_isr_hz / 1000u);
  begin_common();
  s_state = MOTION_RUN;
  return 1;
}

int motion_openloop_start(float rev_per_s, int32_t vq_q12, uint32_t ms)
{
  if (s_state == MOTION_RUN) {
    return 0;
  }
  if (vq_q12 > g_foc.v_limit_q)  vq_q12 = g_foc.v_limit_q;
  if (vq_q12 < -g_foc.v_limit_q) vq_q12 = -g_foc.v_limit_q;

  // 电角速度 = 机械角速度 x 极对数。
  //
  // ⚠ 开环必须 x2，否则实际转速只有指令值的一半。原因在 foc.c 的
  //   ang_e = (raw_e - zero) * sensor_direction：
  //   dir = -1 时 ang_e = zero - raw_e，zero 的推进与转子自身 raw_e 的变化
  //   在稳态时是"叠加"的 —— 稳态解 n = -omega_e / (2 * pole_pairs)，
  //   即机械转速恰好是指令值的一半。实测 0.05 / 0.25 / 0.5 rev/s 三档，
  //   实测/指令比例恒为 0.497（与速度无关），确认是系统性 2 倍而非打滑。
  //   闭环不受影响：zero 固定时 d(ang_e)/dt = dir * pp * n，没有这个 2 倍。
  //
  // ⚠ 但 dir = +1 时上式**无稳态解**（d(ang_e)/dt = pp*n + omega_e 恒比转子
  //   快 omega_e，形成正反馈，转子只会加速到失步）。所以开环期间必须把
  //   sensor_direction 临时置 -1 —— 它是 foc_params_t 的**数据成员**，改它
  //   不需要动 foc.c 的逻辑，退出时还原即可。方向判定修复后 dir 恒为 +1，
  //   这正是之前开环"有时能转、有时乱抖"的原因。
  float omega_e = rev_per_s * TWO_PI_F * (float)g_foc.pole_pairs * 2.0f;
  s_ol_inc = omega_e / (float)s_isr_hz;
  s_ol_acc = 0.0f;
  s_ol_zero0 = g_foc.zero_electric_angle;
  s_ol_dir0  = g_foc.sensor_direction;
  g_foc.sensor_direction = -1;    // zero 偏移式开环只在 dir=-1 有稳态解
  s_ol_vq = vq_q12;
  s_ol_ticks_max = (uint32_t)((uint64_t)ms * s_isr_hz / 1000u);
  s_ol = 1;
  begin_common();
  s_state = MOTION_RUN;
  return 1;
}

void motion_stop(void)
{
  hybrid_off();
  if (s_ol) {
    g_foc.zero_electric_angle = s_ol_zero0;
    g_foc.sensor_direction = s_ol_dir0;
    s_ol = 0;
  }
  s_th = 0;
  s_state = MOTION_IDLE;
  s_cmd_q12 = 0;
  s_iacc = 0;
  s_iacc_f = 0.0f;
  g_foc.torque_q = 0;
  drv_inl_low();                    // 见 begin_common() 的说明
}

void motion_step_isr(void)
{
  // 1) 位置微分 + 累积（绝对角 -> 跨圈位移）
  //
  //    ⚠ 单拍位移必须限幅。物理上 0.25 rev/s 时每拍只走 0.1 raw，但实测窗口
  //    差分给出的位移高达 80+ raw（远超 8 rev/s），而长期平均位移又完全正确
  //    （305 ms 走 1240 raw = 0.248 rev/s，与指令吻合）。这说明编码器读数里
  //    混着**大幅假跳变**——MT6701 在电机通电时受绕组磁场干扰 / SPI 位错但
  //    CRC6 漏检（6 位 CRC 漏检率 1/64）。放过去会同时污染 s_pos_unwrap 和
  //    速度估计（kd 项被打爆 -> 力矩在 +-max 之间跳，就是"抖动"的直接来源）。
  //    这里按"物理上不可能超过 8 rev/s"钳掉，并统计钳位次数供诊断。
  uint16_t raw = (uint16_t)(foc_last_angle() & 0x3FFFu);
  int32_t d = s_have_last ? raw_delta(raw, s_last_raw) : 0;
  s_last_raw = raw;
  s_have_last = 1;
  {
    int32_t d_max = (int32_t)(8.0f * RAW_PER_TURN / (float)s_isr_hz) + 2;  // ~5 raw
    if (d >  d_max) { d =  d_max; ++s_jump_hi; }
    if (d < -d_max) { d = -d_max; ++s_jump_lo; }
  }
  s_pos_unwrap += d;

  // 2) 速度估计（raw/s）—— 用"窗口差分"而不是"每拍差分 x isr_hz"。
  //
  //    ⚠ 单拍位移 d 只有 0 或 1 raw（0.25 rev/s 时每拍 0.1 raw），乘以 s_isr_hz
  //    后量化噪声高达 +-40000 raw/s。旧的 32/256 拍 IIR 只能靠时间常数硬压：
  //    压得狠就迟滞、压得松就被 kd 放大成真实的力矩抖动，怎么调都别扭。
  //
  //    窗口差分从源头降噪：每 VEL_WIN 拍才取一次位置差，量化噪声 =
  //    isr_hz / VEL_WIN = 40000/64 ≈ +-625 raw/s，比单拍差分好 64 倍。
  //    之后再过一道 >>2 的 IIR（时间常数 4 个窗口 = 256 拍 ≈ 6.4 ms），
  //    最终噪声约 +-300 raw/s —— kd=0.1 时阻尼项只有 +-30 Q12，不会再抖。
  //    窗口更新时还要挡掉异常大跳变：如果 VEL_WIN 拍内的位移超过"好几转/秒"
  //    才可能的量，那一定是编码器跳读/CRC 漏检，而不是真实运动。放过去的话
  //    一个坏窗口就能把 s_vel 打到几十万，kd 项瞬间爆掉。
  if (++s_vel_win_cnt >= VEL_WIN) {
    int32_t dp = s_pos_unwrap - s_vel_win_pos;
    s_vel_win_pos = s_pos_unwrap;
    s_vel_win_cnt = 0;
    // 上限 = 3 转/秒 对应的窗口位移，再留几个 raw 的余量
    int32_t dp_max = (int32_t)(3.0f * RAW_PER_TURN *
                               (float)VEL_WIN / (float)s_isr_hz) + 4;
    if (dp >  dp_max) dp =  dp_max;
    if (dp < -dp_max) dp = -dp_max;
    s_vel_meas = (int32_t)(((int64_t)dp * (int64_t)s_isr_hz) / (int64_t)VEL_WIN);
    //
    // ⚠ 平滑 IIR **必须跟着窗口一起更新**（2026-10-15 实测修正）。
    //    旧代码把它放在窗口块外面，于是每拍（40 kHz）都以 1/4 的增益去追一个
    //    每 256 拍才变一次的值 —— 时间常数只有 4 拍 = 0.1 ms，注释里写的
    //    "4 个窗口 = 256 拍"根本没兑现。结果 s_vel ≈ s_vel_meas，窗口差分辛
    //    辛苦苦降下来的噪声又被原样放回去：实测 vel 与 vm 都是 ±20000~40000
    //    raw/s（真实速度才 819），kd 乘上去直接打满 25% 的阻尼限幅，变成
    //    156 Hz 的满幅正负跳变 —— 这才是闭环抖动最主要的能量来源。
    //    挪进窗口块后时间常数才是真正的 4 个窗口（25.6 ms）。
    s_vel += ((s_vel_meas - s_vel) >> 2);
    if (s_state == MOTION_RUN) {
      int32_t av = (s_vel_meas < 0) ? -s_vel_meas : s_vel_meas;
      s_vib_acc += (uint64_t)av;
      ++s_vib_n;
      if (av > s_vib_peak) s_vib_peak = av;
    }
  }
  // 最后一道保险：物理上限 4 转/秒。任何超过它的"速度"都是估计噪声。
  {
    int32_t vmax = (int32_t)(4.0f * RAW_PER_TURN);
    if (s_vel >  vmax) s_vel =  vmax;
    if (s_vel < -vmax) s_vel = -vmax;
  }

  // 手动强制三相：角度/电流照常刷新，只有输出被覆盖。带超时自动释放。
  if (s_manual) {
    hybrid_off();                  // 手动模式自己写 CCR，换向权交回 foc.c
    if (++s_man_ticks >= s_man_timeout_ticks) {
      s_manual = 0;
      s_man_timedout = 1;        // main 打印提示；下一拍 foc 立刻接管输出
      drv_inl_low();             // 见 begin_common() 的说明
    } else {
      manual_apply_pwm();
    }
    g_foc.torque_q = 0;
    s_cmd_q12 = 0;
    return;
  }

  if (s_state != MOTION_RUN && s_state != MOTION_HOLD) {
    g_foc.torque_q = 0;
    s_cmd_q12 = 0;
    hybrid_off();
    return;
  }

  ++s_ticks;

  // 混合换向只在"位置伺服/保持"下接管。开环(s_ol)本来就绕过了编码器、力矩
  // 保持(s_th)是诊断用的恒定电压，两者都维持原有的编码器换向以免污染 A/B。
  if (!s_hyb || s_ol || s_th) {
    hybrid_off();
  }

  // 3) 保护：CRC 风暴 / 超时 / 失步
  if ((foc_crc_errors() - s_crc0) > 200u) {
    abort_move("crc storm");
    return;
  }
  if (s_ol) {
    if (s_ticks >= s_ol_ticks_max) {
      g_foc.zero_electric_angle = s_ol_zero0;   // 还原零偏与方向，别污染闭环
      g_foc.sensor_direction = s_ol_dir0;
      s_ol = 0;
      finish_to_hold();
    }
  } else if (s_th) {
    if (s_ticks >= s_th_ticks_max) {
      s_th = 0;
      finish_to_hold();
    }
  } else if (s_state == MOTION_RUN &&
             (s_ticks * 1000u) / s_isr_hz > g_motion_cfg.timeout_ms) {
    // 只对"还在跑"的动作计时。MOTION_HOLD 是稳态（就地伺服保持），
    // 它会一直待到用户释放为止 —— 旧代码连 HOLD 也一起计时，于是开环/力矩
    // 保持收尾后必然在 timeout_ms 处报一次假的 "MOVE ABORT: timeout"
    // （实测 err=60 raw、vq=0，其实安静地停在终点）。
    abort_move("timeout");
    return;
  }

  float u;
  if (s_th) {
    // 力矩保持：恒定 q 轴电压，不跑位置环（诊断用）
    u = (float)s_th_vq;
  } else if (s_ol) {
    // 开环：电压矢量匀速推进，力矩恒定，不看反馈
    s_ol_acc += s_ol_inc;
    while (s_ol_acc >= TWO_PI_F) s_ol_acc -= TWO_PI_F;
    while (s_ol_acc <  0.0f)     s_ol_acc += TWO_PI_F;
    g_foc.zero_electric_angle = s_ol_zero0 - s_ol_acc;
    u = (float)s_ol_vq;
  } else {
    // 4) 指令推进 —— **电子齿轮跟随**，这是消除抖动的关键一环。
    //
    //    旧逻辑无条件按 s_inc 推进，指令是一条与转子状态无关的直线。出力被
    //    锁在 10% 时转子跟不上，误差一路涨到数百 raw，P 项立刻打满限幅 ->
    //    误差反向时又立刻打满反向 -> bang-bang 极限环（日志里的"剧烈抖动"）。
    //
    //    改成：指令最多超前转子 err_follow。跟得上就按设定速度走，跟不上就
    //    原地等。误差因此**结构上就有界**，永远进不了 bang-bang 区，也就
    //    不会失步。代价是实际平均速度可能低于设定值（力矩不够时），这正是
    //    力矩受限时应有的诚实行为 —— 宁可慢，不要抖。
    if (s_state == MOTION_RUN) {
      float e_now = s_cmd_f - (float)s_pos_unwrap;
      float fol = g_motion_cfg.err_follow;
      if (fol < 50.0f) fol = 50.0f;
      if ((s_inc > 0.0f && e_now <  fol) ||
          (s_inc < 0.0f && e_now > -fol)) {
        s_cmd_f += s_inc;
        if ((s_inc > 0.0f && s_cmd_f > s_target_f) ||
            (s_inc < 0.0f && s_cmd_f < s_target_f)) {
          s_cmd_f = s_target_f;
        }
      }
    }

    float e = s_cmd_f - (float)s_pos_unwrap;
    s_err = (int32_t)e;

    if (s_state == MOTION_RUN && (e > g_motion_cfg.err_limit || e < -g_motion_cfg.err_limit)) {
      abort_move("stall (error > limit)");
      return;
    }

    // 混合换向：用本拍的指令位置推进换向角（编码器只做慢速滑差校正）。
    // 放在这里是因为它要用到推进后的 s_cmd_f；它不影响 u 的计算，只改写
    // g_foc.comm_angle_e 供**下一拍** foc_step_isr 使用。
    if (s_hyb && !s_ol && !s_th) {
      if (hybrid_step(s_cmd_f)) {
        return;                      // 已判丢步并中止
      }
    }

    // 5) PD + 摩擦前馈 + 反电动势前馈 + 积分（条件抗饱和）
    float lim_c = (float)g_motion_cfg.vq_max;
    {
      float h = (float)motion_vq_limit();
      if (lim_c > h) lim_c = h;
    }
    int32_t vel_cmd = (int32_t)(s_inc * (float)s_isr_hz);
    u  = g_motion_cfg.kp * e;
    // 阻尼项**单独限幅**。速度估计在磁干扰下可达 +-25000 raw/s，kd 乘上去
    // 轻松超过出力上限，于是 vq 在 +-max 之间来回跳 —— 这是残余抖动的直接
    // 来源。夹在限幅的 25% 以内：小误差时仍线性起阻尼作用，大噪声时也不会
    // 把整个输出打飞。
    float u_d = g_motion_cfg.kd * (float)(vel_cmd - s_vel);
    float d_cap = lim_c * 0.25f;
    if (u_d >  d_cap) u_d =  d_cap;
    if (u_d < -d_cap) u_d = -d_cap;
    u += u_d;
    u += g_motion_cfg.kff * (float)vel_cmd;
    // 库仑（干）摩擦：大小与速度几乎无关、只随运动方向变号。没有这一项，
    // P 项必须自己"憋"出这个电压转子才开始动，表现为持续的稳态滞后；
    // 补上之后匀速段的残余误差显著变小。
    if (vel_cmd > 0)       u += g_motion_cfg.kfric;
    else if (vel_cmd < 0)  u -= g_motion_cfg.kfric;

    // 6) 积分项：**条件积分抗饱和**。
    //    每拍增量 = ki * e / isr_hz 只有 0.004 Q12 量级，必须用 float 累积
    //    （int 会直接截断成 0，积分形同不存在）。
    //    只在"输出未饱和"或"误差正把输出拉回限幅内"时累积 —— 否则力矩已打满，
    //    继续积分只会让退出饱和时狠狠回弹（经典的 integrator windup）。
    //
    // 另外积分**只在接近稳态时才工作**。|e| 超过 iacc_band 说明还在大范围
    // 运动，那点误差是跟随滞后而不是需要消除的稳态偏差；让它灌进积分，
    // 启动那一两百毫秒就能把积分打满（实测 -491 = 满负值，前馈被抵消掉，
    // 走到一半电机被自己拉住不动）。远离稳态时让积分缓慢回中。
    float iacc_lim = lim_c * 0.4f;
    float u_try = u + s_iacc_f;
    float iacc_band = (float)g_motion_cfg.settle_raw * 4.0f;
    if (iacc_band < 100.0f) iacc_band = 100.0f;
    //
    // ⚠ 保持态必须**冻结积分**（2026-10-15 实测修正）。
    //    HOLD 时指令已固定在当前位置，转子本该停住，但实测角度在 ±350 raw
    //    （±7.7 机械度）上持续摆动、且 vq 只有几十 Q12 —— 这点力矩根本推不动
    //    转子，摆动只能是**自己泵出来的**：积分器把位置误差积起来，相位比
    //    误差再滞后 90°，正好与速度同相 => 负阻尼，于是位置环 + 积分 + 机械
    //    共振构成一个约 2 Hz 的极限环，能量由限幅前的控制器自己供给。
    //    冻结（保留已有偏置、不再累积）即可断掉这条能量通路。
    //    ⚠ 保持态必须让积分**泄放归零**（2026-10-15 实测修正，踩了两个坑）：
    //    (a) 先试过"冻结不动"：结果残留的积分（实测 -199 Q12，占上限的 24%）
    //        是一个恒定推力，把转子一直往一边推；误差涨过 HOLD 死区后 P 项
    //        猛推回来 —— 死区 + 恒定偏置 = 教科书式的极限环，err 在 246~446
    //        之间来回摆，vq 在 -199 / +819 之间跳。
    //    (b) 更早的版本还在 HOLD 里继续累积积分，相位上正好与速度同相 =>
    //        负阻尼，自己给自己供能，摆动永远不衰减。
    //    归零才是正解：停稳后没有任何需要长期维持的负载，留着只会推着转子跑。
    if (s_state == MOTION_HOLD) {
      s_iacc_f -= s_iacc_f * (2.0f / (float)s_isr_hz);   // 0.5 s 时间常数泄放
    } else if (e < iacc_band && e > -iacc_band) {
      if (!((u_try >=  lim_c && e > 0.0f) || (u_try <= -lim_c && e < 0.0f))) {
        s_iacc_f += g_motion_cfg.ki * e / (float)s_isr_hz;
        if (s_iacc_f >  iacc_lim) s_iacc_f =  iacc_lim;
        if (s_iacc_f < -iacc_lim) s_iacc_f = -iacc_lim;
      }
    } else {
      s_iacc_f -= s_iacc_f / (float)s_isr_hz;      // 1 s 时间常数泄放回中
    }
    s_iacc = (int32_t)s_iacc_f;

    // 7) 保持态死区：指令已固定在当前位置，剩下的"误差"几乎全是编码器噪声。
    //    继续全增益伺服会不停追噪声 —— 白白出力发热，还可能把噪声放大成看得
    //    见的抖动。带宽内只留**纯阻尼**（vel_cmd=0，所以 u_d = -kd*s_vel）。
    //
    //    ⚠ 旧写法在这里写 u = s_iacc_f，而下面还有一句 u += s_iacc_f ——
    //    积分被算了两遍；而且把 P 项整个丢掉后连阻尼也没了。
    if (s_state == MOTION_HOLD) {
      float db = (float)g_motion_cfg.settle_raw;
      if (db < 20.0f) db = 20.0f;
      //
      // 保持态"松手"：静止够久就把输出降到 0。
      //
      // 实测（2026-10-15）这是唯一能彻底消掉收尾摆动的办法：一旦把力矩释放
      // （vq=0），编码器读数立刻变成 15177 ±1 raw、|vm|=0 完全稳定；只要闭环
      // 还在出力，就恒定存在 ±150 raw（3.3 机械度）的高频摆动 —— 它只在通电
      // 时出现，用手动直流锁相（电流更大）时反而没有，说明是"通电闭环"自身
      // 的产物，不是传感器被干扰。既然空载转子有摩擦自锁，停稳后松手是最干净
      // 的解法：不发热、不摆、也不吵。
      // 位置漂出去（|e| 超过 2 倍带宽）会立刻重新出力抓回来。
      if ((s_vel < 400 && s_vel > -400) && e < db && e > -db) {
        if (++s_hold_quiet > (s_isr_hz * 3u) / 2u) {   // 连续静止 1.5 s
          if (!s_hold_relax) drv_inl_low();  // 松手即关断下桥（见 begin_common）
          s_hold_relax = 1;
        }
      } else {
        s_hold_quiet = 0;
      }
      if (e > db * 2.0f || e < -db * 2.0f) {
        if (s_hold_relax) drv_inl_high();  // 被推走了，重新出力抓回
        s_hold_relax = 0;                              // 被推动/漂走了，重新抓
        s_hold_quiet = 0;
      }
      if (e < db && e > -db) {
        float u_hd = g_motion_cfg.kd * g_motion_cfg.kd_hold * (0.0f - (float)s_vel);
        float hd_cap = lim_c * 0.5f;
        if (u_hd >  hd_cap) u_hd =  hd_cap;
        if (u_hd < -hd_cap) u_hd = -hd_cap;
        u = u_hd;
      }
    }
    u += s_iacc_f;
    if (s_hold_relax) {
      u = 0.0f;                    // 保持态已松手（见上）：彻底不出力
    }

    // 8) 到位 / 受阻判定。
    //    判据必须与可用力矩匹配：出力锁 10% 时，静摩擦就能留下几百 raw 的
    //    稳态误差，+-40 raw（0.88 机械度）根本达不到，只会拖到超时。
    //    另外 s_vel 是编码器量化噪声放大的结果，拿它当"几乎不动"的判据
    //    永远不成立 —— 所以只看位置误差，不看速度。带宽由 settle_raw 配置。
    if (s_state == MOTION_RUN && s_cmd_f == s_target_f) {
      float band = (float)g_motion_cfg.settle_raw;
      if (band < 20.0f) band = 20.0f;
      if (e < band && e > -band) {
        if (++s_inband > (s_isr_hz / 20u)) {   // 连续 50 ms 在窗内
          settle_to_hold();
        }
      } else {
        s_inband = 0;
      }

      // 停滞收尾：指令已到终点、位置却几乎不再变化。
      //
      // ⚠ 判据只看"位置不动"，**不要求力矩饱和**。早期版本要求 |u| 打满，
      //    结果卡在"误差略超到位带宽（288 raw）但力矩只用了一半（-502）"
      //    的死区里 —— 既判不到位，也判不到受阻，只能拖到 timeout 失败。
      //
      //    1 秒内位移不足 6 raw 就是停住了：最慢的档 0.02 rev/s 也有
      //    327 raw/s，不会被误判。10% 出力下这是**物理极限而非故障**，
      //    按"尽力到位"收尾并如实报告残差分。
      int32_t moved = s_pos_unwrap - s_stuck_pos;
      if (moved < 6 && moved > -6) {
        if (++s_stuck_cnt > s_isr_hz) {        // 1 s 几乎没动
          s_stuck_flag = 1;
          settle_to_hold();
        }
      } else {
        s_stuck_cnt = 0;
        s_stuck_pos = s_pos_unwrap;
      }
    } else {
      s_inband = 0;
    }
  }

  // 7) 限幅下发（Q12 电压）——双重闸门：配置值和全局硬上限取小者
  float lim = (float)g_motion_cfg.vq_max;
  float hard = (float)motion_vq_limit();
  if (lim > hard) lim = hard;
  if (u >  lim) u =  lim;
  if (u < -lim) u = -lim;
  s_cmd_q12 = (int32_t)u;
  g_foc.torque_q = s_cmd_q12;
}

motion_state_t motion_state(void)   { return s_state; }
// 动作期间 |速度估计| 的均值（raw/s）——抖动主指标，越小越平顺
int32_t motion_vib_mean(void)
{
  return (s_vib_n > 0u) ? (int32_t)(s_vib_acc / (uint64_t)s_vib_n) : 0;
}
int32_t motion_vib_peak(void)       { return s_vib_peak; }
int     motion_hold_relaxed(void)   { return (int)s_hold_relax; }
int32_t  motion_error_raw(void)     { return s_err; }
int32_t  motion_final_err_raw(void) { return s_final_err; }
int32_t  motion_vel_rawps(void)     { return s_vel; }
int32_t  motion_vel_meas_rawps(void){ return s_vel_meas; }
uint32_t motion_jump_hi(void)       { return s_jump_hi; }
uint32_t motion_jump_lo(void)       { return s_jump_lo; }
int32_t  motion_cmd_q12(void)       { return s_cmd_q12; }
int32_t  motion_iacc_q12(void)      { return s_iacc; }
uint32_t motion_elapsed_ms(void)    { return (s_ticks * 1000u) / s_isr_hz; }
int32_t  motion_travelled_raw(void) { return s_pos_unwrap - s_pos_at_start; }
const char *motion_fault_msg(void)  { return s_fault; }

int motion_settled_stuck(void)
{
  int r = s_stuck_flag;
  s_stuck_flag = 0;
  return r;
}
