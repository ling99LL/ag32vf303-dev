// pwm3ph.h — GPTIMER0 center-aligned three-phase PWM for DRV8316 3x mode
//
// 3x mode: only INHx is driven (PIN_7/8/9 -> INHA/B/C); INLx is tied to AVDD on
// the board and the driver generates the complementary low side with its own
// VGS-sensed dead time. MCU DTG stays 0.
// BRK input = nFAULT (active low, BKP=0): hardware brake kills the outputs with
// zero software latency if the driver reports a fault.
#ifndef PWM3PH_H
#define PWM3PH_H

#include "alta.h"

#define PWM3PH_FREQ_HZ   20000u
// GPTIMER0 clock = bus clock (100MHz); center-aligned both edges:
// f_pwm = clk / (2 * (ARR+1)) -> ARR+1 = 2500
#define PWM3PH_ARR       2499u

void pwm3ph_init(void);                  // timer + BRK configured, MOE stays off
void pwm3ph_outputs(int on);             // MOE on/off (off = OSSI drives low)
void pwm3ph_set(int32_t ccr_a, int32_t ccr_b, int32_t ccr_c); // 0..PWM3PH_ARR
void pwm3ph_on_update(void (*isr)(void));// update-event ISR hook + PLIC enable

#endif
