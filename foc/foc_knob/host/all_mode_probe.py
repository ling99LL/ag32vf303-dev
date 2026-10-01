# all_mode_probe.py - machine-driven shake census across ALL knob modes.
# Every disturbance is host-driven ('rot'), no hands needed. For each case we
# record 200Hz $T and score: peak-to-peak angle, rail duty (|uq|>=2.8V),
# burst count (sustained |uq|>2V episodes) and whether the tail settles.
# Usage: python all_mode_probe.py [COM26] [tag]
import sys, time, os, csv
import serial

PORT = sys.argv[1] if len(sys.argv) > 1 else "COM26"
TAG = sys.argv[2] if len(sys.argv) > 2 else "base"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mode_probe", TAG)
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
    rows = []                                  # (ang deg, vel rad/s, uq V)
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

def rot_move(deg):
    cmd("rot %d" % deg, 0)
    if wait_msg("rot done", 20) is None:
        print("    rot timeout!")
        return False
    time.sleep(0.35)                           # landing hold release
    return True

def analyze(rows, label, expect, save=True):
    """Score one capture window and print a verdict line."""
    n = len(rows)
    if n < 50:
        print("  %-22s NO DATA (%d rows)" % (label, n))
        return
    angs = [r[0] for r in rows]
    vels = [r[1] for r in rows]
    uqs = [r[2] for r in rows]
    p2p = max(angs) - min(angs)
    rail = 100.0 * sum(1 for u in uqs if abs(u) >= 2.8) / n
    # burst episodes: |uq|>2.0V stretches separated by >=0.2s of quiet
    bursts, in_b, quiet = 0, False, 0
    for u in uqs:
        if abs(u) > 2.0:
            if not in_b and quiet >= 40:       # 0.2s at 200Hz
                bursts += 1
            in_b, quiet = True, 0
        else:
            in_b = False
            quiet += 1
    tail = rows[-160:]                         # last 0.8s
    tail_p2p = max(r[0] for r in tail) - min(r[0] for r in tail)
    tail_mx = max(abs(r[2]) for r in tail)
    tail_mv = max(abs(r[1]) for r in tail)
    mx = max(abs(u) for u in uqs)
    if save:
        os.makedirs(OUT, exist_ok=True)
        with open(os.path.join(OUT, label.replace(" ", "_") + ".csv"),
                  "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerows(rows)
    print("  %-22s p2p %6.2f  rail%5.1f%%  burst %d  maxUq %4.2f  "
          "| tail p2p %5.2f  tailUq %4.2f  tailVel %5.2f"
          % (label, p2p, rail, bursts, mx, tail_p2p, tail_mx, tail_mv))
    verdict = "OK"
    if expect == "zero":
        if mx > 0.15:
            verdict = "FREE-MODE TORQUE (bug)"
    elif expect == "settle":
        # must come to rest: tail parked, no standing torque, no ring
        if bursts >= 3 or tail_mv > 1.0:
            verdict = "RING/NOT SETTLING"
        elif tail_mx > 1.95 and tail_p2p < 0.5:
            verdict = "standing torque %.2fV at rest" % tail_mx
        elif rail > 25 and bursts >= 2:
            verdict = "rail pumping"
    elif expect == "hold":
        # wall/spring may legally hold sub-breakaway torque; must not MOVE
        if tail_p2p > 2.0 or bursts >= 3 or tail_mv > 1.0:
            verdict = "MOVING/RINGING"
    print("      -> %s" % verdict)
    return verdict

print("== all-mode shake census [%s] ==" % TAG)
cmd("tel 200", 0.3)

print("== scan calibration ==")
ser.reset_input_buffer()
cmd("scan", 0)
if wait_msg("scan ok", 30) is None:
    print("SCAN FAILED")
    sys.exit(1)

results = []

print("\n[m0 free] control: rotor parked, torque must be 0")
cmd("m0", 0.3)
for d in (30, 60):
    if rot_move(d):
        v = analyze(capture(2.0), "m0 land +%d" % d, "zero")
        results.append(("m0 +%d" % d, v))
cmd("m0", 0.2)

print("\n[m1 damp] landing decay: no standing torque at rest")
cmd("m1", 0.3)
for d in (10, 30, 60):
    if rot_move(d):
        v = analyze(capture(2.5), "m1 land +%d" % d, "settle")
        results.append(("m1 +%d" % d, v))
cmd("m0", 0.2)

print("\n[m2 inertia] landing decay: assist must not self-run")
cmd("m2", 0.3)
for d in (10, 30, 60):
    if rot_move(d):
        v = analyze(capture(3.0), "m2 land +%d" % d, "settle")
        results.append(("m2 +%d" % d, v))
cmd("m0", 0.2)

print("\n[m3 detent] regression: park +10 x6 (decode period), then a flight")
cmd("m3", 0.3)
for c in ("dw 30", "ds 2.5", "es 4", "sp 0.6", "sb 0", "pn 0", "px -1"):
    cmd(c)
time.sleep(0.4)
for i in range(6):
    if rot_move(10):
        v = analyze(capture(2.0), "m3 park +%d" % ((i + 1) * 10), "settle")
        results.append(("m3 park +%d" % ((i + 1) * 10), v))
if rot_move(40):
    v = analyze(capture(2.5), "m3 land +40 flight", "settle")
    results.append(("m3 +40", v))
cmd("m0", 0.2)

print("\n[m4 bounded] br 45: wall engage at +60 (hold), yank at +90 (snap-in)")
cmd("m4", 0.2)
cmd("br 45", 0.2)
for d in (60, 90):
    cmd("m0", 0.2)                             # rot in m0: no center re-anchor
    if rot_move(d):
        cmd("m4", 0.2)
        v = analyze(capture(3.5), "m4 wall +%d" % d, "hold" if d == 60 else "settle")
        results.append(("m4 +%d" % d, v))
cmd("m0", 0.2)

print("\n[m5 spring] released 30/60/90 deg off center: snap + ring-out")
for d in (30, 60, 90):
    cmd("m0", 0.2)
    if rot_move(d):
        cmd("m5", 0.2)
        v = analyze(capture(4.0), "m5 spring +%d" % d, "settle")
        results.append(("m5 +%d" % d, v))
cmd("m0", 0.2)

cmd("tel 0", 0.2)
ser.close()

print("\n==== SUMMARY [%s] ====" % TAG)
bad = 0
for label, v in results:
    flag = "" if v in (None, "OK") else "  <<< " + v
    if v not in (None, "OK"):
        bad += 1
    print("  %-18s %s%s" % (label, v or "SKIP", flag))
print("BAD = %d" % bad)
