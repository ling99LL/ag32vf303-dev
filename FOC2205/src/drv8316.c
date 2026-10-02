#include "drv8316.h"

static uint16_t make_frame(int read, uint8_t addr, uint8_t data)
{
  uint16_t w = (uint16_t)(((read ? 1u : 0u) << 15) | (((uint16_t)(addr & 0x3Fu)) << 9) | data);
  // Even parity over the 15 non-parity bits (B15:9 and B7:0) -> B8
  uint16_t p = (uint16_t)((w >> 9) ^ (w & 0xFFu));   // fold into <=15 bits
  p ^= (uint16_t)(p >> 4);
  p ^= (uint16_t)(p >> 2);
  p ^= (uint16_t)(p >> 1);
  w |= (uint16_t)((p & 1u) << 8);
  return w;
}

drv_resp_t drv8316_xfer(int read, uint8_t addr, uint8_t data)
{
  drv_resp_t r;
  uint16_t w = make_frame(read, addr, data);

  SPI_SendAndReceive(SPI0, 2, w, 2); // exactly 2 bytes = 16 clocks
  delay_ns(500);                     // spi_mode_wrap latch trails hard-SPI DONE

  uint16_t resp = (uint16_t)(SPIW_RXDATA0 & 0xFFFFu);
  r.stat = (uint8_t)(resp >> 8);
  r.data = (uint8_t)(resp & 0xFFu);
  return r;
}

drv_resp_t drv8316_read_reg(uint8_t addr)  { return drv8316_xfer(1, addr, 0); }
drv_resp_t drv8316_write_reg(uint8_t addr, uint8_t data) { return drv8316_xfer(0, addr, data); }

void drv8316_clear_faults(void)
{
  drv8316_write_reg(DRV_REG_CTRL2, DRV_VAL_CTRL2 | 0x01); // CLR_FLT = W1C, self-clears
}

void drv8316_sleep_pulse_reset(void)
{
  drv_sleep();
  delay_us(30);   // tRST window is 20-40us
  drv_wake();
  delay_ms(2);    // tWAKE
}

void drv8316_init(void)
{
  drv_wake();
  delay_ms(50);   // TPwrUp (internal rails) + tREADY (1ms SPI ready) with margin

  drv8316_write_reg(DRV_REG_CTRL1, DRV_VAL_CTRL1_UNLOCK);
  drv8316_write_reg(DRV_REG_CTRL6, DRV_VAL_CTRL6);   // BUCK_PS_DIS first!
  drv8316_write_reg(DRV_REG_CTRL2, DRV_VAL_CTRL2);   // 3x mode + slew + push-pull SDO
  drv8316_write_reg(DRV_REG_CTRL5, DRV_VAL_CTRL5);   // CSA gain 0.6 V/A
  drv8316_write_reg(DRV_REG_CTRL10, DRV_VAL_CTRL10); // delay compensation
  drv8316_clear_faults();
}
