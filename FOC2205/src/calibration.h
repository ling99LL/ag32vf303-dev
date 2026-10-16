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
#define CALIBRATION_PCT 3
#define CURRENT_TRIP_LSB 200
#endif
