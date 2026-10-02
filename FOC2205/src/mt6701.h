// mt6701.h — MT6701QT-STD SSI angle reader (24-clock frame @12.5MHz)
//
// Frame (MSB first): [23:10] = D[13:0] angle, [9:6] = Mg[3:0] status, [5:0] = CRC6
//   Mg[2] = push pressed, Mg[1:0] = field strength (0 ok / 1 too strong / 2 too weak),
//   Mg[3] = overspeed.  CRC6: X^6+X+1 over the 18 bits D+Mg, MSB first, init 0.
// Data path: hard SPI1 clocks the frame (dummy TX); spi_mode_wrap captures DO on
// the falling edge of the mode-1 SCK and latches it at frame end; we read it from
// SPIW_RXDATA1. CSN is GPIO2_0, paced in software to meet the >=100ns setup.
#ifndef MT6701_H
#define MT6701_H

#include "app_io.h"

typedef struct
{
  uint16_t angle;   // 0..16383 raw
  uint8_t  mg;      // Mg[3:0] status nibble
  uint8_t  push;    // 1 = knob pressed
  uint8_t  field;   // Mg[1:0]
  uint8_t  overspeed;
  int      crc_ok;
} mt6701_sample_t;

void mt6701_init(void);
// One SSI frame read; returns 1 on CRC pass (sample filled), 0 on CRC fail.
int mt6701_read(mt6701_sample_t *s);
// CRC6 (X^6+X+1) over 18 bits, exposed for self-test
uint8_t mt6701_crc6(uint32_t data18);

#endif
