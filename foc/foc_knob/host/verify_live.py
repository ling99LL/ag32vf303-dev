# verify_live.py - confirm hall states keep streaming live in $T telemetry
# while the motor rotates (the "blocked serial during rotation" regression
# test). Open-loop is tested pre-calibration, closed-loop after a 'scan'.
# Usage: python verify_live.py [COM26]
import sys, time
import serial

PORT = sys.argv[1] if len(sys.argv) > 1 else "COM26"

ser = serial.Serial(PORT, 115200, timeout=0.05)
time.sleep(0.3)
ser.write(b"s\ntel 50\n")          # auto status off, telemetry 50 Hz
time.sleep(0.3)
ser.reset_input_buffer()

def grab(seconds):
    rows, buf = [], b""
    t0 = time.time()
    while time.time() - t0 < seconds:
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
                    rows.append((float(f[2]) / 100.0, int(f[6]), int(f[7])))
    return rows

def hall_path(rows):
    seq = []
    for _a, h, _f in rows:
        if not seq or seq[-1] != h:
            seq.append(h)
    return seq

def report(name, rows, need_sweep=None):
    seq = hall_path(rows)
    swept = abs(rows[-1][0] - rows[0][0]) if len(rows) > 1 else 0.0
    ok = len(rows) > 30 and len(seq) >= 5
    if need_sweep is not None:
        ok = ok and swept >= need_sweep
    print("%s: %d frames, %d hall switches, swept %.1f deg\n"
          "  hall path: %s\n  -> %s" %
          (name, len(rows), len(seq) - 1, swept,
           " ".join(map(str, seq[:24])), "PASS" if ok else "FAIL"))
    return ok

rows = grab(0.6)
calibrated = bool(rows) and (rows[-1][2] & 16) != 0   # FLAG_FOC_LIVE
print("board state: %s" % ("calibrated (FOC live)" if calibrated
                           else "not calibrated"))

if not calibrated:
    ser.write(b"rot 180\n")
    report("OPEN-LOOP rot 180 (telemetry must keep flowing)", grab(6.0))

    print("\n-- running scan calibration (~7s) --")
    ser.write(b"scan\n")
    deadline = time.time() + 25
    ok_scan = False
    buf = b""
    while time.time() < deadline:
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
                ok_scan = True
    rows = grab(0.6)
    calibrated = bool(rows) and (rows[-1][2] & 16) != 0
    print("scan %s" % ("ok, FOC live" if ok_scan and calibrated else "FAILED"))

if calibrated:
    ser.write(b"rot 360\n")
    report("CLOSED-LOOP rot 360", grab(14.0), need_sweep=340)

ser.write(b"tel 0\n")
time.sleep(0.2)
ser.close()
