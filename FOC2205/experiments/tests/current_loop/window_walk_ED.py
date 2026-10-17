"""FOC2205 2026-10-17: park the rotor inside the 2026-10-16 bad start window,
then run the decisive voltage-mode (E) and current-loop (D) starts there.

Positioning trick: an open-loop mask jog snaps between magnetic equilibria and
trips the jump guard, so instead we walk with closed-loop 1-turn moves.  Each
move ends ~134 raw short of the start (residual scatter ~74..194 raw), so the
landing positions form a random walk; when a landing falls inside
[target-tol, target+tol] the next move *starts* exactly inside the window.

Every line the script prints is also written to the log file.
"""
import argparse, statistics, sys, time
from pathlib import Path
import serial

GLITCH = 1200

ap = argparse.ArgumentParser()
ap.add_argument('--port', default='COM26')
ap.add_argument('--target', type=int, default=7378)
ap.add_argument('--tol', type=int, default=6)
ap.add_argument('--max-walk', type=int, default=45)
ap.add_argument('--speed-gear', type=int, default=2, help='index into 0.02/0.05/0.1/0.25/0.5 gears')
args = ap.parse_args()

ROOT = Path(__file__).resolve().parents[3]
LOG = ROOT / 'experiments' / 'logs' / 'powered-20261017'
LOG.mkdir(parents=True, exist_ok=True)
log_path = LOG / (time.strftime('%H%M%S-') + 'window-walk.txt')

frames, notes = [], []


