/*
 * AG32VF303 4-Channel High-Speed Logic Analyzer Firmware (Plan B: CPLD Hardware Sampler)
 * Communication: Dual Interface - USB 2.0 FS CDC-ACM (COM33) & Hardware UART0 (115200, COM26)
 * Protocol: SUMP / Openbench Logic Sniffer (OLS) compatible for PulseView / Sigrok
 *
 * Hardware Architecture (Plan B):
 *   CPLD Hardware Sampler: 200 MHz fabric clock; SUMP divider D -> sample rate = 100 MHz/(D+1) (0..100 MSa/s, within measured Fmax 121.9 MHz)
 *   Channel Pinout (QFN32, board CH1..CH4; firmware sampler bits 0..3):
 *     CH1: PIN_7  (Input to CPLD sampler)
 *     CH2: PIN_8  (Input to CPLD sampler)
 *     CH3: PIN_9  (Input to CPLD sampler)
 *     CH4: PIN_10 (Input to CPLD sampler, self-test loopback target)
 *   Signal Generator / Trigger Outputs:
 *     PIN_11: DAC0 analog waveform output (sine/square/sawtooth/triangle via
 *             MCU DMA wave-table playback; sample rate up to 100 MSa/s)
 *     PIN_5 : digital output, source muxed in the CPLD:
 *             1 = square wave 1 Hz..100 MHz (f = 100 MHz/(div+1))
 *             0 = trigger/pulse engine (delay -> level/pulse, host triggered)
 *
 * Status LEDs (Active-LOW, GPIO4_1..4 on QFN32):
 *   LED1: PIN_19 (Idle / Ready)
 *   LED2: PIN_18 (Armed / Waiting Trigger)
 *   LED3: PIN_13 (Capturing / Sampling)
 *   LED4: PIN_14 (Transmitting Data)
 *
 * CPLD Memory Map (Base: 0x60000000):
 *   0x60000000: REG_CTRL     [0:ARM, 2:FORCE, 3:SQ_EN, 7:4:TRIG_MASK, 11:8:TRIG_VAL, 23:16:CLK_DIV]
 *   0x60000004: REG_STATUS   [0:BUSY, 1:DONE, 2:TRIGGERED, 31:16:WORD_COUNT]
 *   0x60000008: REG_DEPTH    [15:0:WORDS] (up to 1024 words = 8192 samples)
 *   0x6000000C: REG_SQ_DIV   [15:0]=A [31:16]=B; square f = 100 MHz/((A+1)*(B+1))
 *   0x60000010: REG_ID       0x4C413332 ("LA32")
 *   0x60000014: REG_TRIG_POS [25:16: trigger word index]
 *   0x60000018: REG_POST_WORDS [15:0]
 *   0x60000020: REG_P5_CFG   [1:0:MODE, 2:LEVEL, 3:IDLE, 5:4:PRESCALE, 8:SQ_SEL]
 *   0x60000024: REG_P5_DELAY [31:0] ticks (tick = 10 ns * 10^prescale)
 *   0x60000028: REG_P5_WIDTH [31:0] pulse width in ticks
 *   0x6000002C: REG_P5_CTRL  W:[0:ARM, 1:FIRE, 2:CLEAR]  R:[0:BUSY, 1:DONE, 2:OUT]
 *   0x60000030: REG_P5_REMAIN [31:0] remaining ticks
 *   0x60001000: RAM_BUFFER   Dual-Port Block RAM (1024 words x 32 bits = 8192 samples)
 *   0x60003000: DAC0_CTRL    [0:EN, 1:BUFEN, 2:DMAEN, 31:16:RATE_DIV]
 *   0x60003004: DAC0_DATA    [9:0] DAC sample code
 *
 * Generator control protocol (SUMP extension: 5-byte frames = opcode + 4 LE bytes):
 *   0x84 GEN_WAVE   [7:0]type(0=sine,1=square,2=saw,3=tri) [15:8]amp% [16]enable
 *   0x85 GEN_FREQ   32-bit frequency in Hz
 *   0x86 P5_CFG     same packing as REG_P5_CFG
 *   0x87 P5_DELAY   32-bit delay ticks
 *   0x88 P5_WIDTH   32-bit pulse width ticks
 *   0x89 P5_CTRL    [0]arm [1]fire [2]clear
 *   0x8A SQ_FREQ    32-bit square-wave frequency in Hz (PIN_5)
 *   0x8B GEN_RATE   DAC sample-rate cap in Hz
 *   0x8C GET_INFO   -> [0xAA][20][...] response frame
 *   0x8D P5_QUERY   -> [0xAA][7][...] response frame
 */

