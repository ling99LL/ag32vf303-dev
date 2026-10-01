# drag_release_probe.py - "release WITH residual velocity" census.
# The rot-landing census always arrives at crawl speed (hold phase kills
# velocity), so it never exercises the scenario the user reported: turn,
# let go while still moving. Method: the m5 homing drag spins the rotor up
# to ~1.2rad/s toward center, then we switch to the target mode MID-FLIGHT
# - the drag torque vanishes and the rotor coasts into the new mode with
# real kinetic energy. Machine analog of a light flick-and-release.
# Usage: python drag_release_probe.py [COM26] [tag]
import sys, time, os, csv
import serial

PORT = sys.argv[1] if len(sys.argv) > 1 else "COM26"
TAG = sys.argv[2] if len(sys.argv) > 2 else "rel"
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

def read_until(seconds, stop=None):
    """Stream $T rows for `seconds`; stop(vel, ang) -> stop early."""
    rows, t0 = [], time.time()
    while time.time() - t0 < seconds:
        d = ser.read(65536)
        if not d:
            continue
        for l in d.decode(errors="replace").splitlines():
            if ROW(l):
                f = l.split(",")
                r = (float(f[2]) / 100.0, float(f[3]) / 1000.0,
                     float(f[4]) / 1000.0)
                rows.append(r)
                if stop is not None and stop(r[1], r[0]):
                    return rows, True
    return rows, False

def rot_move(deg):
    cmd("rot %d" % deg, 0)
    if wait_msg("rot done", 20) is None:
        print("    rot timeout!")
        return False
    time.sleep(0.35)
    return True

def analyze(rows, label, tail_uq_bar):
    n = len(rows)
    if n < 100:
        print("  %-20s NO DATA (%d)" % (label, n))
        return "SKIP"
    angs = [r[0] for r in rows]; vels = [r[1] for r in rows]
    uqs = [r[2] for r in rows]
    p2p = max(angs) - min(angs)
    rail = 100.0 * sum(1 for u in uqs if abs(u) >= 2.8) / n
    bursts, in_b, quiet = 0, False, 0
    for u in uqs:
        if abs(u) > 2.0:
            if not in_b and quiet >= 40:
                bursts += 1
            in_b, quiet = True, 0
        else:
            in_b = False
            quiet += 1
    # settle time: last sample with torque or motion
    settle = 0.0
    for i, (a, v, u) in enumerate(zip(angs, vels, uqs)):
        if abs(u) > 0.5 or abs(v) > 0.3:
            settle = i / 200.0
    tail = rows[-200:]                       # last 1s
    tp2p = max(r[0] for r in tail) - min(r[0] for r in tail)
    tuq = max(abs(r[2]) for r in tail)
    tvel = max(abs(r[1]) for r in tail)
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, label.replace(" ", "_") + ".csv"),
              "w", newline="") as fh:
        csv.writer(fh).writerows(rows)
    verdict = "OK"
    if bursts >= 3 or tvel > 0.5 or tp2p > 2.0:
        verdict = "RING/MOVING TAIL"
    elif tuq > tail_uq_bar:
        verdict = "standing torque %.2fV" % tuq
    print("  %-20s p2p %6.2f rail%5.1f%% burst %d settle %4.1fs | "
          "tail p2p %5.2f uq %4.2f vel %5.2f -> %s"
          % (label, p2p, rail, bursts, settle, tp2p, tuq, tvel, verdict))
    return verdict

print("== drag-release census [%s] ==" % TAG)
cmd("tel 200", 0.3)
print("== scan calibration ==")
ser.reset_input_buffer()
cmd("scan", 0)
if wait_msg("scan ok", 30) is None:
    print("SCAN FAILED"); sys.exit(1)

results = []

def release_case(mode_cmd, label, tail_uq_bar, capture_s=3.5, disp=-80):
    """displace, let m5 drag spin up, hand off to `mode_cmd` mid-flight."""
    cmd("m0", 0.2)
    if not rot_move(disp):
        results.append((label, "SKIP")); return
    cmd("m5", 0.05)                          # drag engages, accelerates home
    rows, hit = read_until(4.0, stop=lambda v, a: abs(v) >= 0.8)
    if not hit:
        print("  %-20s drag never reached 0.8rad/s" % label)
        results.append((label, "SKIP")); return
    cmd(mode_cmd, 0.05)                      # torque handoff IN FLIGHT
    rows2, _ = read_until(capture_s)
    results.append((label, analyze(rows2, label, tail_uq_bar)))

# control: let the drag finish untouched (its own smoothness baseline)
cmd("m0", 0.2)
if rot_move(-80):
    cmd("m5", 0.05)
    rows, _ = read_until(4.5)
    results.append(("m5 control", analyze(rows, "m5 control", 0.50)))

release_case("m0", "m0 coast release", 0.15)
release_case("m1", "m1 damp catch", 0.15)
release_case("m2", "m2 inertia catch", 0.15)
cmd("m4", 0.2); cmd("br 45", 0.2)
release_case("m4", "m4 inbound release", 0.15)
cmd("m3", 0.2)
for c in ("dw 30", "ds 2.5", "es 4", "sp 0.6", "sb 0", "pn 0", "px -1"):
    cmd(c)
# detent: three phases (displacement changes which box/snap it lands in)
release_case("m3", "m3 catch phase A", 1.95, disp=-70)
release_case("m3", "m3 catch phase B", 1.95, disp=-80)
release_case("m3", "m3 catch phase C", 1.95, disp=-90)

cmd("m0", 0.2)
cmd("tel 0", 0.2)
ser.close()

print("\n==== SUMMARY [%s] ====" % TAG)
bad = 0
for label, v in results:
    flag = "" if v in (None, "OK") else "  <<< " + str(v)
    if v not in (None, "OK"):
        bad += 1
    print("  %-20s %s%s" % (label, v or "SKIP", flag))
print("BAD = %d" % bad)