def frame_of(text):
    if text.startswith('#FOC,'):
        return dict(v.split('=', 1) for v in text.split(',')[1:] if '=' in v)
    return None


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
                f = frame_of(text)
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

    def notes_after(mark, seconds=.8):
        send('F'); poll(seconds)
        return notes[mark:]

    def oc_dump(tag):
        mark = len(notes)
        lines = notes_after(mark)
        say('OC[%s]' % tag)
        for t in lines:
            if t and not t.startswith('isr='):
                say('    ' + t)

    def run_move(tag, cmd='r', timeout=35.0):
        send('s'); poll(.4)
        f0 = last()
        if f0.get('st') != '0' or f0.get('out') != '0':
            say('%s: NOT IDLE before start: %s' % (tag, {k: f0.get(k) for k in ('st', 'out')}))
            if not recover(tag=tag + '-pre'):
                raise RuntimeError('cannot reach idle before ' + tag)
            f0 = last()
        start_ang = int(f0['ang'])
        say('=== %s: cmd=%s start ang=%d cl=%s speed=%s ===' % (tag, cmd, start_ang, f0.get('cl'), f0.get('vel')))
        send(cmd); poll(.3)
        cursor = len(frames)
        started = False
        fault = None
        done = False
        active = []
        t0 = time.monotonic()
        while time.monotonic() - t0 < timeout:
            poll(.15)
            while cursor < len(frames):
                f = frames[cursor]; cursor += 1
                if f.get('st') == '1':
                    started = True
                if f.get('out') == '1':
                    active.append(f)
                if f.get('st') == '3':
                    fault = f
                    break
                if started and f.get('st') in ('4', '0') and f.get('out') == '0':
                    done = True
                    break
            if fault or done:
                break
        res = dict(tag=tag, cmd=cmd, start=start_ang, done=done, fault=None, active=len(active))
        if fault:
            say('    FAULT t=%s ms: %s' % (fault.get('t'), fault.get('fault')))
            for f in frames[-4:]:
                say('      up=%s ang=%s ia=%s ib=%s ic=%s vq=%s id=%s iq=%s ocn=%s ocmx=%s ocg=%s'
                    % (f.get('up'), f.get('ang'), f.get('ia'), f.get('ib'), f.get('ic'), f.get('vq'),
                       f.get('id'), f.get('iq'), f.get('ocn'), f.get('ocmx'), f.get('ocg')))
            res['fault'] = fault.get('fault')
            res['end'] = int(fault.get('ang'))
        elif done and active:
            angs = [int(active[0]['ang'])]
            steps, gl = [], 0
            for p, c in zip(active, active[1:]):
                d = step(int(p['ang']), int(c['ang']))
                if abs(d) > GLITCH:
                    gl += 1
                    continue
                steps.append(d); angs.append(angs[-1] + d)
            travel = angs[-1] - angs[0]
            dt = (int(active[-1]['up']) - int(active[0]['up'])) / 1000.0
            errs = [abs(int(f['err'])) for f in active]
            vqs = [abs(int(f['vq'])) for f in active]
            iqs = [int(f['iq']) for f in active]
            res.update(travel=travel, end=int(active[-1]['ang']),
                       rpm=travel * 60 / 16384.0 / dt if dt else 0,
                       peak_err=max(errs), peak_vq=max(vqs),
                       iq=[min(iqs), max(iqs)],
                       step_std=statistics.pstdev(steps) if len(steps) > 1 else 0, gl=gl,
                       ocn=active[-1].get('ocn'), ocmx=active[-1].get('ocmx'), ocg=active[-1].get('ocg'))
            say('    DONE travel=%+d (%.3f turns) %.2f rpm peak_err=%d peak_vq=%d iq[%d..%d] '
                'step_std=%.1f glitch=%d end ang=%d  ocn=%s ocmx=%s ocg=%s'
                % (travel, travel / 16384.0, res['rpm'], res['peak_err'], res['peak_vq'],
                   iqs[0] if iqs else 0, max(iqs) if iqs else 0, res['step_std'], gl,
                   res['end'], res['ocn'], res['ocmx'], res['ocg']))
        else:
            res['end'] = int(last().get('ang', start_ang))
            say('    INCOMPLETE started=%s frames=%d' % (started, len(active)))
        oc_dump(tag)
        return res

    # ---------------- run ----------------
    send('s'); poll(1.0)
    if not frames:
        raise RuntimeError('no frames')
    say('P0 fw=%s up=%s st=%s cl=%s ready=%s ang=%s'
        % (last().get('fw'), last().get('up'), last().get('st'), last().get('cl'),
           last().get('ready'), last().get('ang')))
    if last().get('fw') != '20261017.10':
        raise RuntimeError('unexpected fw ' + str(last().get('fw')))

    # speed gear: cycle 'v' until the reported speed matches the requested gear
    want = {0: '0.02', 1: '0.05', 2: '0.10', 3: '0.25', 4: '0.50'}[args.speed_gear]
    for _ in range(6):
        mark = len(notes)
        send('v'); poll(.5)
        got = [t for t in notes[mark:] if t.startswith('speed=')]
        if got:
            say('speed now: ' + got[-1])
            if got[-1].startswith('speed=%s' % want):
                break

    # make sure the current loop is OFF for the voltage-mode E phase
    mark = len(notes)
    send('d'); poll(.5)
    cfg = [t for t in notes[mark:] if t.startswith('curloop=')]
    if cfg:
        say(cfg[-1])
    if not cfg or not cfg[-1].startswith('curloop=0'):
        mark = len(notes)
        send('l'); poll(.5)
        say('l -> ' + ' | '.join(t for t in notes[mark:] if t.startswith('current loop')))

    target, tol = args.target, args.tol
    walk = []
    hit = False
    for i in range(1, args.max_walk + 1):
        f = last()
        ang = int(f['ang'])
        remaining = step(ang, target)
        if abs(remaining) <= tol:
            say('WINDOW REACHED ang=%d (remaining=%+d)' % (ang, remaining))
            hit = True
            break
        cmd = 'R' if remaining > 0 else 'r'
        say('walk %2d: ang=%d remaining=%+d -> %s' % (i, ang, remaining, cmd))
        r = run_move('walk%02d' % i, cmd)
        end = r.get('end', ang)
        if r.get('fault'):
            recover(tag='walk-recover')
            f = last()
            end = int(f['ang'])
            say('walk %2d faulted, resumed at ang=%d' % (i, end))
        walk.append((i, ang, end, end - ang))
        if abs(step(end, target)) <= tol:
            say('WINDOW REACHED by walk %d landing: ang=%d' % (i, end))
            hit = True
            break
    say('walk summary: ' + '; '.join('ang %d -> %d (%+d)' % (a, b, d) for _, a, b, d in walk))
    if not hit:
        raise RuntimeError('window not reached in %d walks' % args.max_walk)

    # ---- E: voltage mode from the window ----
    E = run_move('E-voltage-bad', 'r', timeout=40.0)
    if E.get('fault'):
        recover(tag='after-E')
    else:
        send('s'); poll(.6)

    # ---- D: current loop ON from the window ----
    mark = len(notes)
    send('l'); poll(.6)
    say('l -> ' + ' | '.join(t for t in notes[mark:] if t.startswith('current loop')))
    f = last()
    if abs(step(int(f['ang']), target)) > tol + 12 and not E.get('fault'):
        # E completed a turn and scattered off the window; walk again with loop ON
        say('D: not in window (ang=%s), walking again' % f.get('ang'))
        for i in range(1, args.max_walk + 1):
            f = last()
            ang = int(f['ang'])
            remaining = step(ang, target)
            if abs(remaining) <= tol:
                break
            cmd = 'R' if remaining > 0 else 'r'
            r = run_move('Dwalk%02d' % i, cmd)
            if r.get('fault'):
                recover(tag='dwalk-recover')
            end = int(last().get('ang'))
            if abs(step(end, target)) <= tol:
                break
        f = last()
        say('D start position ang=%s' % f.get('ang'))
    D = run_move('D-loop-bad', 'r', timeout=40.0)
    if D.get('fault'):
        recover(tag='after-D')
    else:
        send('s'); poll(.6)

    # ---- restore defaults: loop OFF, speed 0.05 ----
    mark = len(notes)
    send('l'); poll(.6)
    say('l -> ' + ' | '.join(t for t in notes[mark:] if t.startswith('current loop')))
    for _ in range(4):
        send('v'); poll(.4)
    say('speed restored note: ' + ' | '.join(t for t in notes[-3:] if t.startswith('speed=')))

    send('d'); poll(.7)
    say('final curloop line: ' + ' | '.join(t for t in notes[-4:] if t.startswith('curloop=')))
    oc_dump('END')
    send('s'); poll(.6)
    say('END_STATE %s' % {k: last().get(k) for k in ('st', 'out', 'brk', 'ready', 'cl', 'fault', 'ang')})

say('LOG', log_path)
say('SUMMARY E(voltage)=%s src=%s' % ('FAULT:' + str(E.get('fault')) if E.get('fault') else 'done %+.3f turns' % (E.get('travel', 0) / 16384.0), E.get('start')))
say('SUMMARY D(loop)   =%s src=%s' % ('FAULT:' + str(D.get('fault')) if D.get('fault') else 'done %+.3f turns' % (D.get('travel', 0) / 16384.0), D.get('start')))
raise SystemExit(0)