#include "bsp/board_api.h"
#include "tusb.h"
#include "mcu/agm/agrv2k.h"
#include <stdio.h>
#include <string.h>
#include <math.h>

// CPLD Hardware Registers
#define CPLD_REG_CTRL      (*(volatile uint32_t *)0x60000000)
#define CPLD_REG_STATUS    (*(volatile uint32_t *)0x60000004)
#define CPLD_REG_DEPTH     (*(volatile uint32_t *)0x60000008)
#define CPLD_REG_TEST_DIV  (*(volatile uint32_t *)0x6000000C)
#define CPLD_REG_ID        (*(volatile uint32_t *)0x60000010)
#define CPLD_REG_TRIG_POS  (*(volatile uint32_t *)0x60000014)
#define CPLD_REG_POST_WORDS (*(volatile uint32_t *)0x60000018)
#define CPLD_REG_P5_CFG    (*(volatile uint32_t *)0x60000020)
#define CPLD_REG_P5_DELAY  (*(volatile uint32_t *)0x60000024)
#define CPLD_REG_P5_WIDTH  (*(volatile uint32_t *)0x60000028)
#define CPLD_REG_P5_CTRL   (*(volatile uint32_t *)0x6000002C)
#define CPLD_REG_P5_REMAIN (*(volatile uint32_t *)0x60000030)
#define CPLD_RAM_BASE      ((volatile uint32_t *)0x60001000)

// DAC0 APB window inside the CPLD (analog waveform output on PIN_11)
#define DAC0_REG_CTRL      (*(volatile uint32_t *)0x60003000)
#define DAC0_REG_DATA      (*(volatile uint32_t *)0x60003004)
#define DAC0_DMA_REQ       4  /* EXT_DMA3_REQ */

// Generator control protocol opcodes (SUMP extension, 5-byte frames)
#define GEN_OP_WAVE        0x84
#define GEN_OP_FREQ        0x85
#define GEN_OP_P5_CFG      0x86
#define GEN_OP_P5_DELAY    0x87
#define GEN_OP_P5_WIDTH    0x88
#define GEN_OP_P5_CTRL     0x89
#define GEN_OP_SQ_FREQ     0x8A
#define GEN_OP_RATE_CAP    0x8B
#define GEN_OP_GET_INFO    0x8C
#define GEN_OP_P5_QUERY    0x8D
#define GEN_RESP_SYNC      0xAA
#define CMD_U32(cb) ((uint32_t)(cb)[1] | ((uint32_t)(cb)[2] << 8) | \
                     ((uint32_t)(cb)[3] << 16) | ((uint32_t)(cb)[4] << 24))

#define BUFFER_SIZE (64 * 1024)
static uint8_t sample_buffer[BUFFER_SIZE];

// Status LEDs (Active-LOW: 0=ON, 1=OFF)
#define LED1_BIT        GPIO_BIT1 // PIN_19
#define LED2_BIT        GPIO_BIT2 // PIN_18
#define LED3_BIT        GPIO_BIT3 // PIN_13
#define LED4_BIT        GPIO_BIT4 // PIN_14

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

// ===========================================================================
// Signal Generator subsystem
//   PIN_11: DAC0 wave engine (DMA circular playback of a waveform table)
//   PIN_5 : trigger/pulse engine OR digital square generator (CPLD mux)
// ===========================================================================
static void comm_send_byte(uint8_t c);
static void comm_flush(void);

