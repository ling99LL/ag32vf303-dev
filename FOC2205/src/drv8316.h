// drv8316.h — DRV8316CRRGFR SPI driver (16-clock frames @6.25MHz)
//
// SDI frame (MSB first): B15=W (0=write, 1=read), B14:9=A[5:0], B8=even parity
// over the other 15 bits, B7:0=D[7:0].  SDO: [15:8]=STAT, [7:0]=read data.
// Exactly 16 clocks per frame or the device raises SPI_SCLK_FLT.
// Data path: hard SPI0 clocks the frame; spi_mode_wrap captures SDO and latches
// it at frame end into SPIW_RXDATA0 (full 16 bits, no bit loss).
#ifndef DRV8316_H
#define DRV8316_H

#include "app_io.h"

// Register addresses
#define DRV_REG_IC_STAT  0x0
#define DRV_REG_STAT1    0x1
#define DRV_REG_STAT2    0x2
#define DRV_REG_CTRL1    0x3
#define DRV_REG_CTRL2    0x4
#define DRV_REG_CTRL3    0x5
#define DRV_REG_CTRL4    0x6
#define DRV_REG_CTRL5    0x7
#define DRV_REG_CTRL6    0x8
#define DRV_REG_CTRL10   0xC

// Init values (see docs §6; do not change without re-reading the datasheet)
#define DRV_VAL_CTRL1_UNLOCK  0x03  // REG_LOCK = 011b
#define DRV_VAL_CTRL6         0x10  // BUCK_PS_DIS=1 (mandatory) + BUCK_SEL=00b (3.3V)
#define DRV_VAL_CTRL2         0x7C  // res=01, SDO push-pull, SLEW=200V/us, PWM_MODE=3x
#define DRV_VAL_CTRL5         0x02  // CSA_GAIN = 0.6 V/A
#define DRV_VAL_CTRL10        0x15  // DLYCMP_EN + DLY_TARGET=1.2us (for 200V/us)

typedef struct
{
  uint8_t stat;   // response STAT byte
  uint8_t data;   // response data byte (readback)
} drv_resp_t;

void drv8316_init(void);
// One 16-clock frame; returns the {STAT, DATA} response.
drv_resp_t drv8316_xfer(int read, uint8_t addr, uint8_t data);
drv_resp_t drv8316_read_reg(uint8_t addr);
drv_resp_t drv8316_write_reg(uint8_t addr, uint8_t data);
// Clear latched faults (CTRL2.CLR_FLT)
void drv8316_clear_faults(void);
// 20-40us nSLEEP low pulse: resets faults without entering sleep (then re-wake)
void drv8316_sleep_pulse_reset(void);

#endif
