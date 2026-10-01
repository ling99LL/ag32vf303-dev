# record_turn.py - record high-rate telemetry while the user turns the knob.
# Switches to m3 with default detent params first, then streams $T to CSV.
# Usage: python record_turn.py [seconds] [COM]
import sys, time
import serial

SECS = float(sys.argv[1]) if len(sys.argv) > 1 else 150.0
PORT = sys.argv[2] if len(sys.argv) > 2 else "COM26"
OUT = "turn_capture.csv"

ser = serial.Serial(PORT, 115200, timeout=0.02)
time.sleep(0.3)

def cmd(c, wait=0.15):
    ser.write((c + "\n").encode())
    time.sleep(wait)

for c in ("vl 3", "ds 5", "dw 30", "es 4", "sp 0.6", "sb 0",
          "pn 0", "px -1", "tel 200", "m3"):
    cmd(c)
cmd("st", 0.3)
time.sleep(0.5)
ser.reset_input_buffer()

t0 = time.time()
n = 0
with open(OUT, "w") as f:
    f.write("t,ang_deg,vel_rad_s,uq_V\n")
    while time.time() - t0 < SECS:
        d = ser.read(65536)
        if not d:
            continue
        for l in d.decode(errors="replace").splitlines():
            if l.startswith("$T,") and l.count(",") == 10:
                fl = l.split(",")
                f.write("%.3f,%.2f,%.3f,%.3f\n" % (
                    time.time() - t0,
                    float(fl[2]) / 100.0,
                    float(fl[3]) / 1000.0,
                    float(fl[4]) / 1000.0))
                n += 1
                if n % 2000 == 0:
                    f.flush()
print("captured %d rows in %.1fs -> %s" % (n, time.time() - t0, OUT))
ser.close()
