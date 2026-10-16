#include <math.h>
#include "calibration.h"
#include "control.h"
#include "control_lock.h"
#include "foc.h"
#include "motion.h"
#include "pwm3ph.h"
#include "current.h"
#include "interrupt.h"

#define PI_F 3.14159265359f
#define TWO_PI_F (2.0f * PI_F)
static volatile int s_stage;
static uint32_t s_hz = 20000u, s_ticks, s_host_ticks, s_peak;
static unsigned s_samples;
static float s_x, s_y, s_zero;

int calibration_active(void) { return s_stage >= 1 && s_stage <= 6; }
int calibration_stage(void) { return s_stage; }
uint32_t calibration_peak(void) { return s_peak; }
void calibration_set_rate(uint32_t hz) { if (hz >= 1000u) s_hz = hz; }
void calibration_keepalive(void) { s_host_ticks = 0; }

static void finish(int result)
{
  pwm3ph_release();
  g_foc.voltage_d_q = g_foc.torque_q = 0;
  g_foc.comm_override = 0;
  s_stage = result;
  if (result != 7) control_set_aligned(0);
}
void calibration_cancel(void)
{
  uint32_t key = control_lock();
  if (calibration_active()) finish(8);
  control_unlock(key);
}
static void fail(const char *why)
{
  finish(9);
  motion_trip(why);
}
int calibration_start(void)
{
  if (!control_calibration_ready()) return 0;
  // Re-zero with INL/MOE off. Only the PWM ISR owns these ADCs otherwise.
  INT_DisableIRQ(GPTIMER0_IRQn);
  motion_stop();
  int ok = current_init();
  INT_EnableIRQ(GPTIMER0_IRQn, 1);
  if (!ok) { motion_trip("calibration ADC zero"); return 0; }
  uint32_t key = control_lock();
  if (!control_calibration_ready()) { control_unlock(key); return 0; }
  control_set_aligned(0);
  s_ticks = s_host_ticks = s_peak = 0;
  s_samples = 0; s_x = s_y = 0;
  g_foc.comm_override = 1;
  g_foc.comm_angle_e = 0;
  g_foc.voltage_d_q = g_foc.torque_q = 0;
  s_stage = 1;
  if (!pwm3ph_arm()) fail("driver break");
  ok = calibration_active();
  control_unlock(key);
  return ok;
}
static void next(int stage)
{
  s_stage = stage; s_ticks = 0; s_samples = 0; s_x = s_y = 0;
}
static int mean(float *result)
{
  if (s_samples < 32 || s_x*s_x+s_y*s_y < s_samples*s_samples*0.90f) return 0;
  *result = atan2f(s_y, s_x);
  if (*result < 0) *result += TWO_PI_F;
  return 1;
}
void calibration_step_isr(void)
{
  if (!calibration_active()) return;
  if (motion_state() == MOTION_FAULT) { finish(9); return; }
  // A host query normally refreshes this watchdog; leave five seconds for a
  // direct serial operator to issue the start command before requiring a new
  // status query or an explicit stop.
  if (++s_host_ticks > s_hz*5u) { fail("calibration link timeout"); return; }
  if (!foc_angle_valid() || (foc_sensor_status() & 0x0bu)) {
    fail("calibration encoder"); return;
  }
  int16_t ia, ib, ic; foc_last_currents(&ia, &ib, &ic);
  int32_t currents[3] = {ia, ib, ic};
  for (int i=0; i<3; ++i) {
    uint32_t mag = (uint32_t)(currents[i] < 0 ? -currents[i] : currents[i]);
    if (mag > s_peak) s_peak = mag;
  }
  uint32_t ticks = ++s_ticks;
  int32_t amplitude = g_foc.v_limit_q * CALIBRATION_PCT / 100;
  if (s_stage == 1) {
    g_foc.voltage_d_q = (int32_t)((int64_t)amplitude * ticks / (s_hz/10u));
    if (ticks >= s_hz/10u) { g_foc.voltage_d_q = amplitude; next(2); }
  } else if (s_stage == 2) {
    if (ticks >= s_hz*3u/10u) next(3);
  } else if (s_stage == 4) {
    // One second for 90 electrical degrees: 2.14 mechanical rpm at 7 pairs.
    g_foc.comm_angle_e = PI_F * 0.5f * ticks / s_hz;
    if (ticks >= s_hz) { g_foc.comm_angle_e = PI_F * 0.5f; next(5); }
  } else if (s_stage == 5) {
    if (ticks >= s_hz*15u/100u) next(6);
  } else if (ticks % (s_hz/500u) == 0) {
    float a = TWO_PI_F * (float)(((uint32_t)foc_last_angle()*g_foc.pole_pairs)&16383u)/16384.0f;
    s_x += cosf(a); s_y += sinf(a); ++s_samples;
    if (s_samples == 32) {
      float angle;
      if (!mean(&angle)) { fail("calibration unstable"); return; }
      if (s_stage == 3) { s_zero = angle; next(4); }
      else {
        float delta = angle-s_zero;
        if (delta < 0) delta += TWO_PI_F;
        g_align_delta = delta;
        int direction = delta > PI_F*.25f && delta < PI_F*.75f ? 1 :
                        delta > PI_F*1.25f && delta < PI_F*1.75f ? -1 : 0;
        if (!direction) { fail("calibration no movement"); return; }
        g_foc.zero_electric_angle = s_zero;
        g_foc.sensor_direction = direction;
        finish(7); control_set_aligned(1);
      }
    }
  }
}
