#include <math.h>
#include "foc.h"
#include "mt6701.h"
#include "current.h"
#include "pwm3ph.h"

#define TWO_PI_F 6.28318530718f
#define PI_F 3.14159265359f
#define FOC_LUT_SIZE 256

foc_params_t g_foc;
float g_align_delta;   // 对齐方向探测的 raw 电角度差（rad），诊断用

static float s_sin_lut[FOC_LUT_SIZE + 1];
static mt6701_sample_t s_angle;
static int16_t s_ia, s_ib, s_ic;
static int32_t s_angle_q14;
static int32_t s_iq_q12;
static uint32_t s_crc_errors;
static uint16_t s_isr_div;
static float   s_raw_e_filt;   // 低通后的电角度（换向用，见 foc_step_isr）
static uint8_t s_raw_e_init;

static void foc_lut_init(void)
{
  for (int i = 0; i <= FOC_LUT_SIZE; ++i) {
    s_sin_lut[i] = sinf((TWO_PI_F * (float)i) / (float)FOC_LUT_SIZE);
  }
}

// Fast sincos with linear interpolation: executes in ~25 cycles without __kernel_rem_pio2f or 448-byte stack
static inline void foc_fast_sincos(float angle_rad, float *s, float *c)
{
  const float rad2idx = (float)FOC_LUT_SIZE / TWO_PI_F;
  float idx_f = angle_rad * rad2idx;
  int idx = (int)idx_f;
  float frac = idx_f - (float)idx;

  idx &= (FOC_LUT_SIZE - 1);
  *s = s_sin_lut[idx] + frac * (s_sin_lut[idx + 1] - s_sin_lut[idx]);

  int c_idx = (idx + (FOC_LUT_SIZE / 4)) & (FOC_LUT_SIZE - 1);
  *c = s_sin_lut[c_idx] + frac * (s_sin_lut[c_idx + 1] - s_sin_lut[c_idx]);
}

void foc_init(uint16_t pole_pairs)
{
  foc_lut_init();
  g_foc.pole_pairs = pole_pairs;
  g_foc.v_limit_q = 8192;   // Q12 = 2.0V phase voltage — safe bring-up cap for any
                            // VM >= 7V (line-line ~3.5V); raise with Vbus sensing
  g_foc.id_ref_q = 0;
  g_foc.iq_ref_q = 0;
  g_foc.kp_q = 4096;
  g_foc.ki_q = 64;
  g_foc.zero_electric_angle = 0.0f;
  g_foc.sensor_direction = 1;
  g_foc.torque_q = 0;
  g_foc.brake = 0;
  // 换向角低通：1/64 -> 噪声衰减约 0.088 倍，滞后 1.6 ms。设 1.0 可完全关掉
  // （串口 'q' 键循环切换，用于 A/B 对比）。
  g_foc.angle_filt_alpha = 1.0f / 64.0f;
  g_foc.comm_override = 0;      // 默认走编码器换向；motion 层按需接管
  g_foc.comm_angle_e = 0.0f;
  s_raw_e_init = 0;
}

static int32_t clamp_i32(int32_t v, int32_t lim)
{
  if (v > lim) return lim;
  if (v < -lim) return -lim;
  return v;
}

