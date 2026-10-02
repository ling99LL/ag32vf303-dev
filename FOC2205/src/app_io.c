#include "app_io.h"

void delay_ns(uint32_t ns)
{
  // cycles = ns * SYSCLK_MHz / 1000; at 200MHz that is 5 cycles per 2.5ns...
  // compute in 64-bit-free form: cycles = ns * (SYSCLK/1e6) / 1000
  uint32_t cycles = (SYS_GetSysClkFreq() / 1000000u) * ns / 1000u;
  if (cycles == 0) cycles = 1;
  uint32_t start = read_csr(cycle);
  while ((uint32_t)(read_csr(cycle) - start) < cycles) { }
}

void delay_us(uint32_t us)
{
  while (us--) {
    delay_ns(1000);
  }
}

void delay_ms(uint32_t ms)
{
  while (ms--) {
    UTIL_IdleUs(1000);
  }
}

void app_io_init(void)
{
  // GPIO2 bank: CSN + nSLEEP outputs
  PERIPHERAL_GPIO_ENABLE(GPIO2);
  GPIO_SetSoftwareMode(MT_CSN_GPIO, MT_CSN_BIT | DRV_SLP_BIT); // plain GPIO, not AF
  GPIO_SetOutput(MT_CSN_GPIO, MT_CSN_BIT | DRV_SLP_BIT);
  mt_csn_high();   // deselect MT6701 (internally pulled up too)
  drv_sleep();     // hold DRV8316 in sleep until drv8316_init()

  // SPI0 (DRV8316) and SPI1 (MT6701): enable clocks and route function
  // signals into the logic fabric (the .ve sends them through spi_mode_wrap).
  PERIPHERAL_SPI_ENABLE(SPI0);
  PERIPHERAL_SPI_ENABLE(SPI1);
  SPI_Init(SPI0, SPI_CTRL_SCLK_DIV16); // 100MHz / 16 = 6.25MHz  (DRV8316 max 10MHz)
  SPI_Init(SPI1, SPI_CTRL_SCLK_DIV8);  // 100MHz / 8  = 12.5MHz  (MT6701 max 15.6MHz)

  // GPTIMER0: CH0/1/2 PWM outputs + BRK input (nFAULT)
  SYS_EnableAPBClock(APB_MASK_GPTIMER0);
  GPIO_AF_ENABLE(GPTIMER0_CH0);
  GPIO_AF_ENABLE(GPTIMER0_CH1);
  GPIO_AF_ENABLE(GPTIMER0_CH2);
  GPIO_AF_ENABLE(GPTIMER0_BRK);
}
