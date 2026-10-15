"""Send a command to the FOC2205 console and capture what it prints back.

Usage: python tools/uart_console.py <CMD> [SECONDS] [COM] [BAUD]

CMD is a string of console keys (e.g. "t", "r", "s"). "" means "just listen".
Example: python tools/uart_console.py t 5        # hold +torque 3 s, watch 5 s
         python tools/uart_console.py "" 20      # passive capture
"""
import sys, time, serial

cmd = sys.argv[1] if len(sys.argv) > 1 else ''
secs = float(sys.argv[2]) if len(sys.argv) > 2 else 6.0
port = sys.argv[3] if len(sys.argv) > 3 else 'COM26'
baud = int(sys.argv[4]) if len(sys.argv) > 4 else 115200

s = serial.Serial(port, baud, timeout=1)
s.reset_input_buffer()
if cmd:
    time.sleep(0.2)
    s.write(cmd.encode())

buf = b''
t0 = time.time()
while time.time() - t0 < secs:
    d = s.read(4096)
    if d:
        buf += d
s.close()
sys.stdout.write(buf.decode('utf-8', 'replace'))
