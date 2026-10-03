// main.c — FOC2205 bring-up flow (see docs/DRV8316+MT6701_FOC驱动板接线设计.md §6-7)
#include <stdio.h>
#include "board.h"
#include "app_io.h"
#include "drv8316.h"
#include "mt6701.h"
#include "current.h"
#include "pwm3ph.h"
#include "foc.h"

#define POLE_PAIRS 7   // 2205 motor placeholder — set to the real value

static volatile uint32_t s_isr_count;

static void foc_isr(void)
{
  foc_step_isr();
  ++s_isr_count;
}

static void bringup_banner(void)
{
  printf("\n=== FOC2205 bring-up ===\n");
  printf("SYSCLK=%u BUSCLK=%u\n",
         (unsigned)SYS_GetSysClkFreq(),
         (unsigned)BOARD_BUS_FREQUENCY);
  // BOOT1(PIN_15) is 100% UNTOUCHED and dedicated to boot strap (10k pulldown).
  // INL_EN sits on PIN_28 (JNTRST pad) — DAPLink uses 2-wire Compact-JTAG, so
  // debugging is unaffected; an external 10k pulldown owns the pad at reset.
  printf("BootMode=%d (0=FLASH 1=UARTloader 3=SRAM)\n", (int)SYS_GetBootMode());
}

static int drv_selftest(void)
{
  drv_resp_t r2 = drv8316_read_reg(DRV_REG_CTRL2);
  drv_resp_t r6 = drv8316_read_reg(DRV_REG_CTRL6);
  printf("DRV8316: CTRL2=0x%02x (want 0x7c) CTRL6=0x%02x (want 0x11) STAT=0x%02x\n",
         r2.data, r6.data, r6.stat);
  if (r2.data != DRV_VAL_CTRL2 || r6.data != DRV_VAL_CTRL6) {
    printf("DRV8316 SPI readback FAIL (mode-1 bridge or wiring?)\n");
    return 0;
  }
  if (r6.stat & 0x20) { // IC_STAT bit5 = SPI_FLT
    printf("DRV8316 SPI_FLT set (frame length/parity?)\n");
    return 0;
  }
  return 1;
}

static int mt_selftest(void)
{
  mt6701_sample_t s;
  int ok = 0;
  for (int i = 0; i < 16; ++i) {
    ok += mt6701_read(&s);
  }
  printf("MT6701: CRC pass %d/16, angle=%u field=%u push=%u\n",
         ok, s.angle, s.field, s.push);
  return ok == 16;
}

int main(void)
{
  board_init();          // clocks + UART0 printf
  bringup_banner();
  app_io_init();

  // --- DRV8316 power-up ---
  drv_wake();
  delay_ms(50);          // TPwrUp + tREADY
  printf("nSLEEP released\n");

  // --- PWM first (all outputs low) per datasheet order ---
  pwm3ph_init();
  printf("PWM3ph ready: %u Hz, ARR=%u\n", (unsigned)PWM3PH_FREQ_HZ, (unsigned)PWM3PH_ARR);

  // --- driver configuration with auto-retry on bus glitch / lock state (D-1 fix) ---
  int drv_ready = 0;
  for (int retry = 0; retry < 3; ++retry) {
    drv8316_init();
    if (drv_selftest()) {
      drv_ready = 1;
      break;
    }
    printf("DRV8316 init retry %d...\n", retry + 1);
    drv8316_sleep_pulse_reset();
  }
  if (!drv_ready) {
    printf("HALT: fix SPI before enabling power stage\n");
    while (1) { }
  }
  drv_inl_high();        // P0-3: release INLx only after the PWM_MODE write
  printf("INLx released -> 3x PWM drive enabled\n");

  // --- encoder ---
  mt6701_init();
  if (!mt_selftest()) {
    printf("HALT: SSI CRC failing (check MODE pin = VDD, wiring, fallback B)\n");
    while (1) { }
  }

  // --- current sense zero cal (motor unpowered) ---
  current_init();
  printf("Izero: A=%d B=%d C=%d\n", g_cur_cal.off_a, g_cur_cal.off_b, g_cur_cal.off_c);

  // --- FOC loop & alignment ---
  foc_init(POLE_PAIRS);
  printf("Aligning rotor to d-axis...\n");
  foc_align_sensor();
  printf("Zero angle offset: %d/1000 rad, sensor direction: %+d\n",
         (int)(g_foc.zero_electric_angle * 1000.0f), (int)g_foc.sensor_direction);

  pwm3ph_on_update(foc_isr);
  pwm3ph_outputs(1);
  printf("FOC loop running\n");

  uint32_t last = s_isr_count;
  for (;;) {
    UTIL_IdleUs(500000);
    uint32_t now = s_isr_count;
    printf("isr=%u ang=%d ib=%d crc_err=%u dir=%+d\n",
           (unsigned)(now - last), (int)foc_last_angle(), (int)foc_last_iq(),
           (unsigned)foc_crc_errors(), (int)g_foc.sensor_direction);
    last = now;

    // bring-up hook: hold torque at 0 until the hand-feel layer drives g_foc.torque_q
  }
}
