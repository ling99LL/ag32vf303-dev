#ifndef CALIBRATION_H
#define CALIBRATION_H
#include <stdint.h>
// 0 idle, 1 ramp, 2 settle zero, 3 sample zero, 4 slow +90deg sweep,
// 5 settle probe, 6 sample probe, 7 success, 8 cancelled, 9 failed.
int calibration_start(void);
void calibration_cancel(void);
void calibration_step_isr(void);
void calibration_keepalive(void);
void calibration_set_rate(uint32_t hz);
int calibration_active(void);
int calibration_stage(void);
uint32_t calibration_peak(void);
#define CALIBRATION_PCT 5
// 1 LSB is about 1.34 mA at the DRV8316C 0.6 V/A gain.  200 LSB (~269 mA)
// tripped normal 5% calibration and detent-mode current; 1800 LSB (~2.4 A)
// is just below the motor's 2.5 A rating and still catches gross faults.
#define CURRENT_TRIP_LSB 1800
#endif
