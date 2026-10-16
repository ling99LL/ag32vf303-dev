"""FOC2205 2026-10-17: park the rotor at the bad-window target using
(a) coarse magnetic-snap hops (manual mask jogs, ~±1363 raw per hop) and
(b) fine closed-loop walk steps (~24..47 raw per 1-turn move).

Stops as soon as the rotor rests within --tol of --target. The rotor must be
idle/healthy when the script starts (run 'z' first if a fault is latched).
"""
import argparse, time
from pathlib import Path
import serial

ap = argparse.ArgumentParser()
ap.add_argument('--port', default='COM26')
ap.add_argument('--target', type=int, default=7378)
ap.add_argument('--tol', type=int, default=6)
ap.add_argument('--max-snaps', type=int, default=24)
ap.add_argument('--max-walks', type=int, default=30)
args = ap.parse_args()

ROOT = Path(__file__).resolve().parents[3]
LOG = ROOT / 'experiments' / 'logs' / 'powered-20261017'
LOG.mkdir(parents=True, exist_ok=True)
log_path = LOG / (time.strftime('%H%M%S-') + 'snap-walk.txt')

frames, notes = [], []


def step(a, b):
    return (b - a + 8192) % 16384 - 8192


with serial.Serial(args.port, 115200, timeout=.02, write_timeout=.5) as ser, \
        log_path.open('w', encoding='utf-8') as log:
    def say(*a):
        text = ' '.join(str(x) for x in a)
        print(text, flush=True)
        log.write(text + '\n'); log.flush()

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
                f = dict(v.split('=', 1) for v in text.split(',')[1:] if '=' in v)
                if all(k in f for k in ('ang', 'up', 'out', 'st', 'vq')):
                    frames.append(f)
            elif text:
                notes.append(text)

    def poll(seconds, interval=.15):
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
        return (f and f.get('st') == '0' and f.get('out') == '0'
                and f.get('ready') == '1')

    def recover(timeout=10.0, tag='recover'):
        send('s'); poll(.4)
        if healthy(last()):
            return True
        send('z')
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            poll(.4)
            if healthy(last()):
                say('%s: ok' % tag)
                return True
        say('%s: FAILED state=%s' % (tag, {k: last().get(k) for k in ('st', 'out', 'ready', 'fault')}))
        return False

    def snap(mask, gear, hold):
        send('s'); poll(.4)
        if last().get('st') != '0':
            if not recover(tag='snap-pre'):
                return None
        a0 = int(last()['ang'])
        send('m'); poll(.3)
        send('w%d' % gear); poll(.3)
        send('x%d' % mask); poll(hold)
        send('s'); poll(.9)
        f = last()
        faulted = f.get('st') == '3'
        if faulted:
            recover(tag='snap-recover')
        a1 = int(last()['ang'])
        return a1, step(a0, a1), faulted

    def walk_once(cmd, timeout=60.0):
        send('s'); poll(.4)
        if last().get('st') != '0':
            if not recover(tag='walk-pre'):
                return None
        a0 = int(last()['ang'])
        send(cmd); poll(.3)
        cursor = len(frames)
        started = False
        fault = done = False
        t0 = time.monotonic()
        while time.monotonic() - t0 < timeout:
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
        say('    walk %s %s after %.1fs' % (cmd, 'FAULT' if fault else ('done' if done else 'TIMEOUT'), time.monotonic() - t0))
        if fault:
            say('    walk %s faulted: %s' % (cmd, last().get('fault')))
            recover(tag='walk-recover')
        send('s'); poll(.4)
        a1 = int(last()['ang'])
        return a1, step(a0, a1), fault

    # ---------------- run ----------------
    send('s'); poll(1.0)
    if not frames:
        raise RuntimeError('no status frames on %s' % args.port)
    f = last()
    say('P0 fw=%s up=%s st=%s cl=%s ready=%s ang=%s'
        % (f.get('fw'), f.get('up'), f.get('st'), f.get('cl'), f.get('ready'), f.get('ang')))
    if f.get('st') != '0':
        recover(tag='P0')
    if not healthy(last()):
        raise RuntimeError('board not healthy at start')

    target, tol = args.target, args.tol
    landings = []
    hit = False

    # ---- phase 1: magnetic-snap hops ----
    masks = [4, 1, 5, 2, 6, 3]
    mi = 0
    for i in range(1, args.max_snaps + 1):
        f = last()
        ang = int(f['ang'])
        remaining = step(ang, target)
        if abs(remaining) <= tol:
            say('WINDOW ang=%d remaining=%+d (before snap %d)' % (ang, remaining, i))
            hit = True
            break
        if abs(remaining) <= 420:
            say('close enough for walk: remaining=%+d after %d snaps' % (remaining, i - 1))
            break
        # rotate mask if the last three landings collapsed to <=2 distinct spots
        distinct = set(a for a, _, _ in landings[-3:])
        if len(landings) >= 3 and len(distinct) <= 2:
            mi = (mi + 1) % len(masks)
            say('    (mask rotation -> %d, landings stuck on %s)' % (masks[mi], sorted(distinct)))
        mask = masks[mi]
        hold = 0.45 if abs(remaining) > 1400 else 0.3
        r = snap(mask, 2, hold)
        if r is None:
            continue
        a1, d, fl = r
        landings.append((a1, d, fl))
        say('snap %2d: mask=%d hold=%.2f ang=%d -> %d (%+d)%s | remaining=%+d'
            % (i, mask, hold, a1 - d, a1, d, ' FAULT' if fl else '', step(a1, target)))
        if abs(step(a1, target)) <= tol:
            say('WINDOW reached by snap %d: ang=%d' % (i, a1))
            hit = True
            break

    # ---- phase 2: fine closed-loop walk ----
    if not hit:
        for i in range(1, args.max_walks + 1):
            f = last()
            ang = int(f['ang'])
            remaining = step(ang, target)
            if abs(remaining) <= tol:
                say('WINDOW ang=%d remaining=%+d (walk %d)' % (ang, remaining, i))
                hit = True
                break
            cmd = 'R' if remaining > 0 else 'r'
            r = walk_once(cmd)
            if r is None:
                continue
            a1, d, fl = r
            say('walk %2d: %s ang=%d -> %d (%+d)%s remaining=%+d'
                % (i, cmd, a1 - d, a1, d, ' FAULT' if fl else '', step(a1, target)))

    f = last()
    ang = int(f['ang'])
    say('FINAL ang=%d remaining=%+d tol=%d hit=%s st=%s out=%s ready=%s'
        % (ang, step(ang, target), tol, hit, f.get('st'), f.get('out'), f.get('ready')))
    send('s'); poll(.5)
say('LOG', log_path)
raise SystemExit(0 if hit else 1)
