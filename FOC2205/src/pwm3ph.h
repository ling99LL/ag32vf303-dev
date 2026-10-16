// pwm3ph.h — GPTIMER0 center-aligned three-phase PWM for DRV8316 3x mode
//
// 3x mode: only INHx is driven (PIN_7/8/9 -> INHA/B/C); INLA/B/C are shorted to
// DRV_INL_ALL on the board and driven by GPIO2_2/PIN_28 (10k pulldown). The
// driver generates the complementary low side with its own VGS-sensed dead
// time. MCU DTG stays 0.
// BRK input = nFAULT (active low, BKP=0): hardware brake kills the outputs with
// zero software latency if the driver reports a fault.
#ifndef PWM3PH_H
#define PWM3PH_H

#include <stdint.h>

#define PWM3PH_FREQ_HZ   20000u
// GPTIMER0 clock = MCU PCLK (explicitly divided to 100MHz in main).
// VE BUSCLK is independent. Center-aligned both edges:
// f_pwm = clk / (2 * (ARR+1)) -> ARR+1 = 2500
#define PWM3PH_ARR       2499u

void pwm3ph_init(void);                  // timer + BRK configured, MOE stays off
int  pwm3ph_arm(void);                   // safe neutral preload, refuse latched break
void pwm3ph_release(void);               // INL low and MOE off
void pwm3ph_prepare(void);               // latch neutral duties with outputs off
int  pwm3ph_faulted(void);
int  pwm3ph_enabled(void);               // actual MOE readback for diagnostics
void pwm3ph_ack_break(void);             // only after explicit health checks
void pwm3ph_outputs(int on);             // MOE on/off (off = OSSI drives low)
void pwm3ph_set(int32_t ccr_a, int32_t ccr_b, int32_t ccr_c); // 0..PWM3PH_ARR
void pwm3ph_on_update(void (*isr)(void));// update-event ISR hook + PLIC enable
extern volatile uint32_t g_pwm_release_diag[6]; // SR before/after INL/after MOE; pin levels

#endif