#define GEN_VER_MAJOR       1
#define GEN_VER_MINOR       1
#define WAVE_TABLE_MAX      2048
#define DAC_SAMPLE_RATE     100000000u  /* APB clock: DAC update is 100MHz/(div+1) */

static uint32_t wave_buf[WAVE_TABLE_MAX] __attribute__((aligned(4)));
static DMAC_LLI_TypeDef dac_lli;

static uint8_t  gen_type   = 0;              /* 0=sine 1=square 2=saw 3=triangle */
static uint8_t  gen_amp    = 100;            /* amplitude % (0..100) */
static uint8_t  gen_en     = 0;              /* DAC output enable */
static uint32_t gen_freq   = 1000;           /* requested frequency (Hz) */
static uint32_t gen_actual = 0;              /* achieved frequency (Hz) */
static uint32_t gen_L      = 512;            /* wave table length */
static uint32_t gen_div    = 0;              /* DAC rate divider */
/* Max DAC sample rate. The AHB->APB DMA handshake needs ~16 bus cycles per
 * transfer; with the repeating DMA buffer a sample interval of >= 20 cycles
 * is fully stable, so rates above 100MHz/20 = 5 MSa/s lose beats (observed
 * +/-4..16%, sometimes halving). At 5 MSa/s pacing is exact; the only residual
 * is the rate-divider grid: typical +/-0.5%, 0% wherever 100MHz divides cleanly. */
static uint32_t gen_rate_cap = 5000000u;
static uint8_t  p5_sq_sel  = 1;              /* PIN_5 source: 1=square 0=engine */

/* Minimum samples per period per waveform: sine, square, saw, triangle */
static const uint16_t gen_min_pts[4] = { 8, 2, 4, 8 };

static uint32_t gen_log2(uint32_t v) {
  uint32_t n = 0;
  while (v > 1) { v >>= 1; n++; }
  return n;
}

/* Pick the table length and DAC rate divider for the requested frequency */
static void gen_compute(void) {
  uint32_t f = gen_freq;
  uint16_t minpts = gen_min_pts[gen_type & 3];
  uint32_t lmax, lmin, L, div;

  if (f < 1) f = 1;
  if (f > gen_rate_cap / minpts) f = gen_rate_cap / minpts;  /* clamp */

  lmax = gen_rate_cap / f;                     /* sample-rate cap constraint */
  lmin = 1;
  while ((uint64_t)f * lmin * 65536u < DAC_SAMPLE_RATE) lmin *= 2; /* div<=65535 */
  if (lmin < minpts) lmin = minpts;

  L = minpts;
  for (uint32_t cand = WAVE_TABLE_MAX; cand >= minpts; cand >>= 1) {
    if (cand < lmin) break;
    if (cand > lmax) continue;
    L = cand;
    break;
  }

  gen_L = L;
  div = (DAC_SAMPLE_RATE + (f * L) / 2) / (f * L);  /* rounded 100M/(f*L) */
  if (div > 0) div -= 1;
  if (div > 65535u) div = 65535u;
  gen_div = div;
  gen_actual = (uint32_t)((uint64_t)DAC_SAMPLE_RATE /
                          ((uint64_t)(gen_div + 1) * gen_L));
}

