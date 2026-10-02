// foc.h — FOC voltage-mode loop skeleton + hand-feel parameter hooks
//
// The knob's feel (手感) is tuned through the params below; the electrical loop
// runs in the GPTIMER0 update ISR: sample currents (quasi-simultaneous) and
// angle (SSI) at the PWM valley, then update the three CCRs.
#ifndef FOC_H
#define FOC_H

#include <stdint.h>

typedef struct
{
  // electrical
  int32_t id_ref_q;     // d-axis current target, Q12 amps
  int32_t iq_ref_q;     // q-axis target (torque), Q12 amps
  int32_t v_limit_q;    // voltage limit, Q12 volts
  int32_t kp_q, ki_q;   // current loop gains (voltage mode uses feedforward)
  uint16_t pole_pairs;
  // hand-feel layer outputs (filled by the knob logic, consumed here)
  int32_t torque_q;     // external torque command, Q12
  uint8_t brake;        // 1 = short phases (parking brake)
} foc_params_t;

extern foc_params_t g_foc;

void foc_init(uint16_t pole_pairs);
// Called from the PWM update ISR
void foc_step_isr(void);
// Read-only status for diagnostics
int32_t foc_last_angle(void);
int32_t foc_last_iq(void);

#endif
