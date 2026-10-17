#include <math.h>
#include <stdio.h>
#include "foc.h"
#include "mt6701.h"
#include "current.h"
#include "pwm3ph.h"
#include "app_io.h"
#include "motion.h"
#include "calibration.h"
#include "control_lock.h"

#define TWO_PI_F 6.28318530718f
#define PI_F 3.14159265359f
#define FOC_LUT_SIZE 256

// A CRC-valid MT6701 frame can still report a transient field-strength or
// overspeed status bit.  Keep steering with the angle, but trip only if the
// status remains abnormal for about 100 ms at the 20 kHz PWM rate.
#define FOC_FIELD_TRIP_COUNT 2000u

// Voltage mode is the default; the inner current loop is enabled at runtime
// (console 'l') only from standby, after the operator has checked the measured
// id/iq polarity in the status frame.
#ifndef FOC_CURRENT_LOOP_DEFAULT
#define FOC_CURRENT_LOOP_DEFAULT 0
#endif

// The ADC clips near 2.75 A at the configured 0.6 V/A gain. Keep the runtime
// trip below the motor's 2.5 A rating with a small margin; this remains a
// software threshold, not a calibrated current limiter.
#ifndef FOC_CURRENT_TRIP_LSB_MAX
#define FOC_CURRENT_TRIP_LSB_MAX 1800
#endif

foc_params_t g_foc;
float g_align_delta;   // 对齐方向探测的 raw 电角度差（rad），诊断用

static float s_sin_lut[FOC_LUT_SIZE + 1];
static mt6701_sample_t s_angle;
static int16_t s_ia, s_ib, s_ic;
static int32_t s_angle_q14;
static uint32_t s_crc_errors;
static uint32_t s_crc_consecutive;
static uint32_t s_field_bad_consecutive;
static uint32_t s_adc_errors;
static uint32_t s_adc_consecutive;
static uint8_t s_angle_valid;
static uint8_t s_adc_seen;
static uint16_t s_isr_div;
static float   s_raw_e_filt;   // 低通后的电角度（换向用，见 foc_step_isr）
static uint8_t s_raw_e_init;

// ---- inner current loop ----
static float s_id_f, s_iq_f;             // filtered field-frame currents (LSB)
static float s_iint_d, s_iint_q;         // PI integrators (modulation LSB float)
static int32_t s_iq_ref;                 // latest q-axis current reference (LSB)
static int16_t s_id_tel, s_iq_tel;       // telemetry snapshots (filtered, LSB)

// ---- over-current discrimination (foc.h foc_oc_t) ----
static int16_t s_pk_a, s_pk_b, s_pk_c;   // signed peaks by |i| since reset
static uint32_t s_oc_events, s_oc_consec, s_oc_max_run, s_oc_glitches;
static uint8_t s_oc_last_mask;           // over phases of the newest over sample
static int16_t s_oc_ring[FOC_OC_SNAP][3];
static uint8_t s_oc_ring_n;              // next write slot in the circular ring
static int16_t s_oc_frozen[FOC_OC_SNAP][3];
static uint8_t s_oc_frozen_n, s_oc_frozen_kind, s_oc_frozen_mask, s_oc_frozen_run;
static char s_oc_msg[64];                // trip text with phase mask and count

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

static inline int32_t imag16(int16_t v) { return v < 0 ? -(int32_t)v : (int32_t)v; }

static void oc_reset_locked(void)
{
  s_pk_a = s_pk_b = s_pk_c = 0;
  s_oc_events = s_oc_consec = s_oc_max_run = s_oc_glitches = 0;
  s_oc_last_mask = 0;
  s_oc_ring_n = 0;
  s_oc_frozen_n = s_oc_frozen_kind = s_oc_frozen_mask = s_oc_frozen_run = 0;
}

