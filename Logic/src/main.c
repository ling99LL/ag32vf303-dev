/*
 * AG32VF303 4-Channel High-Speed Logic Analyzer Firmware
 * Communication: Dual Interface - USB 2.0 FS CDC-ACM & Hardware UART0 (115200)
 * Protocol: SUMP / Openbench Logic Sniffer (OLS) compatible for PulseView / Sigrok
 *
 * Channel Pinout (Demo Board):
 *   CH0: PIN_41 (GPIO2_0)
 *   CH1: PIN_42 (GPIO2_1)
 *   CH2: PIN_43 (GPIO2_2)
 *   CH3: PIN_44 (GPIO2_3)
 *
 * Test Signal Output:
 *   TEST_OUT: PIN_48 (GPIO2_7)
 *
 * Status LEDs (Active-LOW, GPIO4_1..4):
 *   LED1: Power / Idle / Ready (PIN_34)
 *   LED2: Armed / Waiting Trigger (PIN_33)
 *   LED3: Capturing / Sampling (PIN_32)
 *   LED4: Transmitting Data (PIN_31)
 */

#include "bsp/board_api.h"
#include "tusb.h"
#include "mcu/agm/agrv2k.h"
#include <stdio.h>
#include <string.h>

#define BUFFER_SIZE (64 * 1024) // 64KB sample RAM = 65536 samples
static uint8_t sample_buffer[BUFFER_SIZE];

// Status LEDs (Active-LOW: 0=ON, 1=OFF)
// Mapped in logic_board.ve to:
//   GPIO4_1 -> PIN_12 (LED1: Idle / Status 1)
//   GPIO4_2 -> PIN_13 (LED2: Armed / Status 2)
//   GPIO4_3 -> PIN_14 (LED3: Capturing / Status 3)
//   GPIO4_4 -> PIN_18 (LED4: Transmitting / Status 4)
#define LED1_BIT        GPIO_BIT1 // PIN_12
#define LED2_BIT        GPIO_BIT2 // PIN_13
#define LED3_BIT        GPIO_BIT3 // PIN_14
#define LED4_BIT        GPIO_BIT4 // PIN_18

#define LED_IDLE_BIT    LED1_BIT
#define LED_ARM_BIT     LED2_BIT
#define LED_CAP_BIT     LED3_BIT
#define LED_TX_BIT      LED4_BIT
#define ALL_LEDS        (LED1_BIT | LED2_BIT | LED3_BIT | LED4_BIT)

#define LED_GPIO GPIO4
static inline void set_led(uint8_t bit, int on) {
  if (on) {
    GPIO_SetLow(LED_GPIO, bit);
  } else {
    GPIO_SetHigh(LED_GPIO, bit);
  }
}

static inline void set_all_leds(int on) {
  if (on) {
    GPIO_SetLow(LED_GPIO, ALL_LEDS);
  } else {
    GPIO_SetHigh(LED_GPIO, ALL_LEDS);
  }
}

// SUMP Commands
#define SUMP_RESET            0x00
#define SUMP_RUN              0x01
#define SUMP_ID               0x02
#define SUMP_METADATA         0x04
#define SUMP_XON              0x11
#define SUMP_XOFF             0x13
#define SUMP_TRIGGER_VAL_0    0xC0
#define SUMP_TRIGGER_MASK_0   0xC1
#define SUMP_SET_DIVIDER      0x80
#define SUMP_CAPTURE_SIZE     0x81
#define SUMP_FLAGS            0x82

static uint32_t sample_limit   = 10000;
static uint32_t trigger_mask   = 0;
static uint32_t trigger_val    = 0;
static uint32_t sample_divider = 0;
static uint8_t  active_changroups = 1; // default 1 group (CH0..CH3 in group 0)

// USB Clock Trimming (from official TinyUSB CDC example)
static FCB_IO_TypeDef io_cfg;
static FCB_OSC_TypeDef osc_cfg;
static uint32_t sof_min, sof_max;
#define SOF_ERROR 0.01
#define SOF_COUNT 100

static void osc_cal(uint32_t status) {
  static int count;
  static int cycles;
  cycles += GPTIMER_GetCounter(GPTIMER0);
  GPTIMER_SetCounter(GPTIMER0, 0);
  if (++count < SOF_COUNT) return;

  int step = cycles < (int)sof_min ? 1 : cycles > (int)sof_max ? -1 : 0;
  if (step) {
    osc_cfg.CFG_RCOSCCAL += step;
    FCB_SetOscConfig(&io_cfg, &osc_cfg);
    SYS_ClkSourceTypeDef clk_src = SYS_GetClkSource();
    SYS_SetClkSource(SYS_CLK_SOURCE_HSI);
    FCB_WriteIOConfig(&io_cfg);
    SYS_SetClkSource(clk_src);
  }
  count = 0;
  cycles = 0;
}

