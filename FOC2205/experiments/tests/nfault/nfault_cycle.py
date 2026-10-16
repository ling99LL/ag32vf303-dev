"""End-to-end nFAULT injection + firmware reaction test for FOC2205.

Runs, while listening on the console UART:
  1. nfault_inject.bat  - halt the core, arm MOE (INL low = no torque), switch
                          the DRV8316C to report SPI faults on nFAULT, then send
                          one 8-clock frame so the DRV pulls nFAULT low.
                          The target is left HALTED with the fault latched.
  2. nfault_resume.bat  - resume; the firmware must latch MOTION_FAULT with
                          reason "driver break" from the hardware break flag.
  3. 'z'                - checked recovery: clears the DRV fault (nFAULT
                          released) and acks the timer break.
  4. nfault_restore.bat - put CTRL3 back to the firmware-expected default.

Usage: python experiments/tests/nfault/nfault_cycle.py [--port COM26]
Requires the board to be idle and healthy (drvok/encok/adcok/cal = 1, st/out/brk = 0).
Logs go to experiments/logs/powered-<date>/ if present, else experiments/logs/.
"""
import argparse, subprocess, time
from pathlib import Path
import serial

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
LOGDIR = ROOT / "experiments" / "logs"
sub = sorted([d for d in LOGDIR.glob("powered-*") if d.is_dir()])
LOG = sub[-1] if sub else LOGDIR
LOG.mkdir(parents=True, exist_ok=True)

p = argparse.ArgumentParser()
p.add_argument("--port", default="COM26")
p.add_argument("--listen", type=float, default=6.0)
args = p.parse_args()

log_path = LOG / (time.strftime("%H%M%S-") + "nfault-cycle.txt")
t0 = time.monotonic()
fails = []

with serial.Serial(args.port, 115200, timeout=.02) as ser, log_path.open("w", encoding="utf-8") as log:
    def emit(text):
        log.write("%8.3f %s\n" % (time.monotonic() - t0, text)); log.flush()
        print("%8.3f %s" % (time.monotonic() - t0, text), flush=True)
    def pump(seconds, keep=False):
        end = time.monotonic() + seconds
        buf = b""
        while time.monotonic() < end:
            d = ser.read(max(1, ser.in_waiting))
            if not d: continue
            buf += d
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                t = line.decode("utf-8", "replace").rstrip("\r")
                if not t.strip(): continue
                if keep or not t.startswith("isr="):
                    emit(t)
                if "MOVE ABORT: driver break" in t: fails.append(("abort", t))
                if "fault=driver break" in t: fails.append(("frame", t))
    def run(name, seconds, keep=True):
        emit("### " + name)
        pr = subprocess.Popen(["cmd.exe", "/c", str(HERE / name)], cwd=ROOT,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        pump(seconds, keep)
        out, _ = pr.communicate(timeout=20)
        (LOG / (log_path.stem + "-" + name + ".txt")).write_bytes(out)
        emit("### %s exit=%d" % (name, pr.returncode))
        for line in out.decode("utf-8", "replace").splitlines():
            if line.strip() and "DEPRECATED" not in line and not line.startswith("Info :"):
                emit("    | " + line)
        return pr.returncode
    def send(cmd, seconds, keep=True):
        emit("HOST " + cmd)
        ser.write(cmd.encode("ascii")); ser.flush()
        pump(seconds, keep)

    pump(1.0, keep=True)                     # idle listen
    run("nfault_inject.bat", 2.5)
    run("nfault_resume.bat", args.listen)    # firmware must trip on the latched break
    send("?", 1.0)
    send("f", 1.5)
    send("z", 2.0)
    send("?", 1.0)
    run("nfault_restore.bat", 2.0)

if not any(k == "abort" for k, _ in fails):
    print("WARNING: no 'MOVE ABORT: driver break' seen after resume")
print("LOG", log_path)