// Freeze the circular pre-trip window in chronological order (ISR context).
static void oc_freeze(uint8_t kind, uint8_t mask, uint32_t run)
{
  for (int i = 0; i < FOC_OC_SNAP; ++i) {
    int idx = (s_oc_ring_n + i) % FOC_OC_SNAP;
    s_oc_frozen[i][0] = s_oc_ring[idx][0];
    s_oc_frozen[i][1] = s_oc_ring[idx][1];
    s_oc_frozen[i][2] = s_oc_ring[idx][2];
  }
  s_oc_frozen_n = FOC_OC_SNAP;
  s_oc_frozen_kind = kind;
  s_oc_frozen_mask = mask;
  s_oc_frozen_run = run > 255u ? 255u : (uint8_t)run;
}

void foc_init(uint16_t pole_pairs)
{
  foc_lut_init();
  g_foc.pole_pairs = pole_pairs;
  g_foc.v_limit_q = 8192;   // modulation normalization, not a measured voltage limit
  g_foc.voltage_d_q = 0;
  g_foc.zero_electric_angle = 0.0f;
  g_foc.sensor_direction = 1;
  g_foc.torque_q = 0;
  g_foc.brake = 0;
  g_foc.current_loop = FOC_CURRENT_LOOP_DEFAULT;
  g_foc.cur_kp = 8.0f;          // first guess; tune with the K/I gears
  g_foc.cur_ki = 100.0f;
  g_foc.cur_ref_div = 12;       // 25% torque cap -> 2048/12 ~= 170 LSB ~= 228 mA
  g_foc.cur_filt_alpha = 0.25f; // light LPF on feedback and telemetry
  g_foc.cur_v_cap = 4096;       // 50% modulation output clamp for bring-up
  g_foc.cur_trip_lsb = CURRENT_TRIP_LSB;
  // 换向角低通：1/64 -> 噪声衰减约 0.088 倍，滞后 1.6 ms。设 1.0 可完全关掉
  // （串口 'q' 键循环切换，用于 A/B 对比）。
  g_foc.angle_filt_alpha = 1.0f / 64.0f;
  g_foc.comm_override = 0;      // 默认走编码器换向；motion 层按需接管
  g_foc.comm_angle_e = 0.0f;
  s_raw_e_init = 0;
  s_crc_errors = 0;
  s_crc_consecutive = 0;
  s_adc_errors = 0;
  s_adc_consecutive = 0;
  s_angle_valid = 0;
  s_adc_seen = 0;
  s_isr_div = 0;
  s_angle_q14 = 0;
  s_ia = s_ib = s_ic = 0;
  s_id_f = s_iq_f = 0.0f;
  s_iint_d = s_iint_q = 0.0f;
  s_iq_ref = 0;
  s_id_tel = s_iq_tel = 0;
  oc_reset_locked();
}

static int32_t clamp_i32(int32_t v, int32_t lim)
{
  if (v > lim) return lim;
  if (v < -lim) return -lim;
  return v;
}

// Take a circular mean in electrical-angle space. A plain integer average is
// wrong when the encoder samples straddle the 0/16383 wrap boundary.
static int sample_electric_angle(float *angle)
{
  float x = 0.0f;
  float y = 0.0f;
  int valid = 0;
  for (int i = 0; i < 32; ++i) {
    mt6701_sample_t sample;
    if (mt6701_read(&sample)) {
      float a = TWO_PI_F *
          (float)(((uint32_t)sample.angle * g_foc.pole_pairs) & 0x3FFFu) / 16384.0f;
      x += cosf(a);
      y += sinf(a);
      ++valid;
    }
    delay_ms(2);
  }
  if (valid < 24 || x * x + y * y < (float)(valid * valid) * 0.75f) return 0;
  *angle = atan2f(y, x);
  if (*angle < 0.0f) *angle += TWO_PI_F;
  return 1;
}