static void osc_init(void) {
  while (UART_IsTxBusy(MSG_UART)) {}
  PERIPHERAL_ENABLE(FCB, 0);
  SYS_ClkSourceTypeDef clk_src = SYS_GetClkSource();
  SYS_SetClkSource(SYS_CLK_SOURCE_HSI);
  FCB_ReadIOConfig(&io_cfg);
  SYS_SetClkSource(clk_src);
  FCB_GetOscConfig(&io_cfg, &osc_cfg);

  sof_min = (uint32_t)(SYS_GetPLLFreq() / 1000.0 * SOF_COUNT * (1 - SOF_ERROR));
  sof_max = (uint32_t)(SYS_GetPLLFreq() / 1000.0 * SOF_COUNT * (1 + SOF_ERROR));
  PERIPHERAL_ENABLE(GPTIMER, 0);
  GPTIMER_EnableCounter(GPTIMER0);
  dcd_sof_cb = osc_cal;
}

// Low-level Channel / Port abstractions
static inline void toggle_test_out(void) {
  GPIO_Toggle(GPIO2, GPIO_BIT7);
}

// Unified Send Function (sends to USB CDC if mounted, and always to UART0)
static void comm_send_byte(uint8_t c) {
  if (tud_cdc_connected()) {
    tud_cdc_write(&c, 1);
  }
  while (UART_IsTxFifoFull(UART0)) {}
  UART_TransmitData(UART0, c);
}

static void comm_flush(void) {
  if (tud_cdc_connected()) {
    tud_cdc_write_flush();
  }
}

static void send_metadata(void) {
  comm_send_byte(0x01);
  const char *name = "AG32-LA4";
  for (const char *p = name; *p; p++) comm_send_byte((uint8_t)*p);
  comm_send_byte(0x00);

  // Sample Memory (64KB)
  comm_send_byte(0x21);
  comm_send_byte(0x00);
  comm_send_byte(0x00);
  comm_send_byte(0x01);
  comm_send_byte(0x00);

  // Sample Rate: 20 MSa/s max
  comm_send_byte(0x23);
  comm_send_byte(0x01);
  comm_send_byte(0x31);
  comm_send_byte(0x2D);
  comm_send_byte(0x00);

  // Probes: 4
  comm_send_byte(0x40);
  comm_send_byte(0x04);

  // Protocol version: 2
  comm_send_byte(0x41);
  comm_send_byte(0x02);

  comm_send_byte(0x00);
  comm_flush();
}

