// current.h — three-phase current sensing via the 3 logic-side ADCs (quasi-simultaneous)
//
// SOA/SOB/SOC -> PIN_10/11/12 = ADC_IN3/IN4/IN5 (fixed analog pads, no .ve line).
// Each ADC instance has its own START; firing all three back-to-back in the PWM
// update ISR gives <100ns skew between phases. No hardware trigger exists on
// AG32 (verified), so this is the tightest sync available.
#ifndef CURRENT_H
#define CURRENT_H

#include "analog_ip.h"

// CSA gain = 0.6 V/A, VREF = VDDA = 3.3V, 12-bit ADC
#define CUR_LSB_MA_NUM   5500   // mA = (raw - off) * 5500 / 4096  ( = *1.343 )
#define CUR_LSB_MA_DEN   4096

typedef struct
{
  int16_t off_a, off_b, off_c; // zero-current raw offsets
} current_cal_t;

extern current_cal_t g_cur_cal;

void current_init(void);                 // channel setup + zero-offset calibration
void current_trigger(void);              // start all three conversions (ISR use)
void current_read_raw(int16_t *a, int16_t *b, int16_t *c); // wait EOC + subtract offsets

#endif