// P1-1 fix: open-loop d-axis alignment -> zero electrical angle + direction.
// The alignment vector is derived from v_limit so it can never saturate the
// CCRs (a saturated space vector mis-zeros the calibration).
int foc_align_sensor(void)
{
  float vmax = (float)g_foc.v_limit_q / 4096.0f;
  if (vmax < 0.5f) vmax = 0.5f;
  float k = (float)PWM3PH_ARR / (2.0f * vmax);
  float v_align = 0.2f * vmax;   // respect the 20% motion voltage cap during alignment

  // Electrical angle 0 vector: (cos0, cos(-120deg), cos(+120deg))
  pwm3ph_set((int32_t)((float)PWM3PH_ARR * 0.5f + 1.0f * v_align * k),
             (int32_t)((float)PWM3PH_ARR * 0.5f - 0.5f * v_align * k),
             (int32_t)((float)PWM3PH_ARR * 0.5f - 0.5f * v_align * k));
  pwm3ph_outputs(1);
  drv_inl_high();
  delay_ms(400);                 // let the rotor snap to the d axis

  float zero;
  if (!sample_electric_angle(&zero)) {
    pwm3ph_set(0, 0, 0);
    drv_inl_low();
    pwm3ph_outputs(0);
    return 0;
  }

  // Direction probe: step the applied vector to electrical +90deg. If the
  // sensor's raw electrical angle then reads +90 (not -90 wrapped), the sensor
  // tracks the applied sequence positively; a negative-feedback sensor would
  // make the voltage loop run away, so catch it here, not on the bench.
  pwm3ph_set((int32_t)((float)PWM3PH_ARR * 0.5f + 0.0f * v_align * k),
             (int32_t)((float)PWM3PH_ARR * 0.5f + 0.866f * v_align * k),
             (int32_t)((float)PWM3PH_ARR * 0.5f - 0.866f * v_align * k));
  delay_ms(300);

  float probe_raw;
  int probe_ok = sample_electric_angle(&probe_raw);
  pwm3ph_set(0, 0, 0);           // release: all-low = brake state in 3x mode
  drv_inl_low();
  pwm3ph_outputs(0);
  if (!probe_ok) return 0;
  float delta = probe_raw - zero;
  while (delta < 0.0f)      delta += TWO_PI_F;
  while (delta >= TWO_PI_F) delta -= TWO_PI_F;
  // Accept +/-90 degrees with a 45-degree window; reject an unmoved rotor.
  g_align_delta = delta;
  if (delta > TWO_PI_F * 0.125f && delta < TWO_PI_F * 0.375f) {
    g_foc.sensor_direction = 1;
  } else if (delta > TWO_PI_F * 0.625f && delta < TWO_PI_F * 0.875f) {
    g_foc.sensor_direction = -1;
  } else {
    return 0;
  }
  g_foc.zero_electric_angle = zero;
  return 1;
}

