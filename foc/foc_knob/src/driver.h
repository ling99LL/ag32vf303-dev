#ifndef DRIVER_H
#define DRIVER_H
#include <stdbool.h>

// Driver board control lines (EN / nRESET / nSLEEP / nFAULT on GPIO0, foc_knob.ve)
void driver_init(void);           // EN off, RESET idle high, SLEEP idle high
void driver_enable(bool en);      // gate all 3 half-bridges (EN pin)
void driver_set_sleep(bool slp);  // low-power sleep (knob goes limp)
bool driver_sleeping(void);
void driver_reset_pulse(void);    // 20us low pulse on nRESET, then idle high
bool driver_fault(void);          // true when nFAULT pin is low

#endif
