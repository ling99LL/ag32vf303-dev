"""Recover the FOC2205 from a latched fault and verify it is idle/healthy.

Sends `s` (release) and, when the state is not idle, `z` (checked fault
recovery), then polls `?` until the board reports st=0 / out=0 / ready=1.
Exit code 0 means the board is back in no-output standby.
"""
import argparse, sys, time
import serial

ap = argparse.ArgumentParser()
ap.add_argument('--port', default='COM26')
ap.add_argument('--seconds', type=float, default=8.0)
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

    def summary(f):
        if not f:
            return 'no frame'
        return ('st=%s out=%s brk=%s ready=%s calok=%s calst=%s drv=%s fault=%r'
                % (f.get('st'), f.get('out'), f.get('brk'), f.get('ready'),
                   f.get('calok'), f.get('calst'), f.get('drv'), f.get('fault')))

    send('s'); poll(.4)
    last = poll(.3)
    print('STATE BEFORE: ' + summary(last), flush=True)

    healthy = (last and last.get('st') == '0' and last.get('out') == '0'
               and last.get('ready') == '1')
    if not healthy:
        send('z')
        end = time.monotonic() + args.seconds
        while time.monotonic() < end:
            last = poll(.4)
            if last and last.get('st') == '0' and last.get('out') == '0' \
                    and last.get('ready') == '1':
                healthy = True
                break
        print('STATE AFTER z: ' + summary(last), flush=True)

    send('d'); poll(.4)
    if not healthy:
        print('RECOVER FAILED', flush=True)
        sys.exit(2)
    print('RECOVER OK', flush=True)
