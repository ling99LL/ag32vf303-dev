#ifndef CONTROL_LOCK_H
#define CONTROL_LOCK_H

#include <stdint.h>
#ifdef FOC_HOST_TEST
static inline uint32_t control_lock(void) { return 0; }
static inline void control_unlock(uint32_t saved) { (void)saved; }
#else
#include "interrupt.h"
// Nestable in foreground and ISR. Never hold this lock across UART output or waits.
static inline uint32_t control_lock(void)
{
  uint32_t saved;
  __asm__ volatile ("csrrci %0, mstatus, 8" : "=r"(saved) :: "memory");
  return saved;
}
static inline void control_unlock(uint32_t saved)
{
  if (saved & MSTATUS_MIE)
    __asm__ volatile ("csrsi mstatus, 8" ::: "memory");
  else
    __asm__ volatile ("" ::: "memory");
}
#endif
#endif
