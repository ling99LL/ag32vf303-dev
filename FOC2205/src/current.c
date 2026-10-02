#include "current.h"

current_cal_t g_cur_cal;

// sclk = bus / ((div+1)*2); conversion = 13 sclk -> 1.04us at div=3
#define CUR_SCLK_DIV 3

static void start_all(void)
{
  ADC_Start(ADC0, CUR_SCLK_DIV);
  ADC_Start(ADC1, CUR_SCLK_DIV);
  ADC_Start(ADC2, CUR_SCLK_DIV);
}

void current_init(void)
{
  ADC_SetChannel(ADC0, ADC_CHANNEL3); // SOA -> IN3 (PIN_10)
  ADC_SetChannel(ADC1, ADC_CHANNEL4); // SOB -> IN4 (PIN_11)
  ADC_SetChannel(ADC2, ADC_CHANNEL5); // SOC -> IN5 (PIN_12)

  // Zero-offset calibration: motor unpowered / no PWM activity, 256 averages
  uint32_t sa = 0, sb = 0, sc = 0;
  for (int i = 0; i < 256; ++i) {
    int16_t a, b, c;
    start_all();
    ADC_WaitForEoc(ADC0);
    ADC_WaitForEoc(ADC1);
    ADC_WaitForEoc(ADC2);
    a = (int16_t)ADC_GetData(ADC0);
    b = (int16_t)ADC_GetData(ADC1);
    c = (int16_t)ADC_GetData(ADC2);
    sa += a; sb += b; sc += c;
  }
  g_cur_cal.off_a = (int16_t)(sa / 256);
  g_cur_cal.off_b = (int16_t)(sb / 256);
  g_cur_cal.off_c = (int16_t)(sc / 256);
}

void current_trigger(void)
{
  start_all();
}

void current_read_raw(int16_t *a, int16_t *b, int16_t *c)
{
  ADC_WaitForEoc(ADC0);
  ADC_WaitForEoc(ADC1);
  ADC_WaitForEoc(ADC2);
  *a = (int16_t)(ADC_GetData(ADC0) - g_cur_cal.off_a);
  *b = (int16_t)(ADC_GetData(ADC1) - g_cur_cal.off_b);
  *c = (int16_t)(ADC_GetData(ADC2) - g_cur_cal.off_c);
}
