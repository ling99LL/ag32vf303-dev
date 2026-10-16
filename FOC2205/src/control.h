#ifndef CONTROL_H
#define CONTROL_H
#include <stdint.h>
void control_set_aligned(int aligned);
void control_step_isr(void);
void control_poll_driver(void);
uint32_t control_driver_status(void);
int control_driver_ready(void);
int control_is_aligned(void);
int control_ready(void);
int control_calibration_ready(void);
int control_recover(void);
#endif
