"""FOC2205 2026-10-17 v2: park the rotor at the bad-window target.

Cycles of (magnetic-snap hops -> closed-loop 1-turn walk steps), because a
walk can trip/fault and teleport the rotor far away; after any fault the
script falls back to the snap phase. Run with the ACCEPT preset active
(set_preset.py accept) - tripping walks are rare there.

Exit codes: 0 = within tol, 2 = within accept band, 1 = not parked.
"""
import argparse, time
from pathlib import Path
import serial

ap = argparse.ArgumentParser()
ap.add_argument('--port', default='COM26')
ap.add_argument('--target', type=int, default=7378)
ap.add_argument('--tol', type=int, default=8)
ap.add_argument('--accept-lo', type=int, default=-24, help='accept band low (rel target)')
ap.add_argument('--accept-hi', type=int, default=8, help='accept band high (rel target)')
ap.add_argument('--max-cycles', type=int, default=30)
ap.add_argument('--budget-min', type=float, default=14.0)
args = ap.parse_args()

ROOT = Path(__file__).resolve().parents[3]
LOG = ROOT / 'experiments' / 'logs' / 'powered-20261017'
LOG.mkdir(parents=True, exist_ok=True)
log_path = LOG / (time.strftime('%H%M%S-') + 'snap-walk2.txt')

frames, notes = [], []
MASKS = [4, 1, 5, 2, 6, 3]


def step(a, b):
    return (b - a + 8192) % 16384 - 8192


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

    def snap(mask, hold=.32):
        send('s'); poll(.4)
        if last().get('st') != '0':
            if not recover(tag='snap-pre'):
                return None
        a0 = int(last()['ang'])
        send('m'); poll(.3)
        send('w2'); poll(.3)
        send('x%d' % mask); poll(hold)
        send('s'); poll(.9)
        f = last()
        faulted = f.get('st') == '3'
        if faulted:
            recover(tag='snap-recover')
        a1 = int(last()['ang'])
        return a1, step(a0, a1), faulted

    def walk(cmd, timeout=60.0):
        send('s'); poll(.4)
        if last().get('st') != '0':
            if not recover(tag='walk-pre'):
                return None
        a0 = int(last()['ang'])
        send(cmd); poll(.2)
        cursor = len(frames)
        started = fault = done = False
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
        say('    walk %s %s after %.1fs' % (cmd, 'FAULT' if fault else ('done' if done else 'TIMEOUT'),
                                            time.monotonic() - t0))
        if fault:
            say('    walk %s faulted: %s' % (cmd, last().get('fault')))
            recover(tag='walk-recover')
        send('s'); poll(.4)
        a1 = int(last()['ang'])
        return a1, step(a0, a1), fault

    # ---------------- run ----------------
    t_start = time.monotonic()
    send('s'); poll(1.0)
    if not frames:
        raise RuntimeError('no status frames on %s' % args.port)
    f = last()
    say('P0 fw=%s st=%s cl=%s ready=%s ang=%s' % (f.get('fw'), f.get('st'), f.get('cl'),
                                                  f.get('ready'), f.get('ang')))
    if f.get('st') != '0':
        recover(tag='P0')
    if not healthy(last()):
        raise RuntimeError('board not healthy at start')

    target = args.target
    rc = 1
    snap_i = 0
    for cyc in range(1, args.max_cycles + 1):
        if (time.monotonic() - t_start) / 60.0 > args.budget_min:
            say('budget exhausted')
            break
        ang = int(last()['ang'])
        rem = step(ang, target)
        say('cycle %d: ang=%d remaining=%+d' % (cyc, ang, rem))
        if args.accept_lo <= rem <= args.accept_hi:
            rc = 0 if abs(rem) <= args.tol else 2
            say('IN BAND ang=%d remaining=%+d rc=%d' % (ang, rem, rc))
            break

        # snap phase
        for j in range(6):
            ang = int(last()['ang'])
            rem = step(ang, target)
            if args.accept_lo <= rem <= args.accept_hi:
                break
            if abs(rem) <= 340:
                break
            mask = MASKS[snap_i % len(MASKS)]
            snap_i += 1
            r = snap(mask)
            if r is None:
                continue
            a1, d, fl = r
            say('  snap %d: mask=%d ang=%d->%d (%+d)%s remaining=%+d'
                % (snap_i, mask, a1 - d, a1, d, ' FAULT' if fl else '', step(a1, target)))

        rem0 = step(int(last()['ang']), target)
        if not (args.accept_lo <= rem0 <= args.accept_hi) and abs(rem0) > 340:
            say('  still far (%+d), more snaps' % rem0)
            continue
        # walk phase
        for j in range(14):
            ang = int(last()['ang'])
            rem = step(ang, target)
            if args.accept_lo <= rem <= args.accept_hi:
                rc = 0 if abs(rem) <= args.tol else 2
                say('IN BAND ang=%d remaining=%+d rc=%d' % (ang, rem, rc))
                break
            if (time.monotonic() - t_start) / 60.0 > args.budget_min:
                break
            cmd = 'R' if rem > 0 else 'r'
            r = walk(cmd)
            if r is None:
                continue
            a1, d, fl = r
            say('  walk %s ang=%d->%d (%+d)%s remaining=%+d'
                % (cmd, a1 - d, a1, d, ' FAULT' if fl else '', step(a1, target)))
            if fl:
                break  # teleported; back to snaps
        if rc in (0, 2):
            break

    f = last()
    ang = int(f['ang'])
    rem = step(ang, target)
    if rc == 1 and args.accept_lo <= rem <= args.accept_hi:
        rc = 0 if abs(rem) <= args.tol else 2
    say('FINAL ang=%d remaining=%+d tol=%d accept=(%+d,%+d) rc=%d st=%s out=%s ready=%s'
        % (ang, rem, args.tol, args.accept_lo, args.accept_hi, rc,
           f.get('st'), f.get('out'), f.get('ready')))
    send('s'); poll(.5)
    say('LOG ' + str(log_path))
raise SystemExit(rc)
