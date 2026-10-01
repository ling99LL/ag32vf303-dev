// AG32 (100-pin AGM demo board) 4-LED flowing light firmware.
//
// LEDs are on GPIO4_1..GPIO4_4 (die pads PIN_34/33/32/31), active high,
// per the AGM official example_board.ve.

#include "alta.h"
#include "board.h"
#include <stdio.h>

// On-board LEDs are ACTIVE-LOW (wired to VCC)
#define LED_BITS (GPIO_BIT1 | GPIO_BIT2 | GPIO_BIT3 | GPIO_BIT4)
#define N_LEDS 4
#define FLOW_STEP_MS 200

static void led_write(int i, int on) {
  GPIO_SetValue(LED_GPIO, (uint8_t)(1u << (i + 1)), on ? 0x00 : 0xff);
}

int main(void) {
  board_init();

  SYS_EnableAPBClock(LED_GPIO_MASK);
  GPIO_SetOutput(LED_GPIO, LED_BITS);
  GPIO_SetLow(LED_GPIO, LED_BITS);

  printf("AG32 flowing LED started (%d LEDs on GPIO4_1..4)\n", N_LEDS);

  uint32_t next = board_millis();
  unsigned active = 0;
  while (1) {
    led_write((int)active, 1);
    next = board_millis() + FLOW_STEP_MS;
    while ((int32_t)(board_millis() - next) < 0) {
    }
    led_write((int)active, 0);
    active = (active + 1) % N_LEDS;
  }
  return 0;
}