/* Fill wave_buf with the current waveform scaled by amplitude */
static void gen_fill_table(void) {
  const float two_pi = 6.28318530718f;
  float amp = (gen_amp > 100) ? 1.0f : (float)gen_amp / 100.0f;

  for (uint32_t i = 0; i < gen_L; i++) {
    float ph = (float)i / (float)gen_L;
    float v;
    switch (gen_type & 3) {
      case 0:  v = sinf(ph * two_pi); break;
      case 1:  v = (ph < 0.5f) ? 1.0f : -1.0f; break;
      case 2:  v = ph * 2.0f - 1.0f; break;
      case 3:  v = (ph < 0.5f) ? (ph * 4.0f - 1.0f) : (3.0f - ph * 4.0f); break;
      default: v = 0.0f; break;
    }
    v *= amp;
    if (v > 1.0f)  v = 1.0f;
    if (v < -1.0f) v = -1.0f;
    wave_buf[i] = (uint32_t)((v + 1.0f) * 0.5f * 1023.0f + 0.5f);
  }

  /* Repeat the waveform to fill the whole DMA buffer. The DMAC reloads its
   * LLI once per transferSize samples; with transferSize = L reloads happen
   * every few samples for tiny tables (e.g. the 2-point square at 2.5 MHz)
   * and the LLI fetch steals request slots, breaking the pacing. Filling
   * the buffer makes the reload rate 1/2048 and every sample interval exact. */
  for (uint32_t r = gen_L; r < WAVE_TABLE_MAX; r++) {
    wave_buf[r] = wave_buf[r % gen_L];
  }
}

/* Reconfigure DMA + DAC with the current settings (circular playback) */
static void gen_apply(void) {
  DMAC_DisableChannel(DMAC_CHANNEL0);
  if (!gen_en) {
    DAC0_REG_CTRL = 0;               /* output off */
    return;
  }
  gen_fill_table();

  dac_lli.SrcAddr = (uint32_t)wave_buf;
  dac_lli.DstAddr = (uint32_t)&DAC0_REG_DATA;
  dac_lli.LLI     = (uint32_t)&dac_lli;   /* self loop = circular */
  dac_lli.Control = DMAC_MakeControl(DMAC_ADDR_INCR_ON, DMAC_ADDR_INCR_OFF,
                                     DMAC_WIDTH_32_BIT, DMAC_WIDTH_32_BIT,
                                     DMAC_BURST_1, DMAC_BURST_1,
                                     WAVE_TABLE_MAX, DISABLE); /* full repeated buffer */
  DMAC_ConfigLLI(DMAC_CHANNEL0, DMAC_MEM_TO_PERIPHERAL_DMA_CTRL,
                 0, DAC0_DMA_REQ, (uint32_t)&dac_lli);
  DMAC_EnableChannel(DMAC_CHANNEL0);

  DAC0_REG_CTRL = (1u << 0) | (1u << 1);                                  /* EN|BUFEN */
  DAC0_REG_CTRL = (DAC0_REG_CTRL & 0xFFFFu) | (1u << 2) | (gen_div << 16);/* DMAEN|DIV */
}

/* Response frame: [0xAA][len][payload...] (queried by the host GUI) */
static void gen_send_frame(const uint8_t *payload, uint8_t len) {
  comm_send_byte(GEN_RESP_SYNC);
  comm_send_byte(len);
  for (uint8_t i = 0; i < len; i++) comm_send_byte(payload[i]);
  comm_flush();
}

static void gen_send_info(void) {
  uint8_t b[20];
  uint32_t st = CPLD_REG_P5_CTRL;
  uint32_t flags = (gen_en ? 1u : 0u) | ((p5_sq_sel ? 1u : 0u) << 1);
  if (st & 1u) flags |= (1u << 2);
  if (st & 2u) flags |= (1u << 3);

  b[0] = GEN_VER_MAJOR;
  b[1] = GEN_VER_MINOR;
  b[2] = gen_type;
  b[3] = gen_amp;
  b[4] = (uint8_t)(gen_freq);
  b[5] = (uint8_t)(gen_freq >> 8);
  b[6] = (uint8_t)(gen_freq >> 16);
  b[7] = (uint8_t)(gen_freq >> 24);
  b[8] = (uint8_t)(gen_actual);
  b[9] = (uint8_t)(gen_actual >> 8);
  b[10] = (uint8_t)(gen_actual >> 16);
  b[11] = (uint8_t)(gen_actual >> 24);
  b[12] = (uint8_t)flags;
  b[13] = (uint8_t)gen_log2(gen_L);
  b[14] = (uint8_t)(gen_rate_cap);
  b[15] = (uint8_t)(gen_rate_cap >> 8);
  b[16] = (uint8_t)(gen_rate_cap >> 16);
  b[17] = (uint8_t)(gen_rate_cap >> 24);
  b[18] = 0;
  b[19] = 0;
  gen_send_frame(b, 20);
}