static void execute_capture(void) {
  uint32_t count = sample_limit;
  if (count > BUFFER_SIZE) count = BUFFER_SIZE;
  if (count == 0) count = 1024;

  set_all_leds(0);
  set_led(LED_ARM_BIT, 1); // PIN_13 ON

  uint8_t mask = (uint8_t)(trigger_mask & 0x0F);
  uint8_t val  = (uint8_t)(trigger_val & 0x0F);

  if (mask != 0) {
    uint32_t timeout = 5000000;
    while (timeout--) {
      uint8_t curr = GPIO_GetValue(GPIO2, 0x0F);
      if ((curr & mask) == val) break;
      if ((timeout & 0xFF) == 0) toggle_test_out();
    }
  }

  set_led(LED_ARM_BIT, 0);
  set_led(LED_CAP_BIT, 1);

  uint8_t *buf = sample_buffer;
  uint32_t rem = count;

  // If test pattern mode is enabled (sample_divider bit 31 set or default fallback), mix generator;
  // otherwise perform clean 1:1 hardware capture from physical external pins PIN_41..44
  bool test_mode = (sample_divider & 0x80000000) != 0;
  uint32_t eff_div = sample_divider & 0x7FFFFFFF;

  if (eff_div == 0) {
    if (test_mode) {
      uint8_t test_val = 0;
      while (rem--) {
        uint8_t real_in = GPIO_GetValue(GPIO2, 0x0F);
        uint8_t sim_pat = ((test_val >> 2) & 0x01) | (((test_val >> 3) & 0x01) << 1);
        *buf++ = (real_in & 0x0C) | sim_pat;
        test_val++;
        toggle_test_out();
      }
    } else {
      while (rem--) {
        *buf++ = GPIO_GetValue(GPIO2, 0x0F);
        toggle_test_out();
      }
    }
  } else {
    if (test_mode) {
      uint8_t test_val = 0;
      while (rem--) {
        uint8_t real_in = GPIO_GetValue(GPIO2, 0x0F);
        uint8_t sim_pat = ((test_val >> 2) & 0x01) | (((test_val >> 3) & 0x01) << 1);
        *buf++ = (real_in & 0x0C) | sim_pat;
        test_val++;
        volatile uint32_t d = eff_div;
        while (d--) { __asm__ volatile("nop"); }
        toggle_test_out();
      }
    } else {
      while (rem--) {
        *buf++ = GPIO_GetValue(GPIO2, 0x0F);
        volatile uint32_t d = eff_div;
        while (d--) { __asm__ volatile("nop"); }
        toggle_test_out();
      }
    }
  }

  set_led(LED_CAP_BIT, 0);
  set_led(LED_TX_BIT, 1);

  // Reverse buffer in-place to send in bulk (OLS protocol specifies reverse chronological order)
  for (uint32_t i = 0, j = count - 1; i < j; i++, j--) {
    uint8_t tmp = sample_buffer[i];
    sample_buffer[i] = sample_buffer[j];
    sample_buffer[j] = tmp;
  }

  uint8_t groups = active_changroups;
  if (groups == 0 || groups > 4) groups = 1;

  if (groups == 1) {
    // 1 byte per sample (fast direct stream)
    uint32_t sent = 0;
    while (sent < count) {
      tud_task();
      if (tud_cdc_connected()) {
        uint32_t avail = tud_cdc_write_available();
        if (avail > 0) {
          uint32_t to_send = count - sent;
          if (to_send > avail) to_send = avail;
          uint32_t n = tud_cdc_write(&sample_buffer[sent], to_send);
          sent += n;
          tud_cdc_write_flush();
        }
      } else {
        while (sent < count) {
          while (UART_IsTxFifoFull(UART0)) {}
          UART_TransmitData(UART0, sample_buffer[sent++]);
        }
      }
    }
  } else {
    // Multi-group (e.g. 4 bytes per sample): Group 0 has CH0..CH3, other groups 0x00
    uint8_t pkt[128];
    uint32_t sent_samples = 0;
    while (sent_samples < count) {
      tud_task();
      uint32_t batch = (count - sent_samples);
      if (batch > (sizeof(pkt) / groups)) batch = (sizeof(pkt) / groups);

      uint32_t pkt_len = 0;
      for (uint32_t s = 0; s < batch; s++) {
        pkt[pkt_len++] = sample_buffer[sent_samples + s];
        for (uint8_t g = 1; g < groups; g++) {
          pkt[pkt_len++] = 0x00;
        }
      }

      if (tud_cdc_connected()) {
        while (tud_cdc_write_available() < pkt_len) {
          tud_task();
        }
        tud_cdc_write(pkt, pkt_len);
        tud_cdc_write_flush();
      } else {
        for (uint32_t b = 0; b < pkt_len; b++) {
          while (UART_IsTxFifoFull(UART0)) {}
          UART_TransmitData(UART0, pkt[b]);
        }
      }
      sent_samples += batch;
    }
  }
  comm_flush();

  set_led(LED_TX_BIT, 0);
  set_led(LED_IDLE_BIT, 1);
}

static void process_sump_byte(uint8_t b) {
  static uint8_t cmd_buf[5];
  static int cmd_state = 0;

  if (cmd_state == 0) {
    if (b == SUMP_RESET) {
      set_led(ALL_LEDS, 0);
      set_led(LED_IDLE_BIT, 1);
    } else if (b == SUMP_ID) {
      comm_send_byte('1');
      comm_send_byte('A');
      comm_send_byte('L');
      comm_send_byte('S');
      comm_flush();
    } else if (b == SUMP_METADATA) {
      send_metadata();
    } else if (b == SUMP_RUN) {
      execute_capture();
    } else if ((b & 0x80) != 0) {
      // Start 5-byte packet
      cmd_buf[0] = b;
      cmd_state = 1;
    }
  } else {
    cmd_buf[cmd_state++] = b;
    if (cmd_state == 5) {
      cmd_state = 0;
      uint8_t op = cmd_buf[0];
      if (op == SUMP_SET_DIVIDER) {
        // In standard OLS, 0x80 is SET_DIVIDER (24-bit).
        // If cmd_buf[3] == 0 and cmd_buf[4] == 0, check if used as legacy SAMPLE_COUNT:
        uint32_t val24 = (cmd_buf[3] << 16) | (cmd_buf[2] << 8) | cmd_buf[1];
        if (cmd_buf[3] != 0) {
          sample_divider = val24;
        } else {
          // Could be divider or sample_count. Store as divider unless 0x81 is divider.
          sample_divider = val24;
        }
      } else if (op == SUMP_CAPTURE_SIZE) {
        // Standard OLS CMD_CAPTURE_SIZE (0x81)
        uint16_t readcount = (cmd_buf[2] << 8) | cmd_buf[1];
        sample_limit = (readcount + 1) * 4;
      } else if (op == SUMP_TRIGGER_MASK_0) {
        trigger_mask = (cmd_buf[4] << 24) | (cmd_buf[3] << 16) | (cmd_buf[2] << 8) | cmd_buf[1];
      } else if (op == SUMP_TRIGGER_VAL_0) {
        trigger_val = (cmd_buf[4] << 24) | (cmd_buf[3] << 16) | (cmd_buf[2] << 8) | cmd_buf[1];
      } else if (op == SUMP_FLAGS) {
        // Standard OLS CMD_SET_FLAGS (0x82)
        uint16_t flags = (cmd_buf[2] << 8) | cmd_buf[1];
        // In standard OLS / PulseView, bits 2..5 disable changroups 0..3:
        // 0x3C mask: if any disable bit is present, compute enabled groups;
        // if flags == 0 or only test flag (0x08) is passed without standard changroup mask, default to 1 group.
        if ((flags & 0x3C) != 0) {
          uint8_t groups = 0;
          for (uint8_t m = 0x20; m > 0x02; m >>= 1) {
            if ((flags & m) == 0) groups++;
          }
          active_changroups = (groups > 0) ? groups : 1;
        } else {
          active_changroups = 1;
        }

        if (flags & 0x0800) { // CAPTURE_FLAG_INTERNAL_TEST_MODE (bit 11)
          sample_divider |= 0x80000000;
        } else if (flags & 0x08) { // SUMP legacy bit 3 test mode
          sample_divider |= 0x80000000;
        } else {
          sample_divider &= 0x7FFFFFFF;
        }
      }
    }
  }
}

