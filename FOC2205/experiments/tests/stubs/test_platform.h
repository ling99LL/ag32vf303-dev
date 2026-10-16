#ifndef TEST_PLATFORM_H
#define TEST_PLATFORM_H
#include <stdint.h>
#define APP_IO_H
#define ANALOG_IP
#define UART0 0
#define GPTIMER0_IRQn 0
#define SPI1 1
extern uint32_t test_rxdata, test_spi_status;
#define SPIW_RXDATA1 test_rxdata
#define SPIW_STATUS test_spi_status
#define SPIW_ERROR0 (1u << 8)
#define SPIW_ERROR1 (1u << 9)
void delay_ms(uint32_t n);
void delay_us(uint32_t n);
void delay_ns(uint32_t n);
void mt_csn_high(void);
void mt_csn_low(void);
void drv_inl_high(void);
void drv_inl_low(void);
int app_spi_send(int spi, int bytes, uint32_t data);
void INT_DisableIRQ(int irq);
void INT_EnableIRQ(int irq, int priority);
int UART_IsRxFifoEmpty(int uart);
int UART_ReceiveData(int uart);
typedef struct { volatile uint32_t SR, CR1; } GPTIMER_TypeDef;
extern GPTIMER_TypeDef gptimer0_stub;
#define GPTIMER0 (&gptimer0_stub)
typedef struct { uint32_t v; } GPIO_TypeDef;
extern GPIO_TypeDef gpio2_stub, gpio4_stub;
#define GPIO2 (&gpio2_stub)
#define GPIO4 (&gpio4_stub)
#define GPIO_BIT0 (1u << 0)
#define GPIO_BIT2 (1u << 2)
#define DRV_INL_BIT GPIO_BIT2
uint32_t GPIO_GetValue(GPIO_TypeDef *port, uint32_t mask);
#endif
