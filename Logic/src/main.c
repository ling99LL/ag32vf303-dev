/*
 * AG32VF303 4-Channel High-Speed Logic Analyzer Firmware (Plan B: CPLD Hardware Sampler)
 * Communication: Dual Interface - USB 2.0 FS CDC-ACM (COM33) & Hardware UART0 (115200, COM26)
 * Protocol: SUMP / Openbench Logic Sniffer (OLS) compatible for PulseView / Sigrok
 *
 * Hardware Architecture (Plan B):
 *   CPLD Hardware Sampler running at 100~200 MHz synchronous fabric clock
 *   Channel Pinout (QFN32):
 *     CH0: PIN_7  (Input to CPLD sampler)
 *     CH1: PIN_8  (Input to CPLD sampler)
 *     CH2: PIN_9  (Input to CPLD sampler)
 *     CH3: PIN_10 (Input to CPLD sampler, wired to PIN_11)
 *   Hardware Test Generator Output:
 *     TEST_OUT: PIN_11 (Hardware square wave generated in CPLD)
 *
 * Status LEDs (Active-LOW, GPIO4_1..4 on QFN32):
 *   LED1: PIN_12 (Idle / Ready)
 *   LED2: PIN_13 (Armed / Waiting Trigger)
 *   LED3: PIN_14 (Capturing / Sampling)
 *   LED4: PIN_18 (Transmitting Data)
 *
 * CPLD Memory Map (Base: 0x60000000):
 *   0x60000000: REG_CTRL     [0:ARM, 2:FORCE, 3:TEST_EN, 7:4:TRIG_MASK, 11:8:TRIG_VAL, 23:16:CLK_DIV]
 *   0x60000004: REG_STATUS   [0:BUSY, 1:DONE, 2:TRIGGERED, 31:16:WORD_COUNT]
 *   0x60000008: REG_DEPTH    [15:0:WORDS] (up to 1024 words = 8192 samples)
 *   0x6000000C: REG_TEST_DIV [15:0:DIV]
 *   0x60000010: REG_ID       0x4C413332 ("LA32")
 *   0x60001000: RAM_BUFFER   Dual-Port Block RAM (1024 words x 32 bits = 8192 samples)
 */

#include "bsp/board_api.h"
#include "tusb.h"
#include "mcu/agm/agrv2k.h"
#include <stdio.h>
#include <string.h>

// CPLD Hardware Registers
#define CPLD_REG_CTRL      (*(volatile uint32_t *)0x60000000)
#define CPLD_REG_STATUS    (*(volatile uint32_t *)0x60000004)
#define CPLD_REG_DEPTH     (*(volatile uint32_t *)0x60000008)
#define CPLD_REG_TEST_DIV  (*(volatile uint32_t *)0x6000000C)
#define CPLD_REG_ID        (*(volatile uint32_t *)0x60000010)
#define CPLD_REG_TRIG_POS  (*(volatile uint32_t *)0x60000014)
#define CPLD_REG_POST_WORDS (*(volatile uint32_t *)0x60000018)
#define CPLD_RAM_BASE      ((volatile uint32_t *)0x60001000)

#define BUFFER_SIZE (64 * 1024)
static uint8_t sample_buffer[BUFFER_SIZE];

// Status LEDs (Active-LOW: 0=ON, 1=OFF)
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
#define SUMP_TRIGGER_MASK_0   0xC0
#define SUMP_TRIGGER_VAL_0    0xC1
#define SUMP_SET_DIVIDER      0x80
#define SUMP_CAPTURE_SIZE     0x81
#define SUMP_FLAGS            0x82

static uint32_t sample_limit   = 8192;
static uint32_t sample_delay   = 0;
static uint32_t trigger_mask   = 0;
static uint32_t trigger_val    = 0;
static uint32_t sample_divider = 0;
static uint8_t  active_changroups = 1;
static bool     rle_enabled = false;

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

static inline void toggle_test_out(void) {
  GPIO_Toggle(GPIO2, GPIO_BIT7);
}

// Communication Handlers
static void comm_send_byte(uint8_t c) {
  if (tud_cdc_connected()) {
    tud_cdc_write(&c, 1);
    // Non-blocking mirror to UART if FIFO has room, preventing 115200 baud bottleneck on USB
    if (!UART_IsTxFifoFull(UART0)) {
      UART_TransmitData(UART0, c);
    }
  } else {
    // USB not active: reliable blocking send over UART0
    while (UART_IsTxFifoFull(UART0)) {}
    UART_TransmitData(UART0, c);
  }
}