int main(void) {
  board_init();
  osc_init();

  // Initialize TinyUSB Device Stack
  tusb_rhport_init_t dev_init = {
    .role = TUSB_ROLE_DEVICE,
    .speed = TUSB_SPEED_AUTO
  };
  tusb_init(BOARD_TUD_RHPORT, &dev_init);

  if (board_init_after_tusb) {
    board_init_after_tusb();
  }

  // APB Clocks for GPIO2 and GPIO4
  SYS_EnableAPBClock(APB_MASK_GPIO2 | APB_MASK_GPIO4);

  // Setup LEDs
  GPIO_SetOutput(LED_GPIO, ALL_LEDS);
  set_all_leds(0); // All OFF

  // Startup LED Self-Test: sequence PIN_12 -> PIN_13 -> PIN_14 -> PIN_18
  const uint8_t leds[] = { LED1_BIT, LED2_BIT, LED3_BIT, LED4_BIT };
  for (int i = 0; i < 4; i++) {
    set_led(leds[i], 1);
    UTIL_IdleMs(150);
    set_led(leds[i], 0);
  }
  // All blink twice
  for (int i = 0; i < 2; i++) {
    set_all_leds(1);
    UTIL_IdleMs(100);
    set_all_leds(0);
    UTIL_IdleMs(100);
  }
  set_led(LED_IDLE_BIT, 1);

  // Setup 4 LA Inputs: GPIO2_0..3
  GPIO_SetInput(GPIO2, 0x0F);

  // Setup Test Output: GPIO2_7
  GPIO_SetOutput(GPIO2, GPIO_BIT7);
  GPIO_SetLow(GPIO2, GPIO_BIT7);

  printf("\n=== AG32 Logic Analyzer Dual-Mode (USB+UART0) Ready ===\n");

  uint32_t idle_ctr = 0;
  uint32_t led_flow_timer = UTIL_GetTick();
  uint8_t  led_flow_idx = 0;

  while (1) {
    tud_task();

    // Check USB CDC input
    if (tud_cdc_available()) {
      uint8_t c;
      while (tud_cdc_read(&c, 1) > 0) {
        process_sump_byte(c);
      }
    }

    // Check UART0 input
    while (!UART_IsRxFifoEmpty(UART0)) {
      uint8_t c = UART_ReceiveData(UART0);
      process_sump_byte(c);
    }

    // Toggle test output periodically during idle
    if (++idle_ctr > 100000) {
      idle_ctr = 0;
      toggle_test_out();
    }

    // Flowing marquee across PIN_12 -> PIN_13 -> PIN_14 -> PIN_18 during idle
    // Every 250ms shifts to the next LED so you can clearly see all 4 LEDs alive!
    if ((uint32_t)(UTIL_GetTick() - led_flow_timer) >= 250) {
      led_flow_timer = UTIL_GetTick();
      set_all_leds(0);
      set_led(leds[led_flow_idx], 1);
      led_flow_idx = (led_flow_idx + 1) & 0x03;
    }
  }

  return 0;
}
