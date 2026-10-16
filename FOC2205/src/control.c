#include "control.h"
#include "foc.h"
#include "motion.h"
#include "pwm3ph.h"
#include "drv8316.h"
#include "mt6701.h"
#include "current.h"
#include "interrupt.h"
#include "calibration.h"
#include "build_config.h"

static int s_aligned;
static uint32_t s_drv_status;
static int s_drv_ready;

void control_set_aligned(int aligned) { s_aligned = aligned; }
uint32_t control_driver_status(void) { return s_drv_status; }
int control_driver_ready(void) { return s_drv_ready; }
int control_is_aligned(void) { return s_aligned; }
int control_ready(void)
{
  return !calibration_active() && s_aligned && s_drv_ready && current_calibrated() &&
         foc_angle_valid() && foc_current_valid() && !pwm3ph_faulted() &&
         !(foc_sensor_status() & 0x0bu) &&
         motion_state() != MOTION_FAULT;
}
int control_calibration_ready(void)
{
  return !calibration_active() && motion_state() == MOTION_IDLE &&
         !pwm3ph_enabled() &&
         s_drv_ready && current_calibrated() && foc_angle_valid() &&
         foc_current_valid() && !(foc_sensor_status() & 0x0bu) && !pwm3ph_faulted();
}

void control_step_isr(void)
{
  if (pwm3ph_faulted()) motion_trip("driver break");
  foc_step_isr();
  if (foc_crc_consecutive() >= 8u) motion_trip("encoder CRC");
  if (foc_adc_consecutive()) motion_trip("ADC timeout");
  if (calibration_active()) calibration_step_isr();
  else motion_step_isr();
}

void control_poll_driver(void)
{
#if !FOC_CPLD_BRINGUP
  s_drv_status = 0;
  s_drv_ready = 0;
  return;
#else
  s_drv_status = drv8316_read_reg(DRV_REG_IC_STAT).data;
  s_drv_ready = !(s_drv_status & 0x77u) && (s_drv_status & 0x08u) &&
      drv8316_read_reg(DRV_REG_CTRL2).data == DRV_VAL_CTRL2 &&
      drv8316_read_reg(DRV_REG_CTRL6).data == DRV_VAL_CTRL6;
  if ((s_drv_status & 0x77u) || !(s_drv_status & 0x08u))
    motion_trip("driver status");
  else if (!s_drv_ready) motion_trip("driver config");
#endif
}

int control_recover(void)
{
#if !FOC_CPLD_BRINGUP
  return 0;
#else
  if (calibration_active() || motion_state() != MOTION_FAULT) return 0;
  // SPI1 and ADC are owned by the PWM ISR. Pause only that interrupt while
  // checking them with INL and MOE off; never re-run powered alignment here.
  INT_DisableIRQ(GPTIMER0_IRQn);
  motion_stop();
  drv8316_clear_faults();
  delay_ms(2);
  control_poll_driver();
  int ok = !(s_drv_status & 0x77u) && (s_drv_status & 0x08u);
  ok = ok && drv8316_read_reg(DRV_REG_CTRL2).data == DRV_VAL_CTRL2;
  ok = ok && drv8316_read_reg(DRV_REG_CTRL6).data == DRV_VAL_CTRL6;
  mt6701_sample_t sample;
  for (int i = 0; i < 16; ++i) {
    if (!mt6701_read(&sample)) ok = 0;
  }
  if (!current_init()) ok = 0;
  if (ok) {
    pwm3ph_ack_break();
    delay_us(20); // allow an active nFAULT input to reassert the hardware latch
    if (pwm3ph_faulted()) ok = 0;
  }
  if (ok) {
    foc_clear_sensor_faults();
    ok = motion_recover(); // IDLE only; a new command is required to move
  }
  INT_EnableIRQ(GPTIMER0_IRQn, 1);
  return ok;
#endif
}
