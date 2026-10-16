#include "current.h"

current_cal_t g_cur_cal;
static int s_calibrated;
int current_calibrated(void) { return s_calibrated; }

// sclk = bus / ((div+1)*2); conversion = 13 sclk -> 1.04us at div=3
#define CUR_SCLK_DIV 3

static void start_all(void)
{
  ADC_Start(ADC0, CUR_SCLK_DIV);
  ADC_Start(ADC1, CUR_SCLK_DIV);
  ADC_Start(ADC2, CUR_SCLK_DIV);
}

// Bounded wait to prevent infinite hang if ADC/logic clock stalls (D-4 fix)
static inline int wait_adc_eoc_bounded(ADC_TypeDef *adc)
{
  uint64_t start = UTIL_GetMcycle();
  while (!(adc->STAT & ADC_STAT_EOC)) {
    if (UTIL_GetMcycle() - start > 2000u) return 0; // 10us at 200MHz
  }
  return (adc->STAT & ADC_STAT_EOC) != 0;
}

int current_init(void)
{
  s_calibrated = 0;
  ADC_SetChannel(ADC0, ADC_CHANNEL3); // SOA -> IN3 (PIN_10)
  ADC_SetChannel(ADC1, ADC_CHANNEL4); // SOB -> IN4 (PIN_11)
  ADC_SetChannel(ADC2, ADC_CHANNEL5); // SOC -> IN5 (PIN_12)

  // Zero-offset calibration: motor unpowered / no PWM activity, 256 averages
  uint32_t sa = 0, sb = 0, sc = 0;
  for (int i = 0; i < 256; ++i) {
    start_all();
    if (!wait_adc_eoc_bounded(ADC0) || !wait_adc_eoc_bounded(ADC1) ||
        !wait_adc_eoc_bounded(ADC2)) return 0;
    sa += (uint32_t)ADC_GetData(ADC0);
    sb += (uint32_t)ADC_GetData(ADC1);
    sc += (uint32_t)ADC_GetData(ADC2);
  }

  int16_t off_a = (int16_t)(sa / 256);
  int16_t off_b = (int16_t)(sb / 256);
  int16_t off_c = (int16_t)(sc / 256);

  // Sanity check: expected AVDD/2 is ~2048 LSB (+- 500 LSB margin for 1.65V bias)
  // A disconnected or saturated sensor must not be silently treated as healthy.
  if (off_a < 1500 || off_a > 2600 || off_b < 1500 || off_b > 2600 ||
      off_c < 1500 || off_c > 2600) return 0;

  g_cur_cal.off_a = off_a;
  g_cur_cal.off_b = off_b;
  g_cur_cal.off_c = off_c;
  s_calibrated = 1;
  return 1;
}

void current_trigger(void)
{
  start_all();
}

int current_read_raw(int16_t *a, int16_t *b, int16_t *c)
{
  if (!wait_adc_eoc_bounded(ADC0) || !wait_adc_eoc_bounded(ADC1) ||
      !wait_adc_eoc_bounded(ADC2)) return 0;
  *a = (int16_t)(ADC_GetData(ADC0) - g_cur_cal.off_a);
  *b = (int16_t)(ADC_GetData(ADC1) - g_cur_cal.off_b);
  *c = (int16_t)(ADC_GetData(ADC2) - g_cur_cal.off_c);
  return 1;
}
