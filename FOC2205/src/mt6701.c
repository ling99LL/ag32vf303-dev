#include "mt6701.h"

// Last raw 24-bit frame, exposed for offline bit-alignment analysis.
uint32_t g_mt_last_raw;

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
  // 0x43 has bit6 set; that bit is shifted out on the next iteration but
  // survives in the final value, so mask back to 6 bits before comparing.
  // Without this the CRC never matches and every frame looks corrupt.
  return (uint8_t)(crc & 0x3Fu);
}

int mt6701_read(mt6701_sample_t *s)
{
  // CSN low -> >=100ns setup -> 24 clocks -> >=0.5*TCLK -> CSN high
  // The 1us (not 150ns) setup is deliberate: MT6701 leaves DO at Hi-Z until it
  // starts driving, and the 200k pull-up makes the first sampled bit read as 1,
  // shifting the whole frame right by one. Verified on hardware.
  // RXDATA reads clear the bridge's sticky DONE bit; discard any completion left
  // by a previous failed transfer before opening this frame.
  (void)SPIW_RXDATA1;
  mt_csn_low();
  delay_us(1);

  // Single-phase SPI_Send: sends exactly 3 bytes (24 clocks), avoiding 48-clock overflow
  if (!app_spi_send(SPI1, 3, 0x000000u)) {
    mt_csn_high();
    s->crc_ok = 0;
    return 0;
  }

  // Hard SPI DONE precedes the bridge's last pad edge by up to 120ns.
  // Allow that drain plus >=160ns (half of 3.125MHz TCLK) before releasing CSN.
  delay_ns(500);
  mt_csn_high();
  delay_ns(500);   // spi_mode_wrap latches RXDATA ~250ns after the hard SPI DONE

  uint32_t status = SPIW_STATUS;
  if (!(status & 2u) || (status & SPIW_ERROR1)) { s->crc_ok = 0; return 0; }
  uint32_t frame = SPIW_RXDATA1 & 0xFFFFFFu;
  g_mt_last_raw = frame;

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
