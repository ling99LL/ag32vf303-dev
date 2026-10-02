#include <math.h>
#include "foc.h"
#include "mt6701.h"
#include "current.h"
#include "pwm3ph.h"

#define TWO_PI_F 6.28318530718f

foc_params_t g_foc;

static mt6701_sample_t s_angle;
static int16_t s_ia, s_ib, s_ic;
static int32_t s_angle_q14;
static int32_t s_iq_q12;
static uint32_t s_crc_errors;

void foc_init(uint16_t pole_pairs)
{
  g_foc.pole_pairs = pole_pairs;
  g_foc.v_limit_q = 3000;   // Q12 volts, placeholder until Vbus scaling lands
  g_foc.id_ref_q = 0;
  g_foc.iq_ref_q = 0;
  g_foc.kp_q = 4096;
  g_foc.ki_q = 64;
  g_foc.torque_q = 0;
  g_foc.brake = 0;
}

static int32_t clamp_i32(int32_t v, int32_t lim)
{
  if (v > lim) return lim;
  if (v < -lim) return -lim;
  return v;
}

// Voltage-mode FOC step (runs in the GPTIMER0 update ISR = PWM valley):
// currents + angle are sampled first so phase and current share one instant,
// then inverse Park + Clarke produce the three SPWM duties.
void foc_step_isr(void)
{
  // 1. quasi-simultaneous current sample (all three STARTs within ~60ns)
  current_trigger();
  current_read_raw(&s_ia, &s_ib, &s_ic);

  // 2. angle (SSI frame = 1.92us @12.5MHz, CRC6 verified)
  if (!mt6701_read(&s_angle)) {
    ++s_crc_errors;         // drop frame, keep last good angle
  }
  s_angle_q14 = s_angle.angle;

  if (g_foc.brake) {
    pwm3ph_set(0, 0, 0);    // all low = brake state in 3x mode
    return;
  }

  // 3. electrical angle
  float ang_e = TWO_PI_F * (float)(((uint32_t)s_angle.angle * g_foc.pole_pairs) & 0x3FFFu)
                / 16384.0f;

  // 4. q-axis voltage = torque command from the hand-feel layer, d-axis = 0
  float vq = (float)clamp_i32(g_foc.torque_q, g_foc.v_limit_q) / 4096.0f;
  float vd = (float)g_foc.id_ref_q / 4096.0f;
  float vmax = (float)g_foc.v_limit_q / 4096.0f;
  if (vmax < 0.01f) {
    vmax = 0.01f;
  }

  // 5. inverse Park
  float c = cosf(ang_e);
  float s = sinf(ang_e);
  float va = vd * c - vq * s;
  float vb = vd * s + vq * c;

  // 6. inverse Clarke -> three phase voltages
  float v_a = va;
  float v_b = -0.5f * va + 0.8660254f * vb;
  float v_c = -0.5f * va - 0.8660254f * vb;

  // 7. SPWM duties (center = ARR/2; +/-vmax maps to full scale)
  float k = (float)PWM3PH_ARR / (2.0f * vmax);
  pwm3ph_set((int32_t)((float)PWM3PH_ARR * 0.5f + v_a * k),
             (int32_t)((float)PWM3PH_ARR * 0.5f + v_b * k),
             (int32_t)((float)PWM3PH_ARR * 0.5f + v_c * k));

  // diagnostic: expose one phase current (Q12 amps approx)
  s_iq_q12 = (int32_t)s_ib;
}

int32_t foc_last_angle(void) { return s_angle_q14; }
int32_t foc_last_iq(void)    { return s_iq_q12; }
