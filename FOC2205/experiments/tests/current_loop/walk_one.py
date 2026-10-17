"""FOC2205 2026-10-17: single 1-turn walk step with a landing gate.

Exit 0 when the landing angle falls inside [--lo, --hi], 3 otherwise.
"""
import argparse, time
from pathlib import Path
import serial

ap = argparse.ArgumentParser()
ap.add_argument('--port', default='COM26')
ap.add_argument('--cmd', default='r')
ap.add_argument('--lo', type=int, default=7300)
ap.add_argument('--hi', type=int, default=7365)
ap.add_argument('--timeout', type=float, default=70.0)
args = ap.parse_args()

ROOT = Path(__file__).resolve().parents[3]
LOG = ROOT / 'experiments' / 'logs' / 'powered-20261017'
log_path = LOG / (time.strftime('%H%M%S-') + 'walk-one.txt')

frames, notes = [], []
with serial.Serial(args.port, 115200, timeout=.02, write_timeout=.5) as ser, \
        log_path.open('w', encoding='utf-8') as log:
    def say(*a):
        text = ' '.join(str(x) for x in a)
        print(text, flush=True)
        log.write('NOTE ' + text + '\n'); log.flush()

    def send(cmd):
        ser.write(cmd.encode('ascii')); ser.flush()
        log.write('HOST ' + cmd + '\n'); log.flush()

    pending = b''

    def read():
        global pending
        pending += ser.read(max(1, ser.in_waiting))
        while b'\n' in pending:
            line, pending = pending.split(b'\n', 1)
            text = line.decode('utf-8', 'replace').rstrip('\r')
            log.write(text + '\n'); log.flush()
            if text.startswith('#FOC,'):
                frames.append(dict(v.split('=', 1) for v in text.split(',')[1:] if '=' in v))
            elif text:
                notes.append(text)

    def poll(seconds, interval=.12):
        end = time.monotonic() + seconds
        nxt = 0.0
        while time.monotonic() < end:
            now = time.monotonic()
            if now >= nxt:
                send('?'); nxt = now + interval
            read()

    def last():
        return frames[-1] if frames else {}

    def healthy(f):
        return (f and f.get('st') == '0' and f.get('out') == '0' and f.get('ready') == '1')

    def recover(timeout=12.0, tag='recover'):
        send('s'); poll(.5)
        if healthy(last()):
            return True
        send('z')
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            poll(.5)
            if healthy(last()):
                say('%s: ok' % tag)
                return True
        say('%s: FAILED %s' % (tag, {k: last().get(k) for k in ('st', 'out', 'ready', 'fault')}))
        return False

    poll(1.0)
    if last().get('st') == '3' or not healthy(last()):
        recover(tag='pre')
    a0 = int(last()['ang'])
    say('walk_one %s from ang=%d' % (args.cmd, a0))
    send(args.cmd); poll(.2)
    cursor = len(frames)
    started = fault = done = False
    t0 = time.monotonic()
    while time.monotonic() - t0 < args.timeout:
        poll(.12)
        while cursor < len(frames):
            f = frames[cursor]; cursor += 1
            if f.get('st') == '1':
                started = True
            if f.get('st') == '3':
                fault = True
                break
            if started and f.get('st') in ('4', '0') and f.get('out') == '0':
                done = True
                break
        if fault or done:
            break
    say('walk %s %s after %.1fs' % (args.cmd, 'FAULT' if fault else ('done' if done else 'TIMEOUT'),
                                    time.monotonic() - t0))
    if fault:
        say('fault: %s' % last().get('fault'))
        recover(tag='walk-recover')
    send('s'); poll(.4)
    a1 = int(last()['ang'])
    ok = args.lo <= a1 <= args.hi
    say('LANDING %d (from %d, step %+d) gate[%d..%d] -> %s'
        % (a1, a0, (a1 - a0 + 8192) % 16384 - 8192, args.lo, args.hi, 'OK' if ok else 'MISS'))
    say('LOG ' + str(log_path))
raise SystemExit(0 if ok else 3)
