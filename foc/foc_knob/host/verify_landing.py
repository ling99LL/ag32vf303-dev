# verify_landing.py - closed-loop rot must land ON the target (no overshoot).
# The hall decode is quantized to one sector (10 deg mech @ 6pp), so the
# acceptance bar is +/-6 deg on the final resting angle.
# Usage: python verify_landing.py [COM26]
import sys, time
import serial

PORT = sys.argv[1] if len(sys.argv) > 1 else "COM26"

ser = serial.Serial(PORT, 115200, timeout=0.05)
time.sleep(0.3)
ser.write(b"s\ntel 50\n")
time.sleep(0.3)
ser.reset_input_buffer()

def latest_ang(seconds=0.4):
    ser.reset_input_buffer()
    time.sleep(seconds)
    d = ser.read(8192).decode(errors="replace")
    angs = [float(l.split(",")[2]) / 100.0 for l in d.splitlines()
            if l.startswith("$T,") and l.count(",") == 10]
    return angs[-1] if angs else None

print("== scan calibration ==")
ser.write(b"scan\n")
t0, ok, buf = time.time(), False, b""
while time.time() - t0 < 25:
    d = ser.read(512)
    if not d:
        continue
    buf += d
    while b"\n" in buf:
        line, buf = buf.split(b"\n", 1)
        s = line.decode(errors="replace").strip()
        if s and not s.startswith("$T,"):
            print("  " + s)
            if "scan ok" in s:
                ok = True
if not ok:
    print("SCAN FAILED - aborting")
    sys.exit(1)

def rot_and_land(deg):
    start = latest_ang()
    if start is None:
        print("rot %+d: no telemetry" % deg)
        return False
    print("rot %+d from %.1f deg (target %.1f)" % (deg, start, start + deg))
    ser.reset_input_buffer()
    ser.write(b"rot %d\n" % deg)
    t0, done, buf = time.time(), False, b""
    while time.time() - t0 < 40 and not done:
        d = ser.read(512)
        if not d:
            continue
        buf += d
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            s = line.decode(errors="replace").strip()
            if s.startswith("$T,"):
                continue
            if s:
                print("  " + s)
            if "rot done" in s or "ABORT" in s or "timeout" in s:
                done = True
    time.sleep(1.5)                       # let it fully rest
    end = latest_ang()
    if end is None:
        print("  no telemetry after rot")
        return False
    err = end - (start + deg)
    print("  landed %.1f deg, error %+.1f deg -> %s"
          % (end, err, "PASS" if abs(err) <= 6.0 else "FAIL"))
    return abs(err) <= 6.0

r1 = rot_and_land(360)
time.sleep(0.5)
r2 = rot_and_land(-360)
ser.write(b"tel 0\n")
time.sleep(0.2)
ser.close()
print("\nLANDING %s" % ("PASS" if (r1 and r2) else "FAIL"))
sys.exit(0 if (r1 and r2) else 1)
