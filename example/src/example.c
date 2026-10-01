#include "example.h"

void Button_isr(void)
{
  if (button_isr_cb) {
    button_isr_cb();
  }
  UTIL_IdleMs(400); // to debounce
  GPIO_ClearInt(BUT_GPIO, BUT_GPIO_BITS);
}

void MTIMER_isr(void)
{
  GPIO_Toggle(EXT_GPIO, EXT_GPIO_BITS);
  INT_SetMtime(0);
}

void TestMtimer(int ms)
{
  clint_isr[IRQ_M_TIMER] = MTIMER_isr;
  INT_SetMtime(0);
  INT_SetMtimeCmp(SYS_GetSysClkFreq() / 1000 * ms);
  INT_EnableIntTimer();
  while (1);
}


void testSPI();
int main(void)
{
  // This will init clock and uart on the board
  board_init();
  
  // The default isr table is plic_isr. The default entries in the table are peripheral name based like CAN0_isr() or
  // GPIO0_isr(), and can be re-assigned.
  plic_isr[BUT_GPIO_IRQ] = Button_isr;
  // Any interrupt priority needs to be greater than MIN_IRQ_PRIORITY to be effective
  INT_SetIRQThreshold(MIN_IRQ_PRIORITY);
  // Enable interrupt from BUT_GPIO
  INT_EnableIRQ(BUT_GPIO_IRQ, PLIC_MAX_PRIORITY);

  // TestMtimer(500);
  TestAnalog();
  // TestCan();
  // TestCrc();
  // TestFcb();
  // TestGpTimer();
  // TestGpTimerPwm();
  // TestI2c();
  // TestRTC();
  // TestSpi();
  // TestSystem();
  // TestTimer();
  // TestWdog();
  // TestUart();
  // TestFlash();


  GPIO_AF_ENABLE(UART1_UARTRXD);
  GPIO_AF_ENABLE(UART1_UARTTXD);

  SYS_EnableAPBClock(APB_MASK_UART1);
  UART_Init(UART1, 115200, UART_LCR_DATABITS_8, UART_LCR_STOPBITS_1, UART_LCR_PARITY_NONE, UART_LCR_FIFO_16);
  UART_Send(UART1,"rxbuf\r\n",7);
  while (1) 
  {
    UTIL_IdleUs(1000e3);
    UART_Send(UART1 ,"rxbuf\r\n",7);
  }


  //testSPI();

  TestGpio();
}
