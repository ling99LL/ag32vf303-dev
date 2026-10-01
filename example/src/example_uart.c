#include "example.h"

// Test UART DMA
void TestUart(void)
{
#ifdef LOGGER_UART
  // Wait for existing UART transmit to finish
  while (UART_IsTxBusy(MSG_UART));

  const char txbuf[] = "This quick brown fox jumps over the lazy dog!\n";
  const char rxbuf[256];

  SYS_EnableAHBClock(AHB_MASK_DMAC0);
  DMAC_Init();

  UART_Init(MSG_UART, BAUD_RATE, UART_LCR_DATABITS_8, UART_LCR_STOPBITS_1, UART_LCR_PARITY_NONE, UART_LCR_FIFO_16);
  UART_SetDmaMode(MSG_UART, UART_DMA_RX_TX);

  const volatile uint32_t dma_count = sizeof(txbuf) - 1; // Strip the ending '0'
  uint8_t tx_dma_req = UARTx_TX_DMA_REQ(LOGGER_UART);
  uint8_t rx_dma_req = UARTx_RX_DMA_REQ(LOGGER_UART);

  uint32_t tick0 = UTIL_McycleToUs(UTIL_GetMcycle());
  DMAC_Config(DMAC_CHANNEL0, (uint32_t)txbuf, (uint32_t)&MSG_UART->DR,
              DMAC_ADDR_INCR_ON, DMAC_ADDR_INCR_OFF,
              DMAC_WIDTH_8_BIT, DMAC_WIDTH_8_BIT,
              DMAC_BURST_1, DMAC_BURST_1,
              dma_count, DMAC_MEM_TO_PERIPHERAL_DMA_CTRL,
              0, tx_dma_req);

  DMAC_Config(DMAC_CHANNEL1, (uint32_t)&MSG_UART->DR, (uint32_t)rxbuf,
              DMAC_ADDR_INCR_OFF, DMAC_ADDR_INCR_ON,
              DMAC_WIDTH_8_BIT, DMAC_WIDTH_8_BIT,
              DMAC_BURST_1, DMAC_BURST_1,
              0, DMAC_PERIPHERAL_TO_MEM_PERIPHERAL_CTRL, rx_dma_req, 0);

  while (DMAC_IsEnabledChannel(DMAC_CHANNEL0));
  uint32_t tick1 = UTIL_McycleToUs(UTIL_GetMcycle());
  printf("UART TX DMA of %d bytes finished after %d us.\n", dma_count, tick1 - tick0);
#endif
}
