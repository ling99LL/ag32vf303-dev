#ifndef CONSOLE_H
#define CONSOLE_H
#include <stdint.h>
void console_init(uint32_t hz);
void console_feed(int ch);
void console_poll(uint32_t now_ms);
void console_telemetry_poll(uint32_t now_ms);
int console_telemetry_active(void);
int console_autorun_cancelled(void);
#endif