static void comm_flush(void) {
  if (tud_cdc_connected()) {
    tud_cdc_write_flush();
  }
}

static void send_metadata(void) {
  comm_send_byte(0x01);
  const char *name = "AG32-PlanB";
  for (const char *p = name; *p; p++) comm_send_byte((uint8_t)*p);
  comm_send_byte(0x00);

  // Sample Memory: 8192 samples (CPLD BRAM hardware buffer)
  comm_send_byte(0x21);
  comm_send_byte(0x00);
  comm_send_byte(0x00);
  comm_send_byte(0x20); // 8192 = 0x2000
  comm_send_byte(0x00);

  // Max Sample Rate: 100 MSa/s (100,000,000 Hz = 0x05F5E100)
  comm_send_byte(0x23);
  comm_send_byte(0x05);
  comm_send_byte(0xF5);
  comm_send_byte(0xE1);
  comm_send_byte(0x00);

  // Probes: 4 (CH0..CH3)
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
  if (count > 8192) count = 8192; // Max CPLD BRAM capacity

  set_all_leds(0);
  set_led(LED_ARM_BIT, 1); // PIN_13 ON (Waiting Trigger)

  // Check CPLD Hardware Sampler presence
  bool cpld_ok = (CPLD_REG_ID == 0x4C413332);

  if (cpld_ok) {
    // -----------------------------------------------------------------------
    // Plan B: CPLD Hardware Sampling
    // -----------------------------------------------------------------------
    uint32_t words_needed = (count + 7) / 8;
    if (words_needed > 1024) words_needed = 1024;
    CPLD_REG_DEPTH = words_needed;

    // Pre-trigger vs Post-trigger calculation:
    // If sample_delay is configured (post-trigger samples), map to post_trig_words
    uint32_t post_words = (sample_delay > 0) ? ((sample_delay + 7) / 8) : words_needed;
    if (post_words > words_needed) post_words = words_needed;
    if (post_words == 0) post_words = words_needed;
    CPLD_REG_POST_WORDS = post_words;

    uint8_t mask = (uint8_t)(trigger_mask & 0x0F);
    uint8_t val  = (uint8_t)(trigger_val & 0x0F);

    uint32_t eff_div = sample_divider & 0x7FFFFFFF;
    uint32_t clk_div = (eff_div > 0) ? (eff_div & 0xFF) : 0;

    // Adaptively tune PIN_11 test wave generator frequency for optimal scope display:
    if (clk_div == 0) {
      CPLD_REG_TEST_DIV = 99;    // 1 MHz square wave (200MHz / 200)
    } else if (clk_div == 1) {
      CPLD_REG_TEST_DIV = 199;   // 500 kHz square wave
    } else if (clk_div <= 9) {
      CPLD_REG_TEST_DIV = 999;   // 100 kHz square wave
    } else {
      CPLD_REG_TEST_DIV = 4999;  // 20 kHz square wave for low-speed captures
    }

    // ARM CPLD Sampler (bit 0=ARM, bit 3=TEST_EN, bits [7:4]=mask, bits [11:8]=val, bit 12=edge_mode, bits [23:16]=clk_div)
    // If mask is set and edge mode requested, or default edge detection on masked channel
    uint32_t edge_bit = (mask != 0) ? (1 << 12) : 0;
    uint32_t ctrl_val = (1 << 0) | (1 << 3) | ((uint32_t)mask << 4) | ((uint32_t)val << 8) | edge_bit | (clk_div << 16);
    CPLD_REG_CTRL = ctrl_val;

    // Wait for trigger and capture with continuous USB servicing and abort checking
    uint32_t wait_start = UTIL_GetTick();
    bool aborted = false;

    while (1) {
      tud_task();
      uint32_t stat = CPLD_REG_STATUS;

      if (stat & (1 << 2)) { // TRIGGERED
        set_led(LED_ARM_BIT, 0);
        set_led(LED_CAP_BIT, 1); // PIN_14 ON
      }

      if (stat & (1 << 1)) { // DONE
        break;
      }

      // Check if user aborts from PulseView
      if (tud_cdc_available()) {
        uint8_t peek_b;
        tud_cdc_read(&peek_b, 1);
        if (peek_b == SUMP_RESET) {
          CPLD_REG_CTRL = (1 << 3); // De-arm
          aborted = true;
          break;
        }
      }

      // Unattended trigger timeout guard (1500 ms)
      if (UTIL_GetTick() - wait_start > 1500) {
        // Force complete capture so communication never deadlocks
        CPLD_REG_CTRL = ctrl_val | (1 << 2); // Force trigger
        set_led(LED_ARM_BIT, 0);
        set_led(LED_CAP_BIT, 1);
        UTIL_IdleMs(2);
        break;
      }
    }

    if (aborted) {
      set_all_leds(0);
      set_led(LED_IDLE_BIT, 1);
      return;
    }

    set_led(LED_CAP_BIT, 0);
    set_led(LED_TX_BIT, 1); // PIN_18 ON

    // Direct reverse unpacking from BRAM (Zero-Copy inversion)
    // CPLD stored samples linearly: word 0 contains samples 0..7 (sample 0 at bits 3:0).
    // SUMP expects reverse chronological order: latest sample first!
    int32_t target_idx = 0;
    for (int32_t w = (int32_t)words_needed - 1; w >= 0; w--) {
      uint32_t word = CPLD_RAM_BASE[w];
      for (int nibble = 7; nibble >= 0; nibble--) {
        if (target_idx < (int32_t)count) {
          sample_buffer[target_idx++] = (uint8_t)((word >> (nibble * 4)) & 0x0F);
        }
      }
    }

    // Keep test generator running
    CPLD_REG_CTRL = (1 << 3);
  } else {
    // Software Fallback Polling
    set_led(LED_ARM_BIT, 0);
    set_led(LED_CAP_BIT, 1);
    for (uint32_t i = 0; i < count; i++) {
      sample_buffer[count - 1 - i] = GPIO_GetValue(GPIO2, 0x0F);
    }
    set_led(LED_CAP_BIT, 0);
    set_led(LED_TX_BIT, 1);
  }

  uint8_t groups = active_changroups;
  if (groups == 0 || groups > 4) groups = 1;

  // Stream data over USB CDC with 64-byte packet optimization and timeout guard
  uint32_t tx_start = UTIL_GetTick();

  if (rle_enabled && groups == 1) {
    // Standard SUMP RLE (Run-Length Encoding) Compression:
    // When a sample repeats, emit: Sample | 0x80 (if count repeats) or count bytes
    // In SUMP: bit 7 = 1 indicates repeat count payload, bit 7 = 0 indicates sample value
    uint32_t idx = 0;
    while (idx < count) {
      tud_task();
      uint8_t cur_val = sample_buffer[idx] & 0x0F;
      uint32_t run_len = 1;
      while ((idx + run_len) < count && (sample_buffer[idx + run_len] & 0x0F) == cur_val && run_len < 0x3FFF) {
        run_len++;
      }
      idx += run_len;

      // Send the sample
      comm_send_byte(cur_val);

      // If repeated, send count with bit 7 set
      if (run_len > 1) {
        uint32_t repeats = run_len - 1;
        while (repeats > 0) {
          uint8_t chunk = repeats & 0x7F;
          repeats >>= 7;
          if (repeats > 0) {
            comm_send_byte(0x80 | chunk);
          } else {
            comm_send_byte(0x80 | chunk);
          }
        }
      }
      if (UTIL_GetTick() - tx_start > 1000) break;
    }
  } else if (groups == 1) {
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
          if (sent >= count || avail <= 64) {
            tud_cdc_write_flush();
          }
          tx_start = UTIL_GetTick();
        }
      } else {
        while (sent < count) {
          while (UART_IsTxFifoFull(UART0)) {}
          UART_TransmitData(UART0, sample_buffer[sent++]);
        }
      }
      if (UTIL_GetTick() - tx_start > 500) {
        break;
      }
    }
  } else {
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
        uint32_t wait_avail = UTIL_GetTick();
        while (tud_cdc_write_available() < pkt_len) {
          tud_task();
          if (UTIL_GetTick() - wait_avail > 200) break;
        }
        tud_cdc_write(pkt, pkt_len);
        tud_cdc_write_flush();
        tx_start = UTIL_GetTick();
      } else {
        for (uint32_t b = 0; b < pkt_len; b++) {
          while (UART_IsTxFifoFull(UART0)) {}
          UART_TransmitData(UART0, pkt[b]);
        }
      }
      sent_samples += batch;
      if (UTIL_GetTick() - tx_start > 500) break;
    }
  }
  comm_flush();

  set_led(LED_TX_BIT, 0);
  set_led(LED_IDLE_BIT, 1); // PIN_12 ON
}

