"""FOC2205 open-loop acceptance runner.

Usage: python accept_openloop.py --rps 0.05 --vq 490 --direction fwd [--seconds 10]

Sets the open-loop q-voltage limit to an absolute value by stepping the console
'+/-' (x1.25 / x0.75) keys and reading the value back from the 'd' dump, then
runs 'b'/'B' (5 turns at the current speed) and reports the encoder-verified
result. A step larger than GLITCH counts is reported separately instead of being
accumulated into the angle, so an encoder artifact cannot fake a turn.
"""
import argparse, json, time
from pathlib import Path
import serial

GLITCH = 1200   # raw counts; 1200/16384 turn = 26 deg mech between samples

p = argparse.ArgumentParser()
p.add_argument('--rps', type=float, default=0.05)
p.add_argument('--vq', type=int, default=490)
p.add_argument('--direction', choices=['fwd', 'rev'], default='fwd')
p.add_argument('--seconds', type=float, default=0)   # 0 = full 5 turns + margin
p.add_argument('--turns', type=int, default=5)
p.add_argument('--port', default='COM26')
p.add_argument('--tag', default='accept')
args = p.parse_args()

LOG = Path(__file__).resolve().parents[1] / 'logs' / 'powered-20261016'
log_path = LOG / (time.strftime('%H%M%S-') + args.tag + '.txt')
frames, notes = [], []

with serial.Serial(args.port, 115200, timeout=.02, write_timeout=.5) as ser, \
        log_path.open('w', encoding='utf-8') as log:
    def send(cmd):
        ser.write(cmd.encode('ascii')); ser.flush()
        log.write('HOST ' + cmd + '\n'); log.flush()

    pending = b''
    def read():
        global pending
        pending += ser.read(max(1, ser.in_waiting))
        got = []
        while b'\n' in pending:
            line, pending = pending.split(b'\n', 1)
            text = line.decode('utf-8', 'replace').rstrip('\r')
            log.write(text + '\n'); log.flush()
            if text.startswith('#FOC,'):
                f = dict(v.split('=', 1) for v in text.split(',')[1:] if '=' in v)
                if any(k not in f for k in ['ang', 'up', 'out', 'brk', 'st']):
                    print('INCOMPLETE_FRAME', text, flush=True); continue
                f['host_time'] = time.monotonic()
                frames.append(f); got.append(f)
            elif text:
                notes.append(text); print(text, flush=True)
        return got

    def poll(seconds, interval=.1):
        end = time.monotonic() + seconds
        nxt = 0
        while time.monotonic() < end:
            now = time.monotonic()
            if now >= nxt:
                send('?'); nxt = now + interval
            read()

    def dump_vq():
        before = len(notes)
        send('d'); poll(.5)
        for text in notes[before:]:
            if text.startswith('cfg:'):
                return int(text.split('vq_max=')[1].split()[0])
        return None

    def dump_speed():
        before = len(notes)
        send('d'); poll(.5)
        for text in notes[before:]:
            if text.startswith('cfg:'):
                return float(text.split('speed=')[1].split()[0])
        return None

    def set_vq(target):
        for _ in range(24):
            cur = dump_vq()
            if cur is None:
                raise RuntimeError('no cfg dump')
            if abs(cur - target) <= max(3, target * 0.04):
                return cur
            send('-' if cur > target else '+')
            poll(.25)
        return dump_vq()

    def set_speed(rps):
        for _ in range(8):
            cur = dump_speed()
            if cur is None:
                raise RuntimeError('no cfg dump')
            if abs(cur - rps) < 1e-6:
                return cur
            send('v')
            poll(.25)
        return dump_speed()

    try:
        send('s'); poll(.8)
        if not frames:
            raise RuntimeError('No status frames')
        f = frames[-1]
        for key in ['drvok', 'encok', 'adcok', 'cal', 'ready']:
            if f.get(key) != '1':
                raise RuntimeError('Prerequisite failed: %s=%s' % (key, f.get(key)))
        if f.get('st') != '0' or f.get('out') != '0' or f.get('brk') != '0':
            raise RuntimeError('Not in healthy no-output idle: ' + json.dumps(f))

        vq = set_vq(args.vq)
        print('MODULATION vq_max=%d (%.2f%% of 8192)' % (vq, 100.0 * vq / 8192), flush=True)
        rps = set_speed(args.rps)
        print('SPEED %.3f rev/s (%.2f rpm)' % (rps, rps * 60), flush=True)

        frames.clear()
        need_ms = args.turns * 1000.0 / abs(rps)
        watch = args.seconds if args.seconds else need_ms / 1000.0 + 8.0
        send('b' if args.direction == 'fwd' else 'B')
        t0 = time.monotonic(); last_frame = t0; nxt = 0
        while time.monotonic() - t0 < watch:
            now = time.monotonic()
            if now >= nxt:
                send('?'); nxt = now + .1
            got = read()
            if got:
                last_frame = now
                for fr in got:
                    if fr.get('st') == '3' or any(fr.get(k) != '1' for k in ['drvok', 'encok', 'adcok', 'cal']):
                        print('FAULT FRAME', json.dumps(fr), flush=True)
                        raise RuntimeError('Device fault')
            if now - last_frame > 1.5:
                raise RuntimeError('Telemetry timeout')
    finally:
        send('s'); poll(.6)

active = [f for f in frames if f.get('out') == '1']
print('LOG', log_path)
print('FRAMES', len(frames), 'ACTIVE', len(active))
if not active:
    raise SystemExit('NO_ACTIVE_FRAMES')

ang, glitches, max_back = [int(active[0]['ang'])], 0, 0.0
for prev, cur in zip(active, active[1:]):
    step = (int(cur['ang']) - ang[-1] + 8192) % 16384 - 8192
    if abs(step) > GLITCH:
        glitches += 1
        print('GLITCH step=%d at up=%s' % (step, cur['up']), flush=True)
        continue
    ang.append(ang[-1] + step)
    max_back = min(max_back, step)

t = [int(f['up']) for f in active]
span_s = (t[-1] - t[0]) / 1000.0
turns = (ang[-1] - ang[0]) / 16384.0
print('ACTIVE_MS', t[-1] - t[0], 'SPAN_S %.2f' % span_s)
print('TURNS %.3f' % turns, 'DIR', 'fwd' if turns > 0 else 'rev')
print('AVG_RPM %.2f' % (turns * 60 / span_s))
print('MAX_BACKSTEP_COUNTS %d (%.2f deg)' % (max_back, max_back * 360 / 16384))
print('GLITCHES', glitches)
print('LAST', json.dumps(active[-1]))
print('END_STATE', json.dumps({k: frames[-1].get(k) for k in ['st', 'out', 'brk', 'fault', 'ang']}))