static void gen_send_p5_status(void) {
  uint8_t b[7];
  uint32_t st  = CPLD_REG_P5_CTRL;
  uint32_t rem = CPLD_REG_P5_REMAIN;
  uint32_t cfg = CPLD_REG_P5_CFG;
  b[0] = (uint8_t)(st & 0x07u);           /* [0]busy [1]done [2]out */
  b[1] = (uint8_t)(rem);
  b[2] = (uint8_t)(rem >> 8);
  b[3] = (uint8_t)(rem >> 16);
  b[4] = (uint8_t)(rem >> 24);
  b[5] = (uint8_t)(cfg & 0xFFu);
  b[6] = (uint8_t)((cfg >> 8) & 0x01u);
  gen_send_frame(b, 7);
}

/* Program the PIN_5 square generator for a period of n_cycles 200MHz cycles:
 * f = 100 MHz / ((A + 1) * (B + 1)) with A/B 16-bit reload values. */
static void sq_set_n(uint32_t n_cycles) {
  uint32_t a1, b1;
  if (n_cycles < 1u) n_cycles = 1u;
  if (n_cycles <= 65536u) {
    a1 = n_cycles;
    b1 = 1u;
  } else {
    b1 = (n_cycles + 65535u) / 65536u;      /* ceil(n / 65536), >= 2 */
    a1 = (n_cycles + b1 / 2u) / b1;         /* round(n / b1) */
    if (a1 > 65536u) a1 = 65536u;
    if (a1 < 1u) a1 = 1u;
  }
  CPLD_REG_TEST_DIV = ((b1 - 1u) << 16) | (a1 - 1u);
}

/* Square-wave frequency in Hz (12-digit precision limited by 200MHz clock) */
static void sq_set_freq(uint32_t f) {
  if (f < 1u) f = 1u;
  if (f > 100000000u) f = 100000000u;
  sq_set_n((uint32_t)((100000000ULL + f / 2u) / f));
}

