#include <math.h>
#include "foc.h"
#include "mt6701.h"
#include "current.h"
#include "pwm3ph.h"

#define TWO_PI_F 6.28318530718f
#define FOC_LUT_SIZE 256

foc_params_t g_foc;

static float s_sin_lut[FOC_LUT_SIZE + 1];
static mt6701_sample_t s_angle;
static int16_t s_ia, s_ib, s_ic;
static int32_t s_angle_q14;
static int32_t s_iq_q12;
static uint32_t s_crc_errors;
static uint16_t s_isr_div;

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
  g_foc.sensor_direction = (delta < TWO_PI_F * 0.25f || delta > TWO_PI_F * 0.75f) ? 1 : -1;
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
  float ang_e = (raw_e - g_foc.zero_electric_angle) * (float)g_foc.sensor_direction;
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
