"""Restore the runtime motion config recorded before the 2026-10-16 reflash.

Boot defaults (gear indices at reset): kp=2 kd=0.02 ki=1.5 follow=500
vel_win=256 ang_filt=1/64 hybrid=1. The closed-loop session that produced the
force-sweep data ran kp=4 kd=0 ki=10 follow=800 vel_win=64 ang_filt=1/1024
hybrid=0. This walks the console gear tables back to those values and verifies
the result against the firmware's own `d` dump (kff/kfric already match).
"""
import argparse, sys, time
import serial

ap = argparse.ArgumentParser()
ap.add_argument('--port', default='COM26')
args = ap.parse_args()

# k: kp 2->4 | i x2: ki 1.5->10 | j x3: kd 0.02->0 | c: follow 500->800
# q x2: angle filt 1/64->1/1024 | u x3: vel_win 256->64 | y: hybrid on->off
SEQUENCE = ['k', 'i', 'i', 'j', 'j', 'j', 'c', 'q', 'q', 'u', 'u', 'u', 'y']
EXPECT = [
    'kp=4 kd=0/1000 ki=100/10 kff=125/1000 kfric=150',
    'follow=800',
    'hybrid=0',
    'vel_win=64 ang_filt=1/1024',
]

pending = b''

with serial.Serial(args.port, 115200, timeout=.02, write_timeout=.5) as ser:
    def send(cmd):
        ser.write(cmd.encode('ascii')); ser.flush()

    def read():
        global pending
        pending += ser.read(max(1, ser.in_waiting))
        out = []
        while b'\n' in pending:
            line, pending = pending.split(b'\n', 1)
            text = line.decode('utf-8', 'replace').rstrip('\r')
            if text:
                out.append(text)
        return out

    def drain(seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            for text in read():
                print(text, flush=True)

    drain(.3)
    for key in SEQUENCE:
        send(key)
        drain(.25)

    send('d')
    end = time.monotonic() + .6
    dump = []
    while time.monotonic() < end:
        for text in read():
            print(text, flush=True)
            if text.startswith('cfg:') or text.startswith('hybrid='):
                dump.append(text)
    dump = ' '.join(dump)
    missing = [frag for frag in EXPECT if frag not in dump]
    if missing:
        print('MISMATCH: ' + '; '.join(missing), flush=True)
        sys.exit(2)
    print('CONFIG RESTORED', flush=True)
