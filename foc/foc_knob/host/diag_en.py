# Force EN high via JTAG mid-drag: if the pin holds and halls start moving,
# the firmware lost the EN write somewhere; if the pin reads back 0, something
# external is pulling it low (wiring); if it holds but halls stay frozen, the
# driver board / 12V bus is dead.
import serial, subprocess, time, sys

OCD = [r"C:\Users\Administrator\.platformio\packages\tool-agrv_openocd\bin\openocd_cmd.bat",
       "-s", r"C:\Users\Administrator\.platformio\platforms\AgRV\etc",
       "-c", "variable ADAPTER_SPEED 10000",
       "-c", "variable ADAPTER cmsis-dap",
       "-f", "agrv2k.cfg"]

WRITE_EN = ('init; halt; '
            'mww 0x40014004 0xff; '
            'mem2array gi 32 0x400143fc 1; echo AFTER_EN=$gi(0); '
            'mem2array dr 32 0x40014400 1; echo DIR=$dr(0); '
            'resume; shutdown')

READ = ('init; halt; '
        'mem2array gi 32 0x400143fc 1; echo GPIOIN=$gi(0); '
        'mem2array c0 32 0x40020034 1; echo CCR0=$c0(0); '
        'resume; shutdown')

def run(cmd, tag):
    r = subprocess.run(OCD + ["-c", cmd], capture_output=True, text=True, timeout=30)
    for ln in (r.stdout + r.stderr).splitlines():
        ln = ln.strip()
        if "=$" in ln or ln.startswith(("AFTER_EN", "GPIOIN", "DIR", "CCR0")):
            print("  %s: %s" % (tag, ln))
    return r

s = serial.Serial("COM26", 115200, timeout=0.05)
time.sleep(0.3)
s.write(b"tel 0\ns\n")
time.sleep(0.3)
s.reset_input_buffer()
s.write(b"scan\n")
time.sleep(2.0)
print("== force EN=1 via JTAG ==")
run(WRITE_EN, "t=2.0s")
for i, t in enumerate((1.5, 1.5, 1.5)):
    time.sleep(t)
    run(READ, "t=%.1fs" % (3.5 + 1.5 * (i + 1)))

buf = b""
t0 = time.time()
while time.time() - t0 < 12:
    d = s.read(256)
    if d:
        buf += d
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            x = line.decode(errors="replace").strip()
            if x:
                print("  " + x)
            if "scan ok" in x or "scan FAILED" in x:
                s.close()
                sys.exit(0)
s.close()
