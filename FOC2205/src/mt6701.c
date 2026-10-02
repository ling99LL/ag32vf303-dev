#include "mt6701.h"

void mt6701_init(void)
{
  mt_csn_high();
  delay_us(1);
}

// Bitwise CRC-6 (poly X^6+X+1 = 0x43), MSB first, init 0, no final XOR.
// Equivalent to the reference table implementation used by SmartKnob.
uint8_t mt6701_crc6(uint32_t data18)
{
  uint8_t crc = 0;
  for (int i = 17; i >= 0; --i) {
    uint8_t din = (data18 >> i) & 1u;
    uint8_t fb  = ((crc >> 5) & 1u) ^ din;
    crc = (uint8_t)((crc << 1) & 0x3Fu);
    if (fb) {
      crc ^= 0x43u;
    }
  }
  return crc;
}

int mt6701_read(mt6701_sample_t *s)
{
  // CSN low -> >=100ns setup -> 24 clocks -> >=0.5*TCLK -> CSN high
  mt_csn_low();
  delay_ns(150);

  // Single-phase SPI_Send: sends exactly 3 bytes (24 clocks), avoiding 48-clock overflow
  SPI_Send(SPI1, 3, 0x000000u);

  delay_ns(150);   // last CLK low to CSN high (>= 40ns required)
  mt_csn_high();
  delay_ns(500);   // spi_mode_wrap latches RXDATA ~250ns after the hard SPI DONE

  uint32_t frame = SPIW_RXDATA1 & 0xFFFFFFu;

  s->angle = (uint16_t)(frame >> 10);
  s->mg    = (uint8_t)((frame >> 6) & 0x0Fu);
  s->push  = (uint8_t)((s->mg >> 2) & 1u);
  s->field = (uint8_t)(s->mg & 0x03u);
  s->overspeed = (uint8_t)((s->mg >> 3) & 1u);

  uint8_t rx_crc = (uint8_t)(frame & 0x3Fu);
  uint8_t calc   = mt6701_crc6(frame >> 6);
  s->crc_ok = (rx_crc == calc);
  return s->crc_ok;
}
