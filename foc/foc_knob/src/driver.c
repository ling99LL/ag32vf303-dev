#include "alta.h"
#include "foc_knob.h"
#include "driver.h"
#include "util.h"

static bool s_sleeping = false;

void driver_init(void)
{
  SYS_EnableAPBClock(DRV_GPIO_MASK);
  // control lines as outputs, safe idle levels
  GPIO_SetOutput(DRV_GPIO, (uint8_t)(DRV_BIT_EN | DRV_BIT_RESET | DRV_BIT_SLEEP));
  GPIO_SetLow (DRV_GPIO, DRV_BIT_EN);     // outputs disabled
  GPIO_SetHigh(DRV_GPIO, DRV_BIT_RESET);  // out of reset
  GPIO_SetHigh(DRV_GPIO, DRV_BIT_SLEEP);  // awake
  // nFAULT input
  GPIO_SetInput(DRV_GPIO, DRV_BIT_FAULT);
  s_sleeping = false;
}

void driver_enable(bool en)
{
  if (en) GPIO_SetHigh(DRV_GPIO, DRV_BIT_EN);
  else    GPIO_SetLow (DRV_GPIO, DRV_BIT_EN);
}

void driver_set_sleep(bool slp)
{
  if (slp) GPIO_SetLow (DRV_GPIO, DRV_BIT_SLEEP);
  else     GPIO_SetHigh(DRV_GPIO, DRV_BIT_SLEEP);
  s_sleeping = slp;
}

bool driver_sleeping(void) { return s_sleeping; }

void driver_reset_pulse(void)
{
  GPIO_SetLow (DRV_GPIO, DRV_BIT_RESET);
  UTIL_IdleUs(20);
  GPIO_SetHigh(DRV_GPIO, DRV_BIT_RESET);
  UTIL_IdleMs(1);
}

bool driver_fault(void)
{
  // nFAULT low = overtemperature / overcurrent on the driver board
  return (GPIO_GetValue(DRV_GPIO, DRV_BIT_FAULT) & DRV_BIT_FAULT) == 0;
}
