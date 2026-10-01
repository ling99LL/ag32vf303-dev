// Minimal MCU host app for the pure-CPLD LED demo. The MCU does nothing:
// the flowing light is generated entirely in the CPLD user logic.
#include "alta.h"
#include "board.h"

int main(void) {
  board_init();
  for (;;) {
    UTIL_IdleMs(1000);
  }
  return 0;
}