// Voltage-mode FOC step (runs in the GPTIMER0 update ISR = PWM valley):
// currents + angle are sampled first so phase and current share one instant,
// then inverse Park + Clarke + SVPWM injection produce the three duties.
void foc_step_isr(void)
{
  // 1. low-side-synchronous current sampling.  The PWM update ISR is gated to
  //    the peak (INHx low) edge where the low-side shunts are valid. Full rate
  //    whenever the bridge is
  //    armed: the current-loop PI and the N-consecutive OC discriminator both
  //    consume every PWM update. Idle stays at 1/16 rate (P2-3).
  int armed = pwm3ph_enabled();
  int cur_ok = 0;
  if (armed || (s_isr_div++ & 0x0Fu) == 0) {
    current_trigger();
    if (!current_read_raw(&s_ia, &s_ib, &s_ic)) {
      ++s_adc_errors;
      ++s_adc_consecutive;
    } else {
      s_adc_consecutive = 0;
      s_adc_seen = 1;
      cur_ok = 1;
    }
  }
  if (armed && cur_ok) {
    s_oc_ring[s_oc_ring_n][0] = s_ia;
    s_oc_ring[s_oc_ring_n][1] = s_ib;
    s_oc_ring[s_oc_ring_n][2] = s_ic;
    s_oc_ring_n = (uint8_t)((s_oc_ring_n + 1) % FOC_OC_SNAP);
    if (imag16(s_ia) > imag16(s_pk_a)) s_pk_a = s_ia;
    if (imag16(s_ib) > imag16(s_pk_b)) s_pk_b = s_ib;
    if (imag16(s_ic) > imag16(s_pk_c)) s_pk_c = s_ic;
  }

  // 2. angle (24 clocks at 3.125MHz, CRC6 verified)
  mt6701_sample_t sample;
  if (mt6701_read(&sample)) {
    s_angle = sample;
    s_angle_valid = 1;
    s_crc_consecutive = 0;
    if (sample.mg & 0x0bu) {
      // Do not abort on a transient field/overspeed status bit. The angle is
      // still CRC-valid, so use it and require a sustained fault to trip.
      ++s_field_bad_consecutive;
    } else {
      s_field_bad_consecutive = 0;
    }
  } else {
    ++s_crc_errors;         // drop frame, keep last good angle
    ++s_crc_consecutive;
  }
  if (!s_angle_valid) {
    pwm3ph_set(0, 0, 0);
    return;
  }
  s_angle_q14 = s_angle.angle;

  // Count-based protection, not calibrated current regulation. Full-rate
  // sampling while energized bounds software reaction to one PWM update.
  if (armed) {
    if (!current_calibrated() || s_adc_consecutive) {
      motion_trip("ADC timeout"); return;
    }
    if (!foc_angle_valid() || s_field_bad_consecutive >= FOC_FIELD_TRIP_COUNT) {
      motion_trip("encoder invalid/field"); return;
    }
  }
  // Over-current discrimination (foc.h): trip only after FOC_OC_TRIP_COUNT
  // consecutive full-rate samples over CURRENT_TRIP_LSB, and freeze the window
  // around the event. Isolated over-threshold samples are counted as glitches
  // (peak-captured, snapshotted) instead of aborting the move on one bad read.
  if (armed && cur_ok) {
    int32_t trip_lsb = g_foc.cur_trip_lsb;
    if (trip_lsb < CURRENT_TRIP_LSB) trip_lsb = CURRENT_TRIP_LSB;
    if (trip_lsb > FOC_CURRENT_TRIP_LSB_MAX) trip_lsb = FOC_CURRENT_TRIP_LSB_MAX;
    uint8_t mask = 0u;
    if (s_ia > trip_lsb || s_ia < -trip_lsb) mask |= 1u;
    if (s_ib > trip_lsb || s_ib < -trip_lsb) mask |= 2u;
    if (s_ic > trip_lsb || s_ic < -trip_lsb) mask |= 4u;
    if (mask) {
      s_oc_last_mask = mask;
      ++s_oc_events;
      ++s_oc_consec;
      if (s_oc_consec > s_oc_max_run) s_oc_max_run = s_oc_consec;
      if (s_oc_consec >= FOC_OC_TRIP_COUNT) {
        oc_freeze(2u, mask, s_oc_consec);
        snprintf(s_oc_msg, sizeof s_oc_msg, "current ADC threshold %s%s%s n=%u",
                 (mask & 1u) ? "A" : "", (mask & 2u) ? "B" : "",
                 (mask & 4u) ? "C" : "", (unsigned)s_oc_consec);
        motion_trip(s_oc_msg);
        return;
      }
    } else if (s_oc_consec) {
      if (s_oc_consec == 1u) {
        ++s_oc_glitches;
        oc_freeze(1u, s_oc_last_mask, 1u);
      }
      s_oc_consec = 0;
    }
  }

  if (g_foc.brake) {
    pwm3ph_set(0, 0, 0);    // all low = brake state in 3x mode
    return;
  }

  // 3. electrical angle with calibrated zero-offset
  float raw_e = TWO_PI_F * (float)(((uint32_t)s_angle.angle * g_foc.pole_pairs) & 0x3FFFu)
                / 16384.0f;
  // Circular first-order filter in electrical-angle space.
  {
    float a = g_foc.angle_filt_alpha;
    if (!(a > 0.0f && a < 1.0f)) { // invalid alpha or direct path
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
      if (s_raw_e_filt < 0.0f) s_raw_e_filt += TWO_PI_F;
      if (s_raw_e_filt >= TWO_PI_F) s_raw_e_filt -= TWO_PI_F;
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

  // 4. field-frame currents from the measured phases, using the same angle
  //    that will drive the inverse Park. Always measured (telemetry + loop).
  float c, s;
  foc_fast_sincos(ang_e, &s, &c);
  {
    float i_alpha = (float)s_ia;
    float i_beta  = ((float)s_ia + 2.0f * (float)s_ib) * 0.57735026919f;
    float id_m =  i_alpha * c + i_beta * s;
    float iq_m = -i_alpha * s + i_beta * c;
    float a = g_foc.cur_filt_alpha;
    if (a > 0.0f && a < 1.0f) {
      s_id_f += a * (id_m - s_id_f);
      s_iq_f += a * (iq_m - s_iq_f);
    } else {
      s_id_f = id_m;
      s_iq_f = iq_m;
    }
    s_id_tel = (int16_t)s_id_f;
    s_iq_tel = (int16_t)s_iq_f;
  }

  // 5. control law: inner current-loop PI when enabled and armed; direct
  //    voltage command (voltage mode, unchanged behavior) otherwise.
  float vq, vd;
  if (g_foc.current_loop && armed && !calibration_active()) {
    int32_t div = g_foc.cur_ref_div > 0 ? g_foc.cur_ref_div : 1;
    int32_t ref = g_foc.torque_q / div;
    s_iq_ref = ref;
    float cap = (float)g_foc.cur_v_cap;
    if (cap < 1.0f) cap = 1.0f;
    float eq = (float)ref - s_iq_f;
    float ed = -s_id_f;
    float vq_out = g_foc.cur_kp * eq + s_iint_q;
    float vd_out = g_foc.cur_kp * ed + s_iint_d;
    if (vq_out >  cap) vq_out =  cap;
    if (vq_out < -cap) vq_out = -cap;
    if (vd_out >  cap) vd_out =  cap;
    if (vd_out < -cap) vd_out = -cap;
    // Conditional integration: anti-windup against the output clamp.
    if (!((vq_out >=  cap && eq > 0.0f) || (vq_out <= -cap && eq < 0.0f)))
      s_iint_q += g_foc.cur_ki * eq / (float)PWM3PH_FREQ_HZ;
    if (!((vd_out >=  cap && ed > 0.0f) || (vd_out <= -cap && ed < 0.0f)))
      s_iint_d += g_foc.cur_ki * ed / (float)PWM3PH_FREQ_HZ;
    if (s_iint_q >  cap) s_iint_q =  cap;
    if (s_iint_q < -cap) s_iint_q = -cap;
    if (s_iint_d >  cap) s_iint_d =  cap;
    if (s_iint_d < -cap) s_iint_d = -cap;
    vq = vq_out / 4096.0f;
    vd = vd_out / 4096.0f;
  } else {
    s_iint_d = s_iint_q = 0.0f;   // no windup when disarmed or in voltage mode
    s_iq_ref = 0;
    vq = (float)clamp_i32(g_foc.torque_q, g_foc.v_limit_q) / 4096.0f;
    vd = (float)clamp_i32(g_foc.voltage_d_q, g_foc.v_limit_q) / 4096.0f;
  }
  float vmax = (float)g_foc.v_limit_q / 4096.0f;
  if (vmax < 0.01f) {
    vmax = 0.01f;
  }

  // 6. inverse Park (D-2 fix, c/s from step 4)
  float va = vd * c - vq * s;
  float vb = vd * s + vq * c;

  // 7. inverse Clarke -> three phase voltages
  float v_a = va;
  float v_b = -0.5f * va + 0.8660254f * vb;
  float v_c = -0.5f * va - 0.8660254f * vb;

  // 8. SVPWM common-mode zero-sequence injection (D-3 fix: +15.5% bus utilization)
  float v_max_p = (v_a > v_b) ? ((v_a > v_c) ? v_a : v_c) : ((v_b > v_c) ? v_b : v_c);
  float v_min_p = (v_a < v_b) ? ((v_a < v_c) ? v_a : v_c) : ((v_b < v_c) ? v_b : v_c);
  float v_com = -0.5f * (v_max_p + v_min_p);

  float v_a_mod = v_a + v_com;
  float v_b_mod = v_b + v_com;
  float v_c_mod = v_c + v_com;

  // 9. PWM duties (center = ARR/2; +/-vmax maps to full scale)
  float k = (float)PWM3PH_ARR / (2.0f * vmax);
  pwm3ph_set((int32_t)((float)PWM3PH_ARR * 0.5f + v_a_mod * k),
             (int32_t)((float)PWM3PH_ARR * 0.5f + v_b_mod * k),
             (int32_t)((float)PWM3PH_ARR * 0.5f + v_c_mod * k));

}

int32_t foc_last_angle(void) { return s_angle_q14; }
uint32_t foc_crc_errors(void){ return s_crc_errors; }
uint32_t foc_crc_consecutive(void) { return s_crc_consecutive; }
uint32_t foc_adc_errors(void) { return s_adc_errors; }
uint32_t foc_adc_consecutive(void) { return s_adc_consecutive; }
int foc_angle_valid(void) { return s_angle_valid && !s_crc_consecutive; }
int foc_current_valid(void) { return s_adc_seen && !s_adc_consecutive; }
uint8_t foc_sensor_status(void) { return s_angle.mg; }
void foc_clear_sensor_faults(void)
{
  s_crc_consecutive = 0;
  s_adc_consecutive = 0;
  s_raw_e_init = 0;
}

void foc_last_currents(int16_t *a, int16_t *b, int16_t *c)
{
  if (a) *a = s_ia;
  if (b) *b = s_ib;
  if (c) *c = s_ic;
}

void foc_oc_reset(void)
{
  uint32_t key = control_lock();
  oc_reset_locked();
  control_unlock(key);
}

void foc_oc_get(foc_oc_t *out)
{
  if (!out) return;
  uint32_t key = control_lock();
  out->pk_a = s_pk_a;
  out->pk_b = s_pk_b;
  out->pk_c = s_pk_c;
  out->events = s_oc_events;
  out->max_run = s_oc_max_run;
  out->glitches = s_oc_glitches;
  out->last_a = s_ia;
  out->last_b = s_ib;
  out->last_c = s_ic;
  out->snap_kind = s_oc_frozen_kind;
  out->snap_mask = s_oc_frozen_mask;
  out->snap_run = s_oc_frozen_run;
  out->snap_n = s_oc_frozen_n;
  for (int i = 0; i < FOC_OC_SNAP; ++i) {
    out->snap[i][0] = s_oc_frozen[i][0];
    out->snap[i][1] = s_oc_frozen[i][1];
    out->snap[i][2] = s_oc_frozen[i][2];
  }
  control_unlock(key);
}

void foc_current_loop_enable(int on)
{
  uint32_t key = control_lock();
  g_foc.current_loop = on ? 1u : 0u;
  s_iint_d = s_iint_q = 0.0f;   // never resume with a stale integrator
  control_unlock(key);
}

int foc_current_loop_enabled(void) { return g_foc.current_loop; }

void foc_current_limit_set(int32_t trip_lsb, int32_t v_cap)
{
  uint32_t key = control_lock();
  if (trip_lsb < CURRENT_TRIP_LSB) trip_lsb = CURRENT_TRIP_LSB;
  if (trip_lsb > FOC_CURRENT_TRIP_LSB_MAX) trip_lsb = FOC_CURRENT_TRIP_LSB_MAX;
  if (v_cap < 512) v_cap = 512;
  if (v_cap > g_foc.v_limit_q) v_cap = g_foc.v_limit_q;
  g_foc.cur_trip_lsb = trip_lsb;
  g_foc.cur_v_cap = v_cap;
  control_unlock(key);
}

void foc_last_dq(int16_t *d, int16_t *q)
{
  if (d) *d = s_id_tel;
  if (q) *q = s_iq_tel;
}

int32_t foc_last_iq_ref(void) { return s_iq_ref; }