static void process_sump_byte(uint8_t b) {
  static uint8_t cmd_buf[5];
  static int cmd_state = 0;

  if (cmd_state == 0) {
    if (b == SUMP_RESET) {
      set_all_leds(0);
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
      cmd_buf[0] = b;
      cmd_state = 1;
    }
  } else {
    cmd_buf[cmd_state++] = b;
    if (cmd_state == 5) {
      cmd_state = 0;
      uint8_t op = cmd_buf[0];
      if (op == SUMP_SET_DIVIDER) {
        uint32_t val24 = (cmd_buf[3] << 16) | (cmd_buf[2] << 8) | cmd_buf[1];
        sample_divider = val24;
      } else if (op == SUMP_CAPTURE_SIZE) {
        uint16_t readcount = (cmd_buf[2] << 8) | cmd_buf[1];
        uint16_t delaycount = (cmd_buf[4] << 8) | cmd_buf[3];
        sample_limit = (readcount + 1) * 4;
        sample_delay = (delaycount + 1) * 4;
      } else if (op >= 0xC0 && op <= 0xCF) {
        // Standard SUMP / OLS: (op & 0x03) == 0x00 is MASK, 0x01 is VALUE
        uint32_t val32 = (cmd_buf[4] << 24) | (cmd_buf[3] << 16) | (cmd_buf[2] << 8) | cmd_buf[1];
        if ((op & 0x03) == 0x00) {
          trigger_mask = val32;
        } else if ((op & 0x03) == 0x01) {
          trigger_val = val32;
        }
      } else if (op == SUMP_FLAGS) {
        uint16_t flags = (cmd_buf[2] << 8) | cmd_buf[1];
        rle_enabled = ((flags & 0x0100) != 0);
        if ((flags & 0x3C) != 0) {
          uint8_t groups = 0;
          for (uint8_t m = 0x20; m > 0x02; m >>= 1) {
            if ((flags & m) == 0) groups++;
          }
          active_changroups = (groups > 0) ? groups : 1;
        } else {
          active_changroups = 1;
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
  set_all_leds(0);

  // Startup LED Self-Test
  const uint8_t leds[] = { LED1_BIT, LED2_BIT, LED3_BIT, LED4_BIT };
  for (int i = 0; i < 4; i++) {
    set_led(leds[i], 1);
    UTIL_IdleMs(100);
    set_led(leds[i], 0);
  }
  for (int i = 0; i < 2; i++) {
    set_all_leds(1);
    UTIL_IdleMs(60);
    set_all_leds(0);
    UTIL_IdleMs(60);
  }
  set_led(LED_IDLE_BIT, 1); // LED1 (PIN_12) ON

  printf("\n=== AG32 Plan B Logic Analyzer (CPLD Sampler) Ready ===\n");
  if (CPLD_REG_ID == 0x4C413332) {
    printf("[CPLD] Hardware Sampler Active: ID = 0x%08X (LA32)\n", (unsigned int)CPLD_REG_ID);
  }

  uint32_t led_flow_timer = UTIL_GetTick();
  uint8_t  led_flow_idx = 0;

  while (1) {
    tud_task();

    if (tud_cdc_available()) {
      uint8_t c;
      while (tud_cdc_available()) {
        tud_cdc_read(&c, 1);
        process_sump_byte(c);
      }
    }

    while (!UART_IsRxFifoEmpty(UART0)) {
      uint8_t c = UART_ReceiveData(UART0);
      process_sump_byte(c);
    }

    // Idle heartbeat: LED1 stays lit, soft pulse every 2s
    if (UTIL_GetTick() - led_flow_timer > 2000) {
      led_flow_timer = UTIL_GetTick();
      set_led(leds[(led_flow_idx++) % 4], 1);
      UTIL_IdleMs(25);
      set_all_leds(0);
      set_led(LED_IDLE_BIT, 1);
    }
  }
  return 0;
}