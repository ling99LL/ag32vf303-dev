# wall_hold_probe.py - m4 bounded-wall PARKED-at-the-boundary census.
# The snap-in tests (all_mode_probe) never hold the rotor AT the wall; a
# user pressing against the bound parks the rotor on a hall boundary where
# decode flicker can excite the wall P (the mechanism that shook the
# spring). Land 1..9 deg past the bound at several raw phases, then watch
# 3s of 200Hz $T for standing-torque oscillation.
# Usage: python wall_hold_probe.py [COM26]
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

cmd("tel 200", 0.3)
print("== scan ==")
ser.reset_input_buffer()
cmd("scan", 0)
if wait_msg("scan ok", 30) is None:
    print("SCAN FAILED"); sys.exit(1)
cmd("m4", 0.2)
cmd("br 45", 0.2)

print(" depth  p2p    max|uq|  tailUq  tailVel  tailP2P  verdict")
for delta in (46, 48, 50, 52, 54, 56):
    cmd("m0", 0.2)
    cmd("z", 0.3)                    # re-zero: fresh raw phase each landing
    cmd("rot %d" % delta, 0)
    if wait_msg("rot done", 20) is None:
        print("  rot timeout"); continue
    time.sleep(0.35)
    cmd("m4", 0.2)
    rows = capture(3.0)
    if len(rows) < 100:
        print("  no data"); continue
    angs = [r[0] for r in rows]; vels = [r[1] for r in rows]
    uqs = [r[2] for r in rows]
    tail = rows[-400:]               # last 2s
    tp2p = max(r[0] for r in tail) - min(r[0] for r in tail)
    tuq = max(abs(r[2]) for r in tail)
    tvel = max(abs(r[1]) for r in tail)
    mx = max(abs(u) for u in uqs)
    p2p = max(angs) - min(angs)
    ok = "OK" if (tuq <= 1.95 and tp2p < 2.0 and tvel < 0.5) else "SHAKY"
    print("  +%2d  %6.2f  %7.2f  %6.2f  %7.2f  %7.2f  %s"
          % (delta - 45, p2p, mx, tuq, tvel, tp2p, ok))

cmd("m0", 0.2)
cmd("tel 0", 0.2)
ser.close()
print("done")
