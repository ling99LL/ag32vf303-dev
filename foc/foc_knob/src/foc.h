#ifndef FOC_H
#define FOC_H
#include <stdbool.h>

// FOC core: electrical angle -> inverse Park -> SVPWM -> 3-phase duty.
// Torque is voltage-mode (no current sensing on the driver board):
// Uq in volts, proportional to motor torque.

void foc_init(void);                      // sincos LUT etc.
void foc_apply(float theta_e, float uq);  // set 3-phase duties for (angle, torque)
void foc_zero(void);                      // zero vector (no line voltage)

// FOC loop, runs from GPTIMER0 update interrupt (register this after calib)
void foc_loop_irq(void);
void foc_set_enabled(bool en);
bool foc_enabled(void);
bool foc_fault_latched(void);             // driver FAULT seen -> outputs stay off
void foc_clear_fault(void);

uint32_t foc_loop_count(void);            // passes since start (loop-rate check)

// non-blocking open-loop rotation: the GPTIMER0 irq advances a commanded
// electrical angle (voltage-mode drag) so the main loop stays free - serial
// commands and hall telemetry keep running while the motor turns
void foc_ol_start(float total_e_rad, float rate_e_rad_s, float uq_volt);
bool foc_ol_active(void);
void foc_ol_abort(void);                  // stop without the done flag
bool foc_ol_pop_done(void);               // true once: rotation finished

#endif
