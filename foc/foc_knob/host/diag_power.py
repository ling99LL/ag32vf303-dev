# Diagnose a "halls never move" scan: run the open-loop drag and, mid-drag,
# halt the core twice over JTAG and dump GPTIMER CNT/CCR0-2 (are the three
# phase duties actually rotating?) plus the GPIO0 input register (are the
# hall pins frozen?).
import serial, subprocess, time, sys

OCD = [r"C:\Users\Administrator\.platformio\packages\tool-agrv_openocd\bin\openocd_cmd.bat",
       "-s", r"C:\Users\Administrator\.platformio\platforms\AgRV\etc",
       "-c", "variable ADAPTER_SPEED 10000",
       "-c", "variable ADAPTER cmsis-dap",
       "-f", "agrv2k.cfg"]

READ = ("init; halt; "
        "echo CNT; mdw 0x40020024; "
        "echo CCR0; mdw 0x40020034; "
        "echo CCR1; mdw 0x40020038; "
        "echo CCR2; mdw 0x4002003c; "
        "echo GPIO_IN; mdw 0x400143fc; "
        "echo GPIO_DIR; mdw 0x40014400; "
        "echo BDTR; mdw 0x40020044; "
        "resume; shutdown")

def probe(tag):
    r = subprocess.run(OCD + ["-c", READ], capture_output=True, text=True, timeout=30)
    out = (r.stdout + r.stderr)
    print("---- probe %s ----" % tag)
    for ln in out.splitlines():
        ln = ln.strip()
        if ln:
            print("  " + ln)

s = serial.Serial("COM26", 115200, timeout=0.05)
time.sleep(0.3)
s.write(b"tel 0\ns\n")
time.sleep(0.3)
s.reset_input_buffer()
s.write(b"scan\n")
time.sleep(2.0)
probe("A (t=2s)")
time.sleep(2.0)
probe("B (t=4s)")

buf = b""
t0 = time.time()
while time.time() - t0 < 10:
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
                sys.exit(0)
s.close()
