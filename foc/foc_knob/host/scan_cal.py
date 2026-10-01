# Run the 'scan' open-loop calibration on the knob, then verify with a
# closed-loop rot 360. Usage: python scan_cal.py [COM26]
import sys, time, math
import serial

PORT = sys.argv[1] if len(sys.argv) > 1 else "COM26"

ser = serial.Serial(PORT, 115200, timeout=0.05)
time.sleep(0.3)
ser.write(b"tel 0\ns\n")          # telemetry + auto status off during scan
time.sleep(0.3)
ser.reset_input_buffer()

print("== scan cal: open-loop drag 1 rev, keep hands OFF ==")
ser.write(b"scan\n")
t0 = time.time()
buf = b""
ok = False
done = False
while time.time() - t0 < 30 and not done:
    d = ser.read(512)
    if not d:
        continue
    buf += d
    while b"\n" in buf:
        line, buf = buf.split(b"\n", 1)
        s = line.decode(errors="replace").strip()
        if not s or s.startswith("$T,"):
            continue    # firmware pumps $T during the drag now; keep log clean
        print("  " + s)
        if "scan ok" in s:
            done, ok = True, True
        elif "scan FAILED" in s:
            done = True
if not ok:
    print("\nSCAN NOT OK - not attempting closed loop.")
    sys.exit(1)

print("\n== verify: closed-loop rot 360 @ 50 deg/s ==")
ser.write(b"tel 50\n")
time.sleep(0.3)
ser.reset_input_buffer()
ser.write(b"rot 360\n")
t0 = time.time()
ang0 = None
rel_max = -1e9
uq_max = 0.0
last_print = -999
while time.time() - t0 < 20:
    d = ser.read(512)
    if not d:
        continue
    buf += d
    while b"\n" in buf:
        line, buf = buf.split(b"\n", 1)
        s = line.decode(errors="replace").strip()
        if s.startswith("$T,"):
            f = s.split(",")
            if len(f) >= 9:
                a = int(f[2]) / 5729.57795          # cdeg -> rad
                uq = int(f[4]) / 1000.0
                if ang0 is None:
                    ang0 = a
                rel = math.degrees(a - ang0)
                rel_max = max(rel_max, rel)
                uq_max = max(uq_max, abs(uq))
                if rel - last_print >= 45:
                    print("   %+7.1f deg  uq=%+.2fV" % (rel, uq))
                    last_print = rel
        elif "rot" in s and "$T" not in s:
            print("  " + s)

ser.write(b"tel 0\n")
time.sleep(0.2)
ser.close()
print("\nRESULT: swept %+.1f deg, max|uq|=%.2fV -> %s"
      % (rel_max, uq_max, "PASS" if rel_max > 340 else "INCOMPLETE"))
