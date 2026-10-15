"""Capture the FOC2205 boot log from the UART0 console (DAPLink CDC).

Usage: python tools/uart_capture.py [COM] [BAUD] [SECONDS]
Start this BEFORE resetting the board so the banner is not missed.
"""
import sys, time, serial

port = sys.argv[1] if len(sys.argv) > 1 else 'COM26'
baud = int(sys.argv[2]) if len(sys.argv) > 2 else 115200
secs = float(sys.argv[3]) if len(sys.argv) > 3 else 15.0

s = serial.Serial(port, baud, timeout=1)
s.reset_input_buffer()
buf = b''
t0 = time.time()
while time.time() - t0 < secs:
    d = s.read(4096)
    if d:
        buf += d
s.close()
sys.stdout.write(buf.decode('utf-8', 'replace'))