// P1-1 fix: open-loop d-axis alignment -> zero electrical angle + direction.
// The alignment vector is derived from v_limit so it can never saturate the
// CCRs (a saturated space vector mis-zeros the calibration).
void foc_align_sensor(void)
{
  float vmax = (float)g_foc.v_limit_q / 4096.0f;
  if (vmax < 0.5f) vmax = 0.5f;
  float k = (float)PWM3PH_ARR / (2.0f * vmax);
  float v_align = 0.6f * vmax;   // 60% of the limit: holds the rotor, headroom left

  // Electrical angle 0 vector: (cos0, cos(-120deg), cos(+120deg))
  pwm3ph_set((int32_t)((float)PWM3PH_ARR * 0.5f + 1.0f * v_align * k),
             (int32_t)((float)PWM3PH_ARR * 0.5f - 0.5f * v_align * k),
             (int32_t)((float)PWM3PH_ARR * 0.5f - 0.5f * v_align * k));
  pwm3ph_outputs(1);
  delay_ms(400);                 // let the rotor snap to the d axis

  uint32_t sum_ang = 0;
  int valid = 0;
  for (int i = 0; i < 32; ++i) {
    mt6701_sample_t sample;
    if (mt6701_read(&sample)) {
      sum_ang += sample.angle;
      ++valid;
    }
    delay_ms(2);
  }
  if (valid == 0) {
    pwm3ph_set(0, 0, 0);
    return;                      // no CRC-valid frame: keep zero/direction defaults
  }
  uint32_t avg_mech = sum_ang / valid;
  g_foc.zero_electric_angle =
      TWO_PI_F * (float)(((uint32_t)avg_mech * g_foc.pole_pairs) & 0x3FFFu) / 16384.0f;

  // Direction probe: step the applied vector to electrical +90deg. If the
  // sensor's raw electrical angle then reads +90 (not -90 wrapped), the sensor
  // tracks the applied sequence positively; a negative-feedback sensor would
  // make the voltage loop run away, so catch it here, not on the bench.
  pwm3ph_set((int32_t)((float)PWM3PH_ARR * 0.5f + 0.0f * v_align * k),
             (int32_t)((float)PWM3PH_ARR * 0.5f + 0.866f * v_align * k),
             (int32_t)((float)PWM3PH_ARR * 0.5f - 0.866f * v_align * k));
  delay_ms(300);

  sum_ang = 0;
  valid = 0;
  for (int i = 0; i < 32; ++i) {
    mt6701_sample_t sample;
    if (mt6701_read(&sample)) {
      sum_ang += sample.angle;
      ++valid;
    }
    delay_ms(2);
  }
  pwm3ph_set(0, 0, 0);           // release: all-low = brake state in 3x mode
  if (valid == 0) {
    return;
  }
  float probe_raw =
      TWO_PI_F * (float)(((uint32_t)(sum_ang / valid) * g_foc.pole_pairs) & 0x3FFFu) / 16384.0f;
  float delta = probe_raw - g_foc.zero_electric_angle;
  while (delta < 0.0f)      delta += TWO_PI_F;
  while (delta >= TWO_PI_F) delta -= TWO_PI_F;
  // ⚠ 必须用"中心 +-45 度"窗口判定，不能用 90/270 度做边界。
  //   传感器正向时 delta 恰好 = +90 度，反向时恰好 = 270 度(=-90 度)。
  //   旧写法 "delta < 90 || delta > 270" 把判定边界正好压在真实值上，
  //   一点点噪声就会让方向在每次上电时随机翻转 —— 实测 dir 在 +1/-1 之间
  //   交替，翻到错的那次闭环变成正反馈，电机原地剧烈抖动而不是转动。
  //   现在：delta 落在 (45,135) 度 -> +1；落在 (225,315) 度 -> -1。
  g_align_delta = delta;
  g_foc.sensor_direction =
      (delta > TWO_PI_F * 0.125f && delta < TWO_PI_F * 0.375f) ? 1 : -1;
}

