# shake_probe.py - quantify m3 detent REST torque vs decode-grid phase.
# Lands the rotor +10deg at a time (6 landings = one full 10deg hall-decode
# period), then records 2.5s of high-rate $T at each rest. A detent that
# only fights when the decode reports 2+ sectors off (healthy) shows
# |uq| <= ~1.9V at EVERY landing; a landing where |uq| pegs at the voltage
# limit (3V) and the angle creeps/hops = the "一直抖" mechanism.
# Usage: python shake_probe.py [COM26]
import sys, time
import serial

PORT = sys.argv[1] if len(sys.argv) > 1 else "COM26"
ROW = lambda l: l.startswith("$T,") and l.count(",") == 10

ser = serial.Serial(PORT, 115200, timeout=0.02)
time.sleep(0.3)

def cmd(c, wait=0.15):
    ser.write((c + "\n").encode())
    time.sleep(wait)

def wait_msg(substr, timeout):
    buf = b""
    t0 = time.time()
    while time.time() - t0 < timeout:
        d = ser.read(512)
        if not d:
            continue
        buf += d
        for line in buf.split(b"\n"):
            s = line.decode(errors="replace").strip()
            if s and not s.startswith("$T,") and substr in s:
                return s
        # keep tail that might be a partial line
        if b"\n" in buf:
            buf = buf.split(b"\n")[-1]
    return None

def capture(seconds):
    rows = []
    t0 = time.time()
    ser.reset_input_buffer()
    while time.time() - t0 < seconds:
        d = ser.read(65536)
        if not d:
            continue
        for l in d.decode(errors="replace").splitlines():
            if ROW(l):
                f = l.split(",")
                rows.append((float(f[2]) / 100.0, float(f[3]) / 1000.0,
                             float(f[4]) / 1000.0))
    return rows

print("== scan calibration ==")
cmd("tel 200", 0.3)
ser.reset_input_buffer()
cmd("scan", 0)
if wait_msg("scan ok", 25) is None:
    print("SCAN FAILED")
    sys.exit(1)

cmd("m3")
for c in ("dw 30", "ds 2.5", "es 4", "sp 0.6", "sb 0", "pn 0", "px -1"):
    cmd(c)
time.sleep(0.5)
ser.reset_input_buffer()

print("\n land  parked%%  max|uq|@parked  p2p(ang)deg  verdict")
worst = 0.0
for step in range(6):
    cmd("rot 10", 0)
    if wait_msg("rot done", 10) is None:
        print("  rot timeout")
        break
    time.sleep(0.4)                       # let landing hold release
    rows = capture(2.5)
    if not rows:
        print("  no telemetry")
        break
    # parked windows: |vel| < 0.1 rad/s held for >= 0.4s (200Hz rows)
    PARK_V, PARK_N = 0.1, 80
    run = []
    best = None                     # (len, [uq...]) of longest parked run
    for r in rows:
        if abs(r[1]) < PARK_V:
            run.append(r)
        else:
            if best is None or len(run) > len(best):
                best = run
            run = []
    if best is None or len(run) > len(best):
        best = run
    parked_pct = 100.0 * len(best) / len(rows)
    if best and len(best) >= PARK_N:
        mx = max(abs(r[2]) for r in best)
    else:
        mx = float("nan")           # never truly parked
    angs = [r[0] for r in rows]
    p2p = max(angs) - min(angs)
    ok = ("QUIET" if mx <= 1.95 else "SHAKY") if mx == mx else "hand-on"
    if mx == mx:
        worst = max(worst, mx)
    print("  +%3d   %5.1f   %8s       %6.2f      %s"
          % ((step + 1) * 10, parked_pct,
             ("%5.2f" % mx) if mx == mx else "  n/a", p2p, ok))

cmd("m0")
cmd("tel 0", 0.2)
ser.close()
print("\nWORST rest |uq| = %.2f V -> %s"
      % (worst, "detents hold below breakaway everywhere"
         if worst <= 1.95 else "standing torque above breakaway = shake source"))
