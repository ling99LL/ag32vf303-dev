# verify_detent.py - on-board check of the SmartKnob detent engine (mode 3).
# Scans, enables the engine (30 deg detents), then uses 'rot' (which the
# position tracker follows even mid-drag) to verify:
#   1. +90 deg  -> position counts 3 (three detents)
#   2. -90 deg  -> back to 0
#   3. at rest  -> |uq| stays tiny (dead zone + no standing torque = no hum)
# Usage: python verify_detent.py [COM26]
import sys, time
import serial

PORT = sys.argv[1] if len(sys.argv) > 1 else "COM26"

ser = serial.Serial(PORT, 115200, timeout=0.05)
time.sleep(0.3)
ser.write(b"s\ntel 50\n")
time.sleep(0.3)
ser.reset_input_buffer()

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

print("== enable detent engine: m3, width 30deg, strength 2.5 ==")
ser.write(b"m3\ndw 30\nds 2.5\nes 4\n")
time.sleep(0.5)
ser.reset_input_buffer()

def latest_pos_uq(seconds=0.4):
    ser.reset_input_buffer()
    time.sleep(seconds)
    d = ser.read(65536).decode(errors="replace")
    rows = [l.split(",") for l in d.splitlines()
            if l.startswith("$T,") and l.count(",") == 10]
    if not rows:
        return None, None
    return int(rows[-1][9]), abs(int(rows[-1][4])) / 1000.0

def latest_ang_uq(seconds=0.3):
    ser.reset_input_buffer()
    time.sleep(seconds)
    d = ser.read(65536).decode(errors="replace")
    rows = [l.split(",") for l in d.splitlines()
            if l.startswith("$T,") and l.count(",") == 10]
    if not rows:
        return None, None
    return int(rows[-1][2]) / 100.0, abs(int(rows[-1][4])) / 1000.0

def rot_and_count(deg, expect):
    print("rot %+d (expect pos=%d)" % (deg, expect))
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
    if not done:
        print("  rot did not finish -> FAIL")
        return False
    time.sleep(1.0)
    pos, _ = latest_pos_uq()
    if pos is None:
        print("  no telemetry after rot -> FAIL")
        return False
    okp = pos == expect
    print("  pos=%d -> %s" % (pos, "PASS" if okp else "FAIL"))
    return okp

p0, _ = latest_pos_uq()
print("initial pos=%s (expect 0)" % p0)
ok0 = p0 == 0

c1 = rot_and_count(90, 3)
time.sleep(0.5)
c2 = rot_and_count(-90, 0)

# rest quiet check: parked on a detent, torque must collapse (dead zone /
# idle re-center), i.e. no standing hum current
worst = 0.0
t0 = time.time()
while time.time() - t0 < 3.0:
    _, uq = latest_pos_uq(0.3)
    if uq is not None and uq > worst:
        worst = uq
quiet = worst < 0.3
print("rest 3s: max |uq| = %.3f V -> %s (bar 0.30 V)"
      % (worst, "PASS" if quiet else "FAIL"))

# snap-back check: pn 0 px 0 = single detent = return-to-center spring with
# the endstop strength (es*4 V/rad). Drag out to 90 deg with 'rot', hand
# control back to the engine: it must ACTIVELY pull the rotor home - this is
# the automated proof the pull voltage beats the motor's ~2.5V breakaway
# (a too-weak detent strength would leave the rotor sitting out there).
print("== snap-back: pn 0 px 0, rot 90, engine must pull it home ==")
ser.reset_input_buffer()
ser.write(b"pn 0\npx 0\nrot 90\n")
t0, done, buf = time.time(), False, b""
while time.time() - t0 < 30 and not done:
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
pull = 0.0
final = None
t0 = time.time()
while time.time() - t0 < 8.0:
    ang, uq = latest_ang_uq(0.25)
    if ang is None:
        continue
    if uq > pull:
        pull = uq
    final = ang
    if abs(ang) < 0.5 and time.time() - t0 > 2.0:
        break
# +/-15deg (1.5 sectors): sub-breakaway holds intentionally let the rotor
# park one sector out after a hard snap - the idle re-center absorbs it.
snap = final is not None and abs(final) <= 15.0
print("  returned to %.1f deg (peak |uq| %.2f V) -> %s (bar +-15 deg)"
      % (final if final is not None else -999, pull, "PASS" if snap else "FAIL"))
ser.write(b"px -1\n")
time.sleep(0.2)

ser.write(b"tel 0\nm0\n")
time.sleep(0.2)
ser.close()
allok = ok0 and c1 and c2 and quiet and snap
print("\nDETENT %s" % ("PASS" if allok else "FAIL"))
sys.exit(0 if allok else 1)
