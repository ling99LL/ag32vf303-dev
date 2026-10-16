"""Probe whether the DAPLink CDC's DTR/RTS lines are wired to the target's
NRST / BOOT1 pins.

If DTR (or RTS) pulls the board's reset line, we can reset the board from
software -- which is exactly what we need to catch the boot window where
PIN_28 (INL_ALL) is not yet driven high and SWD still works.

Usage: python dtr_probe.py <port> <baud>
"""
import sys
import time
import serial

port = sys.argv[1] if len(sys.argv) > 1 else "COM26"
baud = int(sys.argv[2]) if len(sys.argv) > 2 else 115200

s = serial.Serial(port, baud, timeout=0.3)
print("opened %s @ %d" % (port, baud))

# let a couple of idle status frames come in first
for _ in range(6):
    print("IDLE: " + s.readline().decode("utf-8", "replace").rstrip())

print("--- pulling DTR low (1.0 s) ---")
s.dtr = False
time.sleep(1.0)
print("--- releasing DTR ---")
s.dtr = True

t0 = time.time()
banner = 0
while time.time() - t0 < 9.0:
    line = s.readline().decode("utf-8", "replace").rstrip()
    if not line:
        continue
    print("POST: " + line)
    if ("SYSCLK" in line or "BootMode" in line or "INLx" in line
            or "Stage" in line or "banner" in line):
        banner += 1

print("--- now trying RTS low (1.0 s) ---")
s.rts = False
time.sleep(1.0)
s.rts = True

t0 = time.time()
while time.time() - t0 < 9.0:
    line = s.readline().decode("utf-8", "replace").rstrip()
    if not line:
        continue
    print("POST2: " + line)
    if ("SYSCLK" in line or "BootMode" in line or "INLx" in line
            or "Stage" in line):
        banner += 1

s.close()
print("boot-banner lines seen: %d" % banner)
print("RESULT: %s" % ("DTR/RTS CAN reset the board"
                      if banner else "DTR/RTS are NOT wired to reset"))
