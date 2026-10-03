// app_io.h — FOC2205 pin-level bring-up (named app_io to avoid shadowing the SDK board.h)
//
// Pin map (see foc2205.ve and docs/DRV8316+MT6701_FOC驱动板接线设计.md):
//   GPIO2_0 -> PIN_14  MT6701 CSN   (via logic pass-through spi1_csn_go)
//   GPIO2_1 -> PIN_5   DRV8316 nSLEEP (direct)
//   SPI0 -> mode-1 bridge -> DRV8316C   (SCK/MOSI/CSN via logic, MISO captured in logic)
//   SPI1 -> mode-1 bridge -> MT6701 SSI (SCK via logic; CSN = GPIO2_0; DO captured in logic)
#ifndef APP_IO_H
#define APP_IO_H

#include "alta.h"

// spi_mode_wrap APB register bank (see logic/spi_mode_wrap.v)
#define SPIW_BASE     (0x60007000u)
#define SPIW_RXDATA0  (*(volatile uint32_t *)(SPIW_BASE + 0x00)) // DRV8316 frame [15:0]
#define SPIW_RXDATA1  (*(volatile uint32_t *)(SPIW_BASE + 0x04)) // MT6701 frame [23:0]
#define SPIW_STATUS   (*(volatile uint32_t *)(SPIW_BASE + 0x08)) // bit0/1 frame-done sticky

// MT6701 CSN on GPIO2 bit 0
#define MT_CSN_GPIO   GPIO2
#define MT_CSN_BIT    GPIO_BIT0
// DRV8316 nSLEEP on GPIO2 bit 1 (external 10k pull-up keeps the DRV awake
// through MCU reset — its buck/AVDD die in sleep, so never gate the supply)
#define DRV_SLP_GPIO  GPIO2
#define DRV_SLP_BIT   GPIO_BIT1
// DRV8316 INLA/B/C common enable on GPIO2 bit 2 (P0-3 fix: the three INLx
// pins are tied together to PIN_28/JNTRST with a 10k pulldown — DAPLink's
// 2-wire Compact-JTAG never touches nTRST, so debugging is unaffected).
// LOW = PWM_MODE register change allowed and 3x mode reads Hi-Z; HIGH = 3x drive active.
#define DRV_INL_GPIO  GPIO2
#define DRV_INL_BIT   GPIO_BIT2

void app_io_init(void);            // GPIO + AF + SPI0/SPI1 clocks and dividers

static inline void mt_csn_low(void)  { GPIO_SetLow (MT_CSN_GPIO, MT_CSN_BIT); }
static inline void mt_csn_high(void) { GPIO_SetHigh(MT_CSN_GPIO, MT_CSN_BIT); }
static inline void drv_sleep(void)   { GPIO_SetLow (DRV_SLP_GPIO, DRV_SLP_BIT); }
static inline void drv_wake(void)    { GPIO_SetHigh(DRV_SLP_GPIO, DRV_SLP_BIT); }
static inline void drv_inl_low(void) { GPIO_SetLow (DRV_INL_GPIO, DRV_INL_BIT); }
static inline void drv_inl_high(void){ GPIO_SetHigh(DRV_INL_GPIO, DRV_INL_BIT); }

// Busy-wait helpers (rdcycle-based; SYSCLK = 200MHz -> 5 cycles/ns)
void delay_ns(uint32_t ns);
void delay_us(uint32_t us);
void delay_ms(uint32_t ms);

#endif
