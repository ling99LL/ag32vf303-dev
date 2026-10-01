# Is the hall input changing IN REAL TIME during the open-loop drag?
# Run 'scan' and read GPIO0 input + CCR0 four times via JTAG while it drags.
import serial, subprocess, time, sys

OCD = [r"C:\Users\Administrator\.platformio\packages\tool-agrv_openocd\bin\openocd_cmd.bat",
       "-s", r"C:\Users\Administrator\.platformio\platforms\AgRV\etc",
       "-c", "variable ADAPTER_SPEED 10000",
       "-c", "variable ADAPTER cmsis-dap",
       "-f", "agrv2k.cfg"]

READ = ('init; halt; '
        'mem2array c0 32 0x40020034 1; echo CCR0=$c0(0); '
        'mem2array gi 32 0x400143fc 1; echo GPIOIN=$gi(0); '
        'resume; shutdown')

def probe(tag):
    r = subprocess.run(OCD + ["-c", READ], capture_output=True, text=True, timeout=30)
    vals = {}
    for ln in (r.stdout + r.stderr).splitlines():
        ln = ln.strip()
        if ln.startswith("CCR0="):
            vals["ccr0"] = ln.split("=")[1]
        if ln.startswith("GPIOIN="):
            vals["hall"] = (int(ln.split("=")[1], 16) >> 4) & 7
    print("%s: CCR0=%s hallbits=%s" % (tag, vals.get("ccr0"), vals.get("hall")))
    return vals

s = serial.Serial("COM26", 115200, timeout=0.05)
time.sleep(0.3)
s.write(b"tel 0\ns\n")
time.sleep(0.3)
s.reset_input_buffer()
s.write(b"scan\n")
results = []
for i in range(4):
    time.sleep(1.5)
    results.append(probe("t=%.1fs" % (2.0 + 1.5 * i)))

buf = b""
t0 = time.time()
while time.time() - t0 < 12:
    d = s.read(256)
    if d:
        buf += d
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            t = line.decode(errors="replace").strip()
            if t:
                print("  " + t)
            if "scan ok" in t or "scan FAILED" in t:
                s.close()
                halls = [r["hall"] for r in results]
                ccrs = [r["ccr0"] for r in results]
                print("\nVERDICT: hallbits over drag = %s -> %s" %
                      (halls, "CHANGING (rotor+halls track)" if len(set(halls)) > 1
                       else "FROZEN (rotor not following or pins dead)"))
                print("VERDICT: CCR0 over drag = %s -> %s" %
                      (ccrs, "ROTATING (vector commands)" if len(set(ccrs)) > 1
                       else "STATIC"))
                sys.exit(0)
s.close()