// Voltage-mode FOC step (runs in the GPTIMER0 update ISR = PWM valley):
// currents + angle are sampled first so phase and current share one instant,
// then inverse Park + Clarke + SVPWM injection produce the three duties.
void foc_step_isr(void)
{
  // 1. valley-synchronous current telemetry, every 16th cycle (P2-3: the
  //    voltage-mode loop does not consume currents yet, so full-rate polling
  //    would only burn ~2% of the CPU; restore full rate with the current loop)
  if ((s_isr_div++ & 0x0Fu) == 0) {
    current_trigger();
    current_read_raw(&s_ia, &s_ib, &s_ic);
  }

  // 2. angle (SSI frame = 1.92us @12.5MHz, CRC6 verified)
  if (!mt6701_read(&s_angle)) {
    ++s_crc_errors;         // drop frame, keep last good angle
  }
  s_angle_q14 = s_angle.angle;

  if (g_foc.brake) {
    pwm3ph_set(0, 0, 0);    // all low = brake state in 3x mode
    return;
  }

  // 3. electrical angle with calibrated zero-offset
  float raw_e = TWO_PI_F * (float)(((uint32_t)s_angle.angle * g_foc.pole_pairs) & 0x3FFFu)
                / 16384.0f;
  //
  // ⚠ 换向角低通滤波 —— 闭环抖动的直接成因在这里。
  //
  //    闭环时 ang_e 直接由 encoder 读数算出，于是编码器的噪声/量化误差被
  //    **乘以极对数(7)** 后直接调制电压矢量：实测闭环中机械角高频抖动
  //    std=60 raw，折合电角度 ±9.2°，等于每拍都在晃电压矢量的方向 → 真实
  //    的转矩纹波 → 机械抖动 → 编码器读到的噪声更大（正反馈）。
  //    开环没有这条通道（角度来自内部累加器，天然光滑），所以实测只有
  //    ±3.4~4.9% 的速度波动，而闭环有 ±15%，且**降低 kp 反而更抖**
  //    （kp=2 → 217 raw 峰峰；kp=0.5 → 425 raw 峰峰），证明不是"P 项放大
  //    噪声"，而是换向通道本身。
  //
  //    在电角度域做一阶低通即可切断这个环。取 alpha=1/64：噪声衰减
  //    sqrt(alpha/2) ≈ 0.088 倍，滞后约 64 拍 = 1.6 ms，在 0.05 rev/s 下
  //    只折合 1.3 raw 机械滞后，可以忽略。
  {
    float a = g_foc.angle_filt_alpha;
    if (!(a < 1.0f)) {              // a >= 1 或 NaN：直通（保留 A/B 能力）
      s_raw_e_filt = raw_e;
      s_raw_e_init = 1;
    } else if (!s_raw_e_init) {
      s_raw_e_filt = raw_e;
      s_raw_e_init = 1;
    } else {
      float d = raw_e - s_raw_e_filt;
      while (d >  PI_F) d -= TWO_PI_F;   // 跨圈短路：走最短路径
      while (d < -PI_F) d += TWO_PI_F;
      s_raw_e_filt += a * d;
    }
  }
  float ang_e = (s_raw_e_filt - g_foc.zero_electric_angle) * (float)g_foc.sensor_direction;
  // 混合换向接管点：motion 层每拍写入 comm_angle_e 并置 comm_override。
  // 关闭时这一行不执行，行为与从前逐拍一致（可随时用串口 'y' 做 A/B）。
  if (g_foc.comm_override) {
    ang_e = g_foc.comm_angle_e;
  }
  while (ang_e < 0.0f) ang_e += TWO_PI_F;
  while (ang_e >= TWO_PI_F) ang_e -= TWO_PI_F;

  // 4. q-axis voltage = torque command from the hand-feel layer, d-axis = 0
  float vq = (float)clamp_i32(g_foc.torque_q, g_foc.v_limit_q) / 4096.0f;
  float vd = (float)g_foc.id_ref_q / 4096.0f;
  float vmax = (float)g_foc.v_limit_q / 4096.0f;
  if (vmax < 0.01f) {
    vmax = 0.01f;
  }

  // 5. inverse Park with fast LUT sincos (D-2 fix)
  float c, s;
  foc_fast_sincos(ang_e, &s, &c);
  float va = vd * c - vq * s;
  float vb = vd * s + vq * c;

  // 6. inverse Clarke -> three phase voltages
  float v_a = va;
  float v_b = -0.5f * va + 0.8660254f * vb;
  float v_c = -0.5f * va - 0.8660254f * vb;

  // 7. SVPWM common-mode zero-sequence injection (D-3 fix: +15.5% bus utilization)
  float v_max_p = (v_a > v_b) ? ((v_a > v_c) ? v_a : v_c) : ((v_b > v_c) ? v_b : v_c);
  float v_min_p = (v_a < v_b) ? ((v_a < v_c) ? v_a : v_c) : ((v_b < v_c) ? v_b : v_c);
  float v_com = -0.5f * (v_max_p + v_min_p);

  float v_a_mod = v_a + v_com;
  float v_b_mod = v_b + v_com;
  float v_c_mod = v_c + v_com;

  // 8. PWM duties (center = ARR/2; +/-vmax maps to full scale)
  float k = (float)PWM3PH_ARR / (2.0f * vmax);
  pwm3ph_set((int32_t)((float)PWM3PH_ARR * 0.5f + v_a_mod * k),
             (int32_t)((float)PWM3PH_ARR * 0.5f + v_b_mod * k),
             (int32_t)((float)PWM3PH_ARR * 0.5f + v_c_mod * k));

  // diagnostic: expose one phase current (Q12 amps approx)
  s_iq_q12 = (int32_t)s_ib;
}

int32_t foc_last_angle(void) { return s_angle_q14; }
int32_t foc_last_iq(void)    { return s_iq_q12; }
uint32_t foc_crc_errors(void){ return s_crc_errors; }

void foc_last_currents(int16_t *a, int16_t *b, int16_t *c)
{
  if (a) *a = s_ia;
  if (b) *b = s_ib;
  if (c) *c = s_ic;
}
