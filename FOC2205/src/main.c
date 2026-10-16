#include <stdio.h>
#include "board.h"
#include "spi.h"
#include "uart.h"
#include "app_io.h"
#include "drv8316.h"
#include "interrupt.h"
#include "mt6701.h"
#include "current.h"
#include "pwm3ph.h"
#include "foc.h"
#include "motion.h"
#include "console.h"
#include "control.h"
#include "calibration.h"
#include "build_config.h"

#ifndef MOTION_AUTORUN
#define MOTION_AUTORUN 0
#endif

#define POLE_PAIRS 7   // 2205(2804) 12N14P — docs/电机参数.md 已确认

volatile uint32_t g_stage;
#define STAGE(n) (g_stage = (n))

static volatile uint32_t s_isr_count;

static void foc_isr(void)
{
  control_step_isr();
  ++s_isr_count;
}


static void bringup_banner(void)
{
  printf("\n=== FOC2205 bring-up ===\n");
  printf("SYSCLK=%u PCLK=%u LOGIC_BUSCLK=%u\n",
         (unsigned)SYS_GetSysClkFreq(),
         (unsigned)SYS_GetPclkFreq(),
         (unsigned)BOARD_BUS_FREQUENCY);
  printf("BootMode=%d (0=FLASH 1=UARTloader 3=SRAM)\n", (int)SYS_GetBootMode());
}

volatile uint32_t g_mt_raw[4];
volatile uint32_t g_mt_n;
volatile uint32_t g_mt_shift[3];

static void mt_capture_raw(void)
{
  mt6701_sample_t s = {0};
  for (int k = 0; k < 4; ++k) {
    mt6701_read(&s);
    g_mt_raw[k] = g_mt_last_raw;
  }
  g_mt_n = 4;

  for (int i = 0; i < 3; ++i) {
    uint32_t f = (i == 0) ? g_mt_last_raw
               : (i == 1) ? ((g_mt_last_raw << 1) & 0xFFFFFFu)
                          : (g_mt_last_raw >> 1);
    uint8_t rx   = (uint8_t)(f & 0x3Fu);
    uint8_t calc = mt6701_crc6(f >> 6);
    g_mt_shift[i] = (rx == calc) ? (uint32_t)(0x1000000u | f) : 0u;  // pass flag + frame
  }
}

volatile uint32_t g_diag[8];
volatile uint32_t g_diag_done;

