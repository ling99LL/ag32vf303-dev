#include "pwm3ph.h"
#include "gptimer.h"
#include "interrupt.h"
#include "app_io.h"

static void (*s_update_isr)(void);
volatile uint32_t g_pwm_release_diag[6];

// Measured 2026-10-16: this GPTIMER raises BIF on the MOE 1->0 write itself,
// even with INL low (driver Hi-Z) and nFAULT high, so every deliberate release
// looked like "driver break". Keep the real event in software instead: latch a
// flag that was already set before our own write, and mask the one our write
// creates. A break during operation (MOE on) still trips through the ISR.
static volatile int s_break_latch;
static volatile int s_release_window;

void pwm3ph_init(void)
{
  // CR1: center-aligned mode 3 (up/down), ARR preload on.
  // P1-3: update events fire at BOTH overflow and underflow in this mode
  // (40kHz for 20kHz PWM). We do NOT use RCR to thin them out: which edge
  // RCR=1 lands on depends on enable order, and picking the wrong one would
  // drop every valley. The ISR gates on the counter position instead.
  GPTIMER0->PSC  = 0;
  GPTIMER0->ARR  = PWM3PH_ARR;
  GPTIMER0->CR1  = (0x3u << GPTIMER_CR1_CMS_OFFSET) | GPTIMER_CR1_ARPE;

  // CCMR: PWM1 mode (OCxM = 110) + OCx preload on CH0/1/2
  GPTIMER0->CCMR0 = (0x6u << GPTIMER_CCMR_OC0M_OFFSET) | GPTIMER_CCMR0_OC0PE |
                    (0x6u << 12)                      | GPTIMER_CCMR0_OC1PE;
  GPTIMER0->CCMR1 = (0x6u << GPTIMER_CCMR_OC0M_OFFSET) | GPTIMER_CCMR0_OC0PE;

  // CCER: enable CH0/1/2 outputs, active high
  GPTIMER0->CCER = GPTIMER_CCER_CC0E | GPTIMER_CCER_CC1E | GPTIMER_CCER_CC2E;

  // Start at 0% (output low = all low-side on = safe brake state in 3x mode)
  GPTIMER0->CCR0 = 0;
  GPTIMER0->CCR1 = 0;
  GPTIMER0->CCR2 = 0;

  // BDTR: OSSI=1 (MOE off -> outputs driven low), brake enabled, low-active
  // (nFAULT), digital filter FDIV4_N6, DTG=0 (driver does the dead time)
  GPTIMER0->BDTR = GPTIMER_BDTR_OSSI | GPTIMER_BDTR_BKE |
                   (0x6u << GPTIMER_BDTR_BKF_OFFSET);

  GPTIMER0->CNT = 0;
  GPTIMER_GenerateEventUpdate(GPTIMER0); // latch PSC/ARR/CCRs
}

void pwm3ph_outputs(int on)
{
  if (on) {
    if (pwm3ph_faulted()) return;
    GPTIMER0->BDTR |= GPTIMER_BDTR_MOE;
    GPTIMER_EnableCounter(GPTIMER0);
  } else {
    // A flag already set here is a real break event; remember it, because the
    // MOE 1->0 write below sets BIF by itself on this part.
    if (GPTIMER_IsActiveFlagBreak(GPTIMER0)) s_break_latch = 1;
    s_release_window = 1;
    GPTIMER0->BDTR &= ~GPTIMER_BDTR_MOE;
    GPTIMER_ClearFlagBreak(GPTIMER0);
    s_release_window = 0;
  }
}

int pwm3ph_faulted(void)
{
  if (s_break_latch) return 1;
  if (s_release_window) return 0;
  return GPTIMER_IsActiveFlagBreak(GPTIMER0);
}
int pwm3ph_enabled(void) { return !!(GPTIMER0->BDTR & GPTIMER_BDTR_MOE); }
void pwm3ph_ack_break(void)
{
  s_break_latch = 0;
  GPTIMER_ClearFlagBreak(GPTIMER0);
}
void pwm3ph_release(void)
{
  int was_on = pwm3ph_enabled();
  if (was_on) {
    g_pwm_release_diag[0] = GPTIMER0->SR;
    g_pwm_release_diag[3] = GPIO_GetValue(GPIO4, 0xff);
    g_pwm_release_diag[5] = GPTIMER0->BDTR;
  }
  drv_inl_low();
  if (was_on) g_pwm_release_diag[1] = GPTIMER0->SR;
  pwm3ph_outputs(0);
  if (was_on) {
    g_pwm_release_diag[2] = GPTIMER0->SR;
    g_pwm_release_diag[4] = GPIO_GetValue(GPIO4, 0xff);
  }
}
void pwm3ph_prepare(void)
{
  pwm3ph_set(PWM3PH_ARR / 2, PWM3PH_ARR / 2, PWM3PH_ARR / 2);
  GPTIMER_GenerateEventUpdate(GPTIMER0);
  GPTIMER_ClearFlagUpdate(GPTIMER0);
}
int pwm3ph_arm(void)
{
  pwm3ph_release();
  if (pwm3ph_faulted()) return 0;
  pwm3ph_prepare();
  pwm3ph_outputs(1);
  drv_inl_high();
  if (pwm3ph_faulted()) { pwm3ph_release(); return 0; }
  return 1;
}

void pwm3ph_set(int32_t ccr_a, int32_t ccr_b, int32_t ccr_c)
{
  // P0-4 修复：强制 0 ~ PWM3PH_ARR 饱和限幅，防止负数下溢转成 0xFFFFFFFF 造成 100% 满占空比直通
  if (ccr_a < 0) ccr_a = 0; else if (ccr_a > (int32_t)PWM3PH_ARR) ccr_a = (int32_t)PWM3PH_ARR;
  if (ccr_b < 0) ccr_b = 0; else if (ccr_b > (int32_t)PWM3PH_ARR) ccr_b = (int32_t)PWM3PH_ARR;
  if (ccr_c < 0) ccr_c = 0; else if (ccr_c > (int32_t)PWM3PH_ARR) ccr_c = (int32_t)PWM3PH_ARR;

  GPTIMER0->CCR0 = (uint32_t)ccr_a;
  GPTIMER0->CCR1 = (uint32_t)ccr_b;
  GPTIMER0->CCR2 = (uint32_t)ccr_c;
}

static void pwm3ph_update_irq(void)
{
  GPTIMER_ClearFlagUpdate(GPTIMER0);
  // P1-3 valley gate: at the underflow (valley) event CNT has just wrapped to
  // ~0 and counts up; at the overflow (peak) event CNT sits at ARR counting
  // down. Only the valley has all low-side switches on (valid current sense)
  // and starts a fresh PWM period.
  if (GPTIMER0->CNT > (PWM3PH_ARR >> 1)) {
    return;
  }
  if (s_update_isr) {
    s_update_isr();
  }
}

void pwm3ph_on_update(void (*isr)(void))
{
  s_update_isr = isr;
  GPTIMER_EnableIntUpdate(GPTIMER0);
  plic_isr[GPTIMER0_IRQn] = pwm3ph_update_irq;
  INT_EnableIRQ(GPTIMER0_IRQn, 1);
  INT_EnablePLIC();
  GPTIMER_EnableCounter(GPTIMER0); // acquisition continues with the power stage off
}