/* Raw divider path (SUMP 0x83 extension): f = 100 MHz / (div + 1) */
static void sq_set_div(uint32_t div) {
  if (div >= 0xFFFFFFFEu) return;           /* sentinel / invalid */
  sq_set_n(div + 1u);
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
#define SUMP_TEST_DIV         0x83

static uint32_t sample_limit   = 8192;
static uint32_t sample_delay   = 0;
static uint32_t trigger_mask   = 0;
static uint32_t trigger_val    = 0;
static uint32_t sample_divider = 0;
static uint32_t test_div_override = 0xFFFFFFFFu;  // 0xFFFFFFFF = auto (gear table)
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
  set_led(LED_ARM_BIT, 1); // PIN_18 ON (Waiting Trigger)

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
    // SUMP delaycount = samples AFTER trigger (libsigrok: delay = read*(1-ratio));
    // pre_words + post_words = words_needed. delaycount==0 -> pure pre-trigger.
    uint32_t post_words = (sample_delay > 0) ? ((sample_delay + 7) / 8) : 1;
    if (post_words > words_needed) post_words = words_needed;
    if (post_words == 0) post_words = 1;
    uint32_t pre_words = words_needed - post_words;
    CPLD_REG_POST_WORDS = post_words;

    uint8_t mask = (uint8_t)(trigger_mask & 0x0F);
    uint8_t val  = (uint8_t)(trigger_val & 0x0F);

    uint32_t eff_div = sample_divider & 0x7FFFFFFF;
    uint32_t clk_div = (eff_div > 0) ? (eff_div & 0xFFFFu) : 0; // 16-bit divider (1.5 kSa/s .. 100 MSa/s)

    // Square-wave self-test gear (PIN_5 digital output): f = 100 MHz / (div + 1).
    // Only applied while PIN_5 is in square mode; gears are Nyquist-aligned so
    // loopback can be verified on CH1..CH4.
    if (test_div_override != 0xFFFFFFFFu) {
      sq_set_div(test_div_override);                      // manual frequency (SUMP 0x83/0x8A)
    } else if (p5_sq_sel) {
      if (clk_div == 0) {
        CPLD_REG_TEST_DIV = 1;    // 50 MHz square wave, 2 samples/period @ 100 MSa/s
      } else if (clk_div == 1) {
        CPLD_REG_TEST_DIV = 3;    // 25 MHz square wave, 2 samples/period @ 50 MSa/s
      } else if (clk_div <= 4) {
        CPLD_REG_TEST_DIV = 9;    // 10 MHz square wave, 2 samples/period @ 20 MSa/s
      } else {
        CPLD_REG_TEST_DIV = 4999; // 20 kHz square wave for low-speed captures
      }
    }

    // ARM CPLD Sampler (bit 0=ARM, bit 3=TEST_EN, bits [7:4]=mask, bits [11:8]=val, bit 12=edge_mode, bits [23:16]=clk_div)
    // In SUMP/OLS protocol, 0xC0/0xC1 defines stage 0 mask & value for hardware level match.
    // Level match provides instantaneous hardware triggering on incoming digital levels/waveforms.
    uint32_t edge_bit = (trigger_mask & 0x10) ? (1 << 12) : 0; // bit 4 set in mask selects edge mode
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
        set_led(LED_CAP_BIT, 1); // PIN_13 ON
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
    set_led(LED_TX_BIT, 1); // PIN_14 ON

    // OLS devices send their buffer backwards (newest first); libsigrok/PulseView
    // reverse it again. Each CPLD word holds {s7..s0} with the newest sample in
    // bits 31:28. The circular pre-trigger window starts at first_word and wraps
    // at words_needed.
    uint32_t trig_pos_w = (CPLD_REG_TRIG_POS >> 16) & 0x3FFu;
    uint32_t first_word = (trig_pos_w + words_needed - pre_words) % words_needed;

    int32_t target_idx = 0;
    for (int32_t k = (int32_t)words_needed - 1; k >= 0; k--) {
      uint32_t wi   = (first_word + (uint32_t)k) % words_needed;
      uint32_t word = CPLD_RAM_BASE[wi];
      if ((target_idx + 8) <= (int32_t)count) {
        sample_buffer[target_idx + 0] = (uint8_t)((word >> 28) & 0x0F);
        sample_buffer[target_idx + 1] = (uint8_t)((word >> 24) & 0x0F);
        sample_buffer[target_idx + 2] = (uint8_t)((word >> 20) & 0x0F);
        sample_buffer[target_idx + 3] = (uint8_t)((word >> 16) & 0x0F);
        sample_buffer[target_idx + 4] = (uint8_t)((word >> 12) & 0x0F);
        sample_buffer[target_idx + 5] = (uint8_t)((word >> 8)  & 0x0F);
        sample_buffer[target_idx + 6] = (uint8_t)((word >> 4)  & 0x0F);
        sample_buffer[target_idx + 7] = (uint8_t)(word         & 0x0F);
        target_idx += 8;
      } else {
        for (int nibble = 7; nibble >= 0; nibble--) {
          if (target_idx < (int32_t)count) {
            sample_buffer[target_idx++] = (uint8_t)((word >> (nibble * 4)) & 0x0F);
          }
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
        while (avail >= 64 && sent < count) {
          uint32_t to_send = count - sent;
          if (to_send > avail) to_send = avail;
          uint32_t n = tud_cdc_write(&sample_buffer[sent], to_send);
          if (n == 0) break;
          sent += n;
          avail -= n;
          tx_start = UTIL_GetTick();
        }
        tud_cdc_write_flush();
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

  // Activity Stretch: ensure LED4 transmission flash is clearly visible to human eye
  UTIL_IdleMs(35);
  set_led(LED_TX_BIT, 0);
  set_led(LED_IDLE_BIT, 1); // PIN_19 ON
}

// Dedicated raw USB Full-Speed throughput benchmark function (Optimized Batching)
static void execute_usb_benchmark(uint32_t total_bytes) {
  static uint8_t test_chunk[512];
  for (int i = 0; i < 512; i++) test_chunk[i] = (uint8_t)(i & 0xFF);

  uint32_t sent = 0;
  uint32_t t_start = UTIL_GetTick();

  while (sent < total_bytes) {
    tud_task();
    if (tud_cdc_connected()) {
      uint32_t avail = tud_cdc_write_available();
      if (avail > 0) {
        uint32_t to_send = total_bytes - sent;
        if (to_send > avail) to_send = avail;
        if (to_send > sizeof(test_chunk)) to_send = sizeof(test_chunk);
        uint32_t n = tud_cdc_write(test_chunk, to_send);
        if (n > 0) {
          sent += n;
          tud_cdc_write_flush();
          t_start = UTIL_GetTick();
        }
      }
    }
    if (UTIL_GetTick() - t_start > 3000) break;
  }
  tud_task();
  tud_cdc_write_flush();
}
static void process_sump_byte(uint8_t b) {
  static uint8_t cmd_buf[5];
  static int cmd_state = 0;

  if (cmd_state == 0) {
    if (b == SUMP_RESET) {
      set_all_leds(0);
      set_led(LED_IDLE_BIT, 1);
      test_div_override = 0xFFFFFFFFu;  // restore auto square-wave gear mapping
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
    } else if (b == 0x0A) {
      execute_usb_benchmark(sample_limit ? sample_limit : 65536);
    } else if (b == 0x0B) { // 16 KB
      execute_usb_benchmark(16384);
    } else if (b == 0x0C) { // 32 KB
      execute_usb_benchmark(32768);
    } else if (b == 0x0D) { // 64 KB
      execute_usb_benchmark(65536);
    } else if (b == 0x0E) { // 128 KB
      execute_usb_benchmark(131072);
    } else if (b == 0x0F) { // 256 KB
      execute_usb_benchmark(262144);
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
      } else if (op == SUMP_TEST_DIV) {
        // Extension: manual square-wave divider (0xFFFFFFFF = auto gear table)
        uint32_t val32 = CMD_U32(cmd_buf);
        test_div_override = val32;
      } else if (op == GEN_OP_WAVE) {
        // Set waveform type / amplitude / output enable
        uint32_t p = CMD_U32(cmd_buf);
        gen_type = (uint8_t)(p & 0x03u);
        gen_amp  = (uint8_t)((p >> 8) & 0xFFu);
        if (gen_amp > 100) gen_amp = 100;
        gen_en   = (uint8_t)((p >> 16) & 0x01u);
        gen_compute();
        gen_apply();
      } else if (op == GEN_OP_FREQ) {
        uint32_t f = CMD_U32(cmd_buf);
        if (f < 1) f = 1;
        if (f > 100000000u) f = 100000000u;
        gen_freq = f;
        gen_compute();
        gen_apply();
      } else if (op == GEN_OP_P5_CFG) {
        uint32_t p = CMD_U32(cmd_buf);
        CPLD_REG_P5_CFG = p & 0x1FFu;
        p5_sq_sel = (uint8_t)((p >> 8) & 0x01u);
      } else if (op == GEN_OP_P5_DELAY) {
        CPLD_REG_P5_DELAY = CMD_U32(cmd_buf);
      } else if (op == GEN_OP_P5_WIDTH) {
        CPLD_REG_P5_WIDTH = CMD_U32(cmd_buf);
      } else if (op == GEN_OP_P5_CTRL) {
        CPLD_REG_P5_CTRL = CMD_U32(cmd_buf) & 0x07u;
      } else if (op == GEN_OP_SQ_FREQ) {
        sq_set_freq(CMD_U32(cmd_buf));
      } else if (op == GEN_OP_RATE_CAP) {
        uint32_t r = CMD_U32(cmd_buf);
        if (r < 1526u) r = 1526u;              // divider range limit
        if (r > 100000000u) r = 100000000u;
        gen_rate_cap = r;
        gen_compute();
        gen_apply();
      } else if (op == GEN_OP_GET_INFO) {
        gen_send_info();
      } else if (op == GEN_OP_P5_QUERY) {
        gen_send_p5_status();
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

// Configure weak pull-down on input pins (CH0~CH3: PIN_7..10 and PIN_1) to prevent floating crosstalk
static void config_pin_pulldowns(void) {
  PERIPHERAL_ENABLE(FCB, 0);
  SYS_ClkSourceTypeDef clk_src = SYS_GetClkSource();
  SYS_SetClkSource(SYS_CLK_SOURCE_HSI);

  FCB_IO_TypeDef local_io;
  FCB_ReadIOConfig(&local_io);

  FCB_PIN_TypeDef pin_cfg;
  const int pulldown_pins[] = {
    AGRV2KQ32_PIN_7_ID,   // CH0
    AGRV2KQ32_PIN_8_ID,   // CH1
    AGRV2KQ32_PIN_9_ID,   // CH2
    AGRV2KQ32_PIN_10_ID   // CH3
  };

  for (size_t i = 0; i < sizeof(pulldown_pins)/sizeof(pulldown_pins[0]); i++) {
    FCB_GetPinConfig(&local_io, pulldown_pins[i], &pin_cfg);
    FCB_PIN_SetPullMode(&pin_cfg, FCB_PIN_PULL_DOWN);
    FCB_SetPinConfig(&local_io, pulldown_pins[i], &pin_cfg);
  }

  FCB_WriteIOConfig(&local_io);
  SYS_SetClkSource(clk_src);
}

int main(void) {
  board_init();
  config_pin_pulldowns();
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

  // Waveform generator init: DMAC armed, DAC output OFF until the host enables it.
  // PIN_5 defaults to the square-wave source (keeps the self-test loopback alive).
  PERIPHERAL_ENABLE(DMAC, 0);
  DMAC_Init();
  gen_compute();
  DAC0_REG_CTRL     = 0;
  CPLD_REG_P5_CFG   = (1u << 8);   // SQ_SEL=1: square wave source
  CPLD_REG_P5_CTRL  = 0x04u;       // clear trigger engine state
  CPLD_REG_TEST_DIV = 999;         // 100 kHz default

  // Setup LEDs
  GPIO_SetOutput(LED_GPIO, ALL_LEDS);
  set_all_leds(0);

  // Startup LED Self-Test (Distinct visual confirmation for all 4 LEDs)
  const uint8_t leds[] = { LED1_BIT, LED2_BIT, LED3_BIT, LED4_BIT };
  for (int i = 0; i < 4; i++) {
    set_led(leds[i], 1);
    UTIL_IdleMs(180);
    set_led(leds[i], 0);
    UTIL_IdleMs(60);
  }
  for (int i = 0; i < 2; i++) {
    set_all_leds(1);
    UTIL_IdleMs(120);
    set_all_leds(0);
    UTIL_IdleMs(120);
  }
  set_led(LED_IDLE_BIT, 1); // LED1 (PIN_19) ON

  printf("\n=== AG32 Plan B Logic Analyzer (CPLD Sampler) Ready ===\n");
  printf("[GEN] PIN_11 DAC0 wave generator ready (output OFF), PIN_5 = 100kHz square\n");
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

    // Idle heartbeat: LED1 stays lit, soft rotating pulse every 1.5s
    if (UTIL_GetTick() - led_flow_timer > 1500) {
      led_flow_timer = UTIL_GetTick();
      uint8_t next_led = leds[1 + ((led_flow_idx++) % 3)]; // cycle LED2, LED3, LED4
      set_led(next_led, 1);
      UTIL_IdleMs(80);
      set_led(next_led, 0);
      set_led(LED_IDLE_BIT, 1);
    }
  }
  return 0;
}