static void drv_dump_regs(void)
{
  drv_resp_t r;
  const uint8_t addr[6] = { DRV_REG_IC_STAT, DRV_REG_CTRL1, DRV_REG_CTRL2,
                            DRV_REG_CTRL5, DRV_REG_CTRL6, DRV_REG_CTRL10 };
  for (int i = 0; i < 6; ++i) {
    r = drv8316_read_reg(addr[i]);
    g_diag[i] = ((uint32_t)r.stat << 8) | (uint32_t)r.data;
  }
  g_diag_done = 1;
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
  mt6701_sample_t s = {0};
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
#if FOC_RELOAD_LOGIC
  // Keep the existing compressed ROM boot address. Reconfigure from that
  // verified image on HSI, using the same SDK path as logic_embed, without
  // changing option bytes or erasing the stand-alone boot logic.
  SYS_DisableNJTRST();
  PERIPHERAL_GPIO_ENABLE(GPIO2);
  GPIO_SetSoftwareMode(GPIO2, DRV_INL_BIT);
  drv_inl_low();
  GPIO_SetOutput(GPIO2, DRV_INL_BIT);
  PERIPHERAL_ENABLE(FCB, 0);
  SYS_SwitchHSIClock();
  // In compressed boot mode 0x80034000 holds the decompressor, while OB
  // 0x38/0x3c stores the actual compressed bitstream address and complement.
  uint32_t config_addr = *(volatile uint32_t *)0x81000038u;
  uint32_t config_inv = *(volatile uint32_t *)0x8100003cu;
  if ((config_addr ^ config_inv) == 0xffffffffu &&
      config_addr >= 0x80034000u && config_addr < 0x80040000u) {
    FCB_ClearErrors();
    FCB_AutoDecompress(config_addr);
  }
  PERIPHERAL_DISABLE(FCB, 0);
#endif
  // VE BUSCLK configures the fabric bus; it does not divide MCU peripherals.
  // Set this before board_init calculates the UART baud rate. PCLK=200/2 MHz
  // gives GPTIMER 20 kHz and SPI DIV32 3.125 MHz (DRV8316 max 5 MHz).
  SYS_SetPclkDivider(1);
  board_init();          // clocks + UART0 printf
  STAGE(1);
  bringup_banner();
  app_io_init();
  STAGE(2);

  pwm3ph_init();
  foc_init(POLE_PAIRS);
  motion_init();
  STAGE(3);
  printf("PWM3ph ready: %u Hz, ARR=%u\n", (unsigned)PWM3PH_FREQ_HZ, (unsigned)PWM3PH_ARR);

#if FOC_CPLD_BRINGUP
  drv_wake();
  delay_ms(50);          // TPwrUp + tREADY
  printf("nSLEEP released\n");

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
  drv_dump_regs();
  // Independent diagnostics stay available even with VM/DRV8316 off.
  // Do not calibrate or energize the rotor until every prerequisite passes.
  mt6701_init();
  int mt_ready = mt_selftest();
  int adc_ready = current_init();
  printf("ADC calibration: %s; Izero A=%d B=%d C=%d\n",
         adc_ready ? "valid" : "invalid (raw diagnostics only)",
         g_cur_cal.off_a, g_cur_cal.off_b, g_cur_cal.off_c);
  if (!drv_ready) {
    STAGE(4);
    printf("STARTUP FAULT: DRV8316 unavailable/config mismatch; check VM and SPI\n");
    motion_trip("driver unavailable/config");
    goto startup_fault;
  }
  STAGE(5);
  control_poll_driver();
  if (motion_state() == MOTION_FAULT) goto startup_fault;
  pwm3ph_ack_break();
  if (!mt_ready) {
    STAGE(6);
    mt_capture_raw();
    printf("STARTUP FAULT: SSI CRC failing (check MODE pin = VDD, wiring, fallback B)\n");
    motion_trip("startup encoder CRC");
    goto startup_fault;
  }
  STAGE(7);

  if (!adc_ready) {
    STAGE(8);
    drv_inl_low();
    pwm3ph_outputs(0);
    printf("STARTUP FAULT: current-sense ADC calibration failed\n");
    motion_trip("startup ADC calibration");
    goto startup_fault;
  }
  STAGE(8);
  printf("Izero: A=%d B=%d C=%d\n", g_cur_cal.off_a, g_cur_cal.off_b, g_cur_cal.off_c);

  // Never energize the rotor during boot. Calibration is an explicit,
  // cancellable action from the host panel after the operator confirms the
  // 9V supply and unloaded mechanical setup.
  STAGE(10);
  drv_inl_low();
  pwm3ph_outputs(0);
  control_set_aligned(0);
  printf("Calibration idle: outputs OFF; press 'a' in the host panel to start\n");
#else
  // Recovery image: never access SPIW/ADC CPLD windows and never install the
  // sampling ISR. Keep INL/MOE low and put the driver back to sleep.
  drv_inl_low();
  drv_sleep();
  pwm3ph_set(0, 0, 0);
  pwm3ph_outputs(0);
  control_set_aligned(0);
  STAGE(90);
  printf("SAFE BOOT: FOC_CPLD_BRINGUP=0; CPLD SPI/ADC access disabled\n");
  printf("SAFE BOOT: outputs OFF; verify logic before enabling bring-up\n");
#endif
startup_fault:
#if FOC_CPLD_BRINGUP
  pwm3ph_on_update(foc_isr);
  if (motion_state() != MOTION_FAULT) STAGE(11);
  printf("acquisition running; power stage idle or faulted\n");

  uint32_t c0 = s_isr_count;
  uint64_t m0 = UTIL_GetMcycle();
  UTIL_IdleMs(200);
  uint64_t m1 = UTIL_GetMcycle();
  uint32_t dcount = s_isr_count - c0;
  uint32_t dt_us_mc = (uint32_t)((m1 - m0) / (SYS_GetSysClkFreq() / 1000000u));          // mcycle -> us @200MHz
  uint32_t isr_hz_ms = dcount * 5u;                          // 200ms 窗口 -> Hz
  uint32_t isr_hz_mc = (dt_us_mc > 0)
                     ? (uint32_t)(((uint64_t)dcount * 1000000u) / dt_us_mc) : 0u;
  uint32_t isr_hz = isr_hz_mc;                               // 以 mcycle 时基为准
  if (isr_hz < PWM3PH_FREQ_HZ * 9u / 10u || isr_hz > PWM3PH_FREQ_HZ * 11u / 10u) {
    motion_trip("invalid ISR rate");
    isr_hz = PWM3PH_FREQ_HZ;
  }
  motion_set_isr_rate(isr_hz);
  calibration_set_rate(isr_hz);
  printf("ISR rate: IdleMs=%u Hz, mcycle=%u Hz (dt=%u us, cnt=%u)\n",
         (unsigned)isr_hz_ms, (unsigned)isr_hz_mc,
         (unsigned)dt_us_mc, (unsigned)dcount);
#else
  // foc_step_isr() reads the encoder and ADC on every tick, so it stays off in
  // the recovery image even though the UART monitor remains alive.
  uint32_t isr_hz = PWM3PH_FREQ_HZ;
  motion_set_isr_rate(isr_hz);
  calibration_set_rate(isr_hz);
  printf("SAFE monitor: PWM ISR disabled; UART diagnostics remain available\n");
#endif
  console_init(isr_hz);

  uint32_t up_ms = 0;
  uint32_t last_print_ms = 0;
  uint64_t runtime_start = UTIL_GetMcycle();
  uint32_t cycles_per_ms = SYS_GetSysClkFreq() / 1000u;
  uint32_t isr_base = s_isr_count;
  uint32_t drv_next_ms = 1000u;
  int autorun_fired = 0;
  motion_state_t last_state = motion_state();

  for (;;) {
    UTIL_IdleUs(1000);              // 1ms nominal poll
    up_ms = (uint32_t)((UTIL_GetMcycle() - runtime_start) / cycles_per_ms);

    console_poll(up_ms);

#if MOTION_AUTORUN
    if (console_autorun_cancelled()) autorun_fired = 1;
    if (!autorun_fired && up_ms >= 3000u) {
      autorun_fired = 1;
      printf("auto: turning +1 turn now\n");
      motion_start_turns(1.0f, g_motion_cfg.rev_per_s, g_motion_cfg.vq_max);
    }
    if (!autorun_fired && (up_ms % 1000u) == 0u) {
      printf("auto-run in %u s (press s to cancel)\n", (unsigned)((3000u - up_ms) / 1000u));
    }
#else
    if (!autorun_fired) {
      autorun_fired = 1;
      printf("auto-run OFF: holding torque 0, press 'r' to turn +1 rev\n");
    }
#endif

    if (motion_manual_timed_out()) {
      printf("manual mode auto-released (30 s idle) -- power stage off\n");
    }

    if (FOC_CPLD_BRINGUP && (int32_t)(up_ms - drv_next_ms) >= 0) { // 每秒刷一次故障面
      drv_next_ms = up_ms + 1000u;
      control_poll_driver();
    }

    motion_state_t st = motion_state();
    if (st != last_state) {
      int32_t tr = motion_travelled_raw();
      uint32_t mag = (uint32_t)((tr < 0) ? -(int64_t)tr : tr);
      if (st == MOTION_DONE) {
        int32_t resid = motion_final_err_raw();
        uint32_t rmag = (uint32_t)((resid < 0) ? -resid : resid);
        printf("MOVE DONE: travelled %s%ld raw (%u/1000 turn) in %u ms, "
               "residual %s%u raw\n",
               (tr < 0) ? "-" : "+", (long)mag,
               (unsigned)((uint64_t)mag * 1000u / 16384u), (unsigned)motion_elapsed_ms(),
               (resid < 0) ? "-" : "+", (unsigned)rmag);
        printf("  jitter: |vm| mean=%ld peak=%ld raw/s (ideal %ld raw/s)\n",
               (long)motion_vib_mean(), (long)motion_vib_peak(),
               (long)(g_motion_cfg.rev_per_s * 16384.0f));
        motion_stop();
      } else if (st == MOTION_FAULT) {
        printf("MOVE ABORT: %s (err=%ld raw, vel=%ld raw/s, vq=%ld, t=%u ms)\n",
               motion_fault_msg(), (long)motion_error_raw(),
               (long)motion_vel_rawps(), (long)motion_cmd_q12(),
               (unsigned)motion_elapsed_ms());
      }
      last_state = motion_state();
    }

    if ((uint32_t)(up_ms - last_print_ms) >= 250u) {
      last_print_ms = up_ms;
      uint32_t now = s_isr_count;
      printf("isr=%u ang=%d crc=%u j=%u/%u | st=%d err=%ld vm=%ld vel=%ld vq=%ld i=%ld"
             " t=%u hyb=%d sl=%ld rx=%d\n",
             (unsigned)(now - isr_base), (int)foc_last_angle(),
             (unsigned)foc_crc_errors(),
             (unsigned)motion_jump_hi(), (unsigned)motion_jump_lo(),
             (int)st, (long)motion_error_raw(),
             (long)motion_vel_meas_rawps(), (long)motion_vel_rawps(),
             (long)motion_cmd_q12(), (long)motion_iacc_q12(),
             (unsigned)motion_elapsed_ms(),
             (int)motion_hybrid_enabled(), (long)motion_slip_raw(),
             (int)motion_hold_relaxed());
      isr_base = now;
    }
  }
}
