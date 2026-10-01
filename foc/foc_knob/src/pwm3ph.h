#ifndef PWM3PH_H
#define PWM3PH_H
#include <stdint.h>
#include <stdbool.h>

// GPTIMER0 CH0/1/2 three-phase center-aligned PWM (see foc_knob.ve for pads).
void     pwm3ph_init(uint32_t pwm_freq_hz);
// duty in 0..1 each phase (0.5/0.5/0.5 = zero vector), CCR preload enabled
void     pwm3ph_set_duty(float d0, float d1, float d2);
// MOE (main output enable); with OSSI=1, disabled outputs idle LOW = safe brake
void     pwm3ph_outputs_enable(bool en);
uint32_t pwm3ph_arr(void);

#endif
