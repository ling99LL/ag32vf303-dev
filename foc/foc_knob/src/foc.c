#include "alta.h"
#include "foc_knob.h"
#include "foc.h"
#include "pwm3ph.h"
#include "driver.h"
#include "hall.h"
#include "util.h"
#include <math.h>

#define SIN_N 256
static float s_sin_tab[SIN_N + 1];

static volatile bool s_enabled = false;
static volatile bool s_fault_latched = false;
static volatile uint32_t s_loop_count = 0;
static uint32_t s_last_us;

void foc_init(void)
{
  for (int i = 0; i <= SIN_N; i++)
    s_sin_tab[i] = sinf((float)(2.0 * M_PI) * (float)i / (float)SIN_N);
  s_last_us = UTIL_GetUSec();
}

// theta: any float [rad]; table + linear interpolation, <<0.01deg error
static void foc_sincos(float theta, float *so, float *co)
{
  float t = theta * ((float)SIN_N * (float)(1.0 / (2.0 * M_PI)));
  t -= (float)SIN_N * floorf(t * (1.0f / (float)SIN_N));
  int i0 = (int)t;
  float f = t - (float)i0;
  *so = s_sin_tab[i0] + f * (s_sin_tab[i0 + 1] - s_sin_tab[i0]);
  int ic = i0 + SIN_N / 4;                  // cos = sin shifted by 90deg
  *co = s_sin_tab[ic & (SIN_N - 1)];
}

// inverse Park (Ud = 0) + SVPWM via min-max injection; uq in volts.
// Uq vector goes 90deg elec AHEAD of theta_e (q-axis): applying it AT theta_e
// is pure d-axis = zero torque, rotor just locks to the field.
void foc_apply(float theta_e, float uq)
{
  float s, c;
  foc_sincos(theta_e, &s, &c);
  float ualpha = -uq * s;
  float ubeta  =  uq * c;

  float umag = sqrtf(ualpha * ualpha + ubeta * ubeta);
  const float umax = VBUS_VOLTAGE * 0.57735027f;   // Udc / sqrt(3)
  if (umag > umax && umag > 1e-6f) {
    float k = umax / umag;
    ualpha *= k;
    ubeta  *= k;
  }

  // phase voltages from inverse Clarke
  float u1 = ualpha;
  float u2 = -0.5f * ualpha + 0.8660254f * ubeta;
  float u3 = -0.5f * ualpha - 0.8660254f * ubeta;
  float vmax = u1 > u2 ? (u1 > u3 ? u1 : u3) : (u2 > u3 ? u2 : u3);
  float vmin = u1 < u2 ? (u1 < u3 ? u1 : u3) : (u2 < u3 ? u2 : u3);
  float cm = -(vmax + vmin) * 0.5f;                // common-mode injection
  pwm3ph_set_duty((u1 + cm) / VBUS_VOLTAGE + 0.5f,
                  (u2 + cm) / VBUS_VOLTAGE + 0.5f,
                  (u3 + cm) / VBUS_VOLTAGE + 0.5f);
}

void foc_zero(void) { pwm3ph_set_duty(0.5f, 0.5f, 0.5f); }

void foc_set_enabled(bool en)  { s_enabled = en; }
bool foc_enabled(void)         { return s_enabled; }
bool foc_fault_latched(void)   { return s_fault_latched; }
void foc_clear_fault(void)     { s_fault_latched = false; }
uint32_t foc_loop_count(void)  { return s_loop_count; }

// ---------------- non-blocking open-loop rotation ('rot' pre-cal) ----------
static struct {
  volatile bool  active;
  volatile bool  done;
  volatile float th;       // commanded electrical angle [rad]
  volatile float rate;     // signed electrical slew [rad/s]
  volatile float remain;   // electrical radians still to traverse
  volatile float uq;       // drag voltage [V]
} s_ol;

void foc_ol_start(float total_e_rad, float rate_e_rad_s, float uq_volt)
{
  s_ol.th     = 0.0f;
  s_ol.rate   = rate_e_rad_s;
  s_ol.remain = total_e_rad > 0.0f ? total_e_rad : 0.0f;
  s_ol.uq     = uq_volt;
  s_ol.done   = false;
  s_ol.active = true;
}

bool foc_ol_active(void) { return s_ol.active; }
void foc_ol_abort(void)  { s_ol.active = false; }

bool foc_ol_pop_done(void)
{
  if (!s_ol.done) return false;
  s_ol.done = false;
  return true;
}

// ---------------- FOC main loop: GPTIMER0 update interrupt ----------------

// overrides the weak symbol in the SDK ISR table (framework-agrv_sdk/interrupt.c)
void GPTIMER0_isr(void)
{
  foc_loop_irq();
}

void foc_loop_irq(void)
{
  GPTIMER_ClearFlagUpdate(GPTIMER0);
  s_loop_count++;

  uint32_t now = UTIL_GetUSec();
  uint32_t d_us = now - s_last_us;
  s_last_us = now;
  float dt = (float)d_us * 1e-6f;
  // center-aligned timers may update at both triangle ends; measuring dt makes
  // the loop rate-agnostic (20 or 40 kHz both work correctly)
  if (dt < 1e-5f || dt > 2e-2f) dt = 2.5e-5f;

  hall_update(dt);

  if (driver_sleeping()) {
    foc_zero();
    return;
  }
  if (driver_fault()) {
    // latched: outputs stay off until 'cl' command clears it
    pwm3ph_outputs_enable(false);
    foc_zero();
    s_fault_latched = true;
    return;
  }
  if (s_ol.active) {          // open-loop drag: no halls needed, keep stepping
    float adv = s_ol.rate * dt;
    s_ol.th += adv;
    s_ol.remain -= (adv < 0.0f) ? -adv : adv;
    foc_apply(s_ol.th, s_ol.uq);
    g_knob_uq = s_ol.uq;
    if (s_ol.remain <= 0.0f) {
      s_ol.active = false;
      s_ol.done   = true;
    }
    return;
  }
  if (!hall_state_valid()) {   // transient glitch: no torque this pass
    foc_zero();
    return;
  }
  if (!s_enabled) {
    foc_zero();
    return;
  }

  float uq = knob_compute_uq(hall_mech_angle(), hall_mech_velocity(), dt);
  if (g_knob_th_valid) foc_apply(g_knob_th, uq);   // rot drag: own field angle
  else                 foc_apply(hall_electrical_angle(), uq);
}
