#include "alta.h"
#include "pwm3ph.h"

static uint32_t s_arr = 0;

void pwm3ph_init(uint32_t pwm_freq_hz)
{
  SYS_EnableAPBClock(APB_MASK_GPTIMER0);
  GPIO_AF_ENABLE(GPTIMER0_CH0);
  GPIO_AF_ENABLE(GPTIMER0_CH1);
  GPIO_AF_ENABLE(GPTIMER0_CH2);

  GPTIMER_InitTypeDef ti;
  GPTIMER_StructInit(&ti);
  // center-aligned: f_pwm = f_clk / (2 * ARR)
  ti.CounterMode = GPTIMER_COUNTERMODE_CENTER_UP;
  ti.Autoreload  = SYS_GetPclkFreq() / (2u * pwm_freq_hz);
  s_arr = ti.Autoreload;
  GPTIMER_Init(GPTIMER0, &ti);

  GPTIMER_OC_InitTypeDef oc;
  for (int ch = 0; ch < 3; ch++) {
    GPTIMER_OC_StructInit(&oc);
    oc.OCState      = GPTIMER_OCSTATE_ENABLE;
    oc.OCMode       = GPTIMER_OCMODE_PWM1;
    oc.CompareValue = s_arr / 2;          // start at zero vector
    GPTIMER_OC_Init(GPTIMER0, (GPTIMER_ChannelNumTypeDef)ch, &oc);
    GPTIMER_OC_EnablePreload(GPTIMER0, (GPTIMER_ChannelNumTypeDef)ch);
  }
  GPTIMER_EnableARRPreload(GPTIMER0);
  // when MOE is cleared, force outputs to idle level (low) instead of Hi-Z,
  // so the driver inputs see a defined "all low" = low-side brake state
  GPTIMER_SetOffStateIdle(GPTIMER0, GPTIMER_OSSI_ENABLE);

  GPTIMER_DisableAllOutputs(GPTIMER0);    // MOE off until FOC is calibrated
  GPTIMER_EnableCounter(GPTIMER0);
  // load shadow registers (same double-update trick as the official DMA example)
  GPTIMER_GenerateEventUpdate(GPTIMER0);
  GPTIMER_GenerateEventUpdate(GPTIMER0);
}

void pwm3ph_set_duty(float d0, float d1, float d2)
{
  const float d[3] = {d0, d1, d2};
  for (int ch = 0; ch < 3; ch++) {
    float x = d[ch];
    if (x < 0.0f) x = 0.0f;
    if (x > 1.0f) x = 1.0f;
    GPTIMER_OC_SetCompare(GPTIMER0, (GPTIMER_ChannelNumTypeDef)ch,
                          (uint32_t)(x * (float)s_arr));
  }
}

void pwm3ph_outputs_enable(bool en)
{
  if (en) GPTIMER_EnableAllOutputs(GPTIMER0);
  else    GPTIMER_DisableAllOutputs(GPTIMER0);
}

uint32_t pwm3ph_arr(void) { return s_arr; }
