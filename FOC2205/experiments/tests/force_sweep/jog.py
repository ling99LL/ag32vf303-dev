"""Jog the rotor to a new electrical alignment with manual mode.

`m` enters manual (mask 0 = zero vector, no torque), `wN` picks the power gear
(N * MOTION_POWER_PCT_MAX / 4), `xN` applies the phase mask (1..6 are the six
non-zero vectors, 60 electrical degrees apart), then `s` releases. Prints the
encoder angle before and after so the position shift is measured, not assumed.
"""
import argparse, re, sys, time
import serial

ap = argparse.ArgumentParser()
ap.add_argument('--port', default='COM26')
ap.add_argument('--mask', type=int, default=1, choices=range(1, 7))
ap.add_argument('--gear', type=int, default=2, choices=range(1, 5))
ap.add_argument('--hold', type=float, default=1.5)
args = ap.parse_args()

pending = b''

def frame_of(text):
    if text.startswith('#FOC,'):
        return dict(v.split('=', 1) for v in text.split(',')[1:] if '=' in v)
    return None

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

    def poll(seconds, interval=.15):
        end = time.monotonic() + seconds
        nxt = 0.0
        last = None
        while time.monotonic() < end:
            now = time.monotonic()
            if now >= nxt:
                send('?'); nxt = now + interval
            for text in read():
                print(text, flush=True)
                f = frame_of(text)
                if f:
                    last = f
        return last

    send('s'); poll(.4)
    before = poll(.3)
    if before.get('st') != '0' or before.get('out') != '0':
        print('NOT IDLE: st=%s out=%s' % (before.get('st'), before.get('out')), flush=True)
        sys.exit(2)
    print('ANGLE BEFORE %s' % before.get('ang'), flush=True)

    send('m'); poll(.3)
    send('w%d' % args.gear); poll(.3)
    send('x%d' % args.mask); poll(args.hold)
    send('s'); poll(.6)
    after = poll(.3)
    print('ANGLE AFTER %s' % after.get('ang'), flush=True)
    if after.get('st') != '0' or after.get('out') != '0':
        print('NOT IDLE AFTER JOG: st=%s out=%s fault=%r'
              % (after.get('st'), after.get('out'), after.get('fault')), flush=True)
        sys.exit(2)
    delta = (int(after['ang']) - int(before['ang']) + 8192) % 16384 - 8192
    print('JOG DELTA %+d raw' % delta, flush=True)
