#include "app_io.h"
#include "util.h"

// Busy-wait helpers.
// NOTE: do NOT use read_csr(cycle) here. The AG32 core (misa 0x40801125, no U
// extension) does not implement the user-level cycle CSR - reading it traps as
// an illegal instruction (mcause 2, mtval 0xc00026f3), which on this board
// killed the firmware right after the first SPI transfer. Use the SDK's
// mcycle-based helper instead (mcycle/mcycleh are implemented).
// SYSCLK for the busy-wait math. Pinned to the "SYSCLK 200" line in foc2205.ve
// rather than read back at run time, so the delay maths cannot silently change
// if the clock tree is ever reconfigured. Verified on board: the bring-up
// banner prints SYSCLK=200000000, and SYS_GetSysClkFreq() (which returns the
// frequency of the *currently selected* source - SYS_Clocks.PLL_FREQUENCY once
// board_init() has switched to the PLL) agrees with this constant.
#define FOC_SYSCLK_HZ 200000000u

void delay_ns(uint32_t ns)
{
  uint32_t cycles = (FOC_SYSCLK_HZ / 1000000u) * ns / 1000u;
  if (cycles == 0) cycles = 1;
  UTIL_IdleCycle(cycles);
}

void delay_us(uint32_t us)
{
  UTIL_IdleUs(us);
}

void delay_ms(uint32_t ms)
{
  UTIL_IdleMs(ms);
}

void app_io_init(void)
{
  // P0-4: PIN_28 is the JNTRST pad. After reset SYS->SWJ_CNTL reads back 0x00000000,
  // i.e. every SWJ pad is still owned by the debug port - so GPIO2_2's output is
  // overridden and INL_ALL stays low no matter what the GPIO registers say
  // (measured: DIR=1, AFSEL=0, DATA=1, yet the pad reads 0 V against the board's
  // 10k pulldown). Release NJTRST before touching GPIO2. Only bit4 is set: JTCK/
  // JTMS (PIN_25/24) must keep working - that is the 2-wire debug link itself, and
  // openocd talks SWD over exactly those two pads. JTDI/JTDO (PIN_26/27) are unused
  // but left alone to keep the change minimal. TAP reset without nTRST is fine:
  // five TMS-high clocks do it, and SWD never asserts nTRST anyway.
  SYS_DisableNJTRST();

  // GPIO2 bank: CSN + nSLEEP + INL_EN outputs
  PERIPHERAL_GPIO_ENABLE(GPIO2);
  GPIO_SetSoftwareMode(MT_CSN_GPIO, MT_CSN_BIT | DRV_SLP_BIT | DRV_INL_BIT); // plain GPIO, not AF
  GPIO_SetOutput(MT_CSN_GPIO, MT_CSN_BIT | DRV_SLP_BIT | DRV_INL_BIT);
  mt_csn_high();   // deselect MT6701 (internally pulled up too)

  // P1-2: never gate nSLEEP at boot — the DRV's buck/AVDD die in sleep, and a
  // supply chain hanging off them would reset-loop. Hardware 10k pull-up keeps
  // the DRV awake even while the MCU is in reset.
  drv_wake();
  // P0-3: INLx must be LOW when writing CTRL2.PWM_MODE (datasheet Table 8-2
  // note). Kept low here; main() raises it after drv8316_init().
  drv_inl_low();

  // SPI0 (DRV8316) and SPI1 (MT6701): enable clocks and route function
  // signals into the logic fabric (the .ve sends them through spi_mode_wrap).
  PERIPHERAL_SPI_ENABLE(SPI0);
  PERIPHERAL_SPI_ENABLE(SPI1);
  SPI_Init(SPI0, SPI_CTRL_SCLK_DIV32); // 100MHz / 32 = 3.125MHz (DRV8316C: 5MHz max)
  SPI_Init(SPI1, SPI_CTRL_SCLK_DIV32); // 100MHz / 32 = 3.125MHz (MT6701 allows up to ~15.6MHz;
                                       // slowed down for bring-up timing margin)

  // GPTIMER0: CH0/1/2 PWM outputs + BRK input (nFAULT)
  SYS_EnableAPBClock(APB_MASK_GPTIMER0);
  GPIO_AF_ENABLE(GPTIMER0_CH0);
  GPIO_AF_ENABLE(GPTIMER0_CH1);
  GPIO_AF_ENABLE(GPTIMER0_CH2);
  GPIO_AF_ENABLE(GPTIMER0_BRK);
}
