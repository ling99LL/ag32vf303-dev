"""FOC2205 2026-10-17: current-loop + over-current-telemetry acceptance.

Matrix (every move is +1 turn at the configured speed, vq_max from `d`):
  A voltage-good : current loop OFF, start from a known-good angle
  B loop-good    : current loop ON,  next turn from the same area
  C converge     : manual-mode jog convergence onto the 2026-10-16 bad start
                   window (ang 7370..7386, 8/8 starts tripped there on .7)
  D loop-bad     : current loop ON,  start from the bad window
  E voltage-bad  : current loop OFF, start from the bad window

Decisive question for the new telemetry: from the bad window, does the
"3 consecutive samples over threshold" rule fire (real over-current: the `F`
snapshot then holds the run), or does the turn complete with only isolated
glitches counted (sampling artifact)?  The old single-sample rule tripped
8/8 starts from that window.

Run:  python experiments/tests/current_loop/accept_current_loop.py
"""
import argparse, statistics, sys, time
from pathlib import Path
import serial

GLITCH = 1200  # per-100ms step above this = encoder glitch (force-sweep rule)

ap = argparse.ArgumentParser()
ap.add_argument('--port', default='COM26')
ap.add_argument('--window', type=int, default=7378, help='bad-window center')
ap.add_argument('--tol', type=int, default=6)
args = ap.parse_args()

ROOT = Path(__file__).resolve().parents[3]
LOG = ROOT / 'experiments' / 'logs' / 'powered-20261017'
LOG.mkdir(parents=True, exist_ok=True)
log_path = LOG / (time.strftime('%H%M%S-') + 'currentloop-accept.txt')

frames, notes = [], []


def frame_of(text):
    if text.startswith('#FOC,'):
        return dict(v.split('=', 1) for v in text.split(',')[1:] if '=' in v)
    return None


def step(a, b):
    return (b - a + 8192) % 16384 - 8192


with serial.Serial(args.port, 115200, timeout=.02, write_timeout=.5) as ser, \
        log_path.open('w', encoding='utf-8') as log:
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
                notes.append(text); print(text, flush=True)

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

    def note_since(mark):
        return notes[mark:]

    def oc_read(tag):
        mark = len(notes)
        send('F'); poll(.7)
        lines = note_since(mark)
        print('OC[%s]: %s' % (tag, ' | '.join(lines) or 'no reply'), flush=True)
        return lines

    def dump_cfg(tag):
        mark = len(notes)
        send('d'); poll(.7)
        lines = [t for t in note_since(mark) if t.startswith(('cfg:', 'hybrid:', 'curloop='))]
        print('[%s]' % tag, flush=True)
        for t in lines:
            print('    ' + t, flush=True)
        return lines

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
                print('%s: ok (st=0 out=0 ready=1)' % tag, flush=True)
                return True
        print('%s: FAILED state=%s' % (tag, {k: last().get(k) for k in
              ('st', 'out', 'ready', 'fault')}), flush=True)
        return False

    def calibrate(timeout=60.0):
        send('s'); poll(.8)
        f = last()
        for key in ('drvok', 'encok', 'adcok', 'cal'):
            if f.get(key) != '1':
                raise RuntimeError('calibration prereq %s=%s' % (key, f.get(key)))
        print('START calst=%s ready=%s aligned=%s calpk=%s'
              % (f.get('calst'), f.get('ready'), f.get('aligned'), f.get('calpk')),
              flush=True)
        send('a')
        seen = False
        prev = None
        t0 = time.monotonic()
        while time.monotonic() - t0 < timeout:
            poll(.4)
            f = last()
            if f.get('calst') in ('1', '2', '3', '4', '5', '6'):
                seen = True
            cur = (f.get('calst'), f.get('ready'), f.get('aligned'),
                   f.get('calpk'), f.get('fault'))
            if cur != prev:
                print('%7.2f calst=%s ready=%s aligned=%s calpk=%s fault=%s'
                      % (time.monotonic() - t0, *cur), flush=True)
                prev = cur
            if f.get('calst') in ('7', '9') or (seen and f.get('calst') == '8'):
                break
        send('s'); poll(.6)
        f = last()
        print('CALIBRATION result calst=%s ready=%s aligned=%s calpk=%s'
              % (f.get('calst'), f.get('ready'), f.get('aligned'), f.get('calpk')),
              flush=True)
        return f.get('calst') == '7' and f.get('ready') == '1'

    def move(tag, timeout=75.0):
        send('s'); poll(.5)
        f0 = last()
        if f0.get('st') != '0' or f0.get('out') != '0':
            raise RuntimeError('%s: not idle before start: %s'
                               % (tag, {k: f0.get(k) for k in ('st', 'out')}))
        start_ang = int(f0.get('ang'))
        print('=== %s: start ang=%d cl=%s iref=%s ==='
              % (tag, start_ang, f0.get('cl'), f0.get('iref')), flush=True)
        mark = len(notes)
        send('r'); poll(.3)
        for t in note_since(mark):
            if 'busy' in t or 'fault latched' in t:
                raise RuntimeError('%s: move refused: %s' % (tag, t))
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
        res = dict(tag=tag, start_ang=start_ang, done=done, fault=None,
                   frames=len(active))
        if fault:
            print('    FAULT at t=%s ms: %s' % (fault.get('t'), fault.get('fault')),
                  flush=True)
            for f in frames[-4:]:
                print('      up=%s ang=%s ia=%s ib=%s ic=%s vq=%s id=%s iq=%s '
                      'ocn=%s ocmx=%s ocg=%s'
                      % (f.get('up'), f.get('ang'), f.get('ia'), f.get('ib'), f.get('ic'),
                         f.get('vq'), f.get('id'), f.get('iq'), f.get('ocn'), f.get('ocmx'),
                         f.get('ocg')), flush=True)
            res['fault'] = fault.get('fault')
        elif done and active:
            angs = [int(active[0]['ang'])]
            steps, glitches = [], 0
            for prev, cur in zip(active, active[1:]):
                d = step(int(prev['ang']), int(cur['ang']))
                if abs(d) > GLITCH:
                    glitches += 1
                    continue
                steps.append(d); angs.append(angs[-1] + d)
            travel = angs[-1] - angs[0]
            dt = (int(active[-1]['up']) - int(active[0]['up'])) / 1000.0
            errs = [abs(int(f['err'])) for f in active]
            vqs = [abs(int(f['vq'])) for f in active]
            iqs = [int(f['iq']) for f in active]
            ids = [int(f['id']) for f in active]
            iref = int(active[-1].get('iref') or '0')
            ideal = 819 // 10
            dev = [abs(s - ideal) / float(ideal) for s in steps] if steps else [0.0]
            res.update(
                travel=travel / 16384.0, rpm=travel * 60 / 16384.0 / dt if dt else 0,
                peak_err=max(errs) if errs else 0, peak_vq=max(vqs) if vqs else 0,
                iq_min=min(iqs) if iqs else 0, iq_max=max(iqs) if iqs else 0,
                iq_mean=statistics.fmean(iqs) if iqs else 0,
                id_min=min(ids) if ids else 0, id_max=max(ids) if ids else 0,
                iref=iref, step_std=statistics.pstdev(steps) if len(steps) > 1 else 0,
                dev_mean=statistics.fmean(dev), glitches=glitches,
                final=active[-1])
            print('    DONE travel=%+.3f turns  %.2f rpm  peak_err=%d  peak_vq=%d  '
                  'iq[%.0f..%.0f] mean=%.1f (iref=%d)  id[%d..%d]  step_std=%.1f  '
                  '|dev| mean=%.0f%%  glitch=%d  ocn=%s ocmx=%s ocg=%s'
                  % (res['travel'], res['rpm'], res['peak_err'], res['peak_vq'],
                     res['iq_min'], res['iq_max'], res['iq_mean'], res['iref'],
                     res['id_min'], res['id_max'], res['step_std'],
                     100 * res['dev_mean'], glitches, active[-1].get('ocn'),
                     active[-1].get('ocmx'), active[-1].get('ocg')), flush=True)
        else:
            print('    INCOMPLETE (no DONE, no FAULT; started=%s frames=%d)'
                  % (started, len(active)), flush=True)
        oc_read(tag)
        return res

    def jog(mask, gear, hold):
        send('s'); poll(.4)
        before = last()
        if before.get('st') != '0':
            if not recover(tag='jog-pre'):
                raise RuntimeError('jog: cannot reach idle')
            before = last()
        a0 = int(before['ang'])
        send('m'); poll(.3)
        send('w%d' % gear); poll(.3)
        send('x%d' % mask); poll(hold)
        send('s'); poll(.8)
        after = last()
        if after.get('st') == '3':
            print('    jog faulted: %s -> recovering' % after.get('fault'), flush=True)
            recover(tag='jog-recover')
            return None
        a1 = int(after['ang'])
        return step(a0, a1)

    def converge(target, tol, max_jogs=20):
        mask_dir = {1: 1, 4: -1}   # assumes mask 1 moves +raw on this rig
        overshoots = 0
        boost = 1.0
        best = None
        for i in range(1, max_jogs + 1):
            f = last()
            ang = int(f['ang'])
            remaining = step(ang, target)
            if best is None or abs(remaining) < abs(best[1]):
                best = (ang, remaining, i)
            print('  jog %2d: ang=%d remaining=%+d' % (i, ang, remaining), flush=True)
            if abs(remaining) <= tol:
                print('  converged ang=%d (target %d +-%d)' % (ang, target, tol),
                      flush=True)
                return ang
            want = 1 if remaining > 0 else -1
            cands = [m for m, s in mask_dir.items() if s == want]
            if not cands:
                cands = [4 if want < 0 else 1]
            mask = cands[0]
            gear = 2 if abs(remaining) > 400 else 1
            scale = 4830.0 if gear == 2 else 2400.0
            hold = abs(remaining) / scale * 1.5 * (0.7 ** overshoots) * boost
            hold = max(.12, min(2.0, hold))
            d = jog(mask, gear, hold)
            if d is None:
                continue
            print('        jog mask=%d gear=%d hold=%.2f -> %+d' % (mask, gear, hold, d),
                  flush=True)
            if d == 0:
                boost = min(boost * 1.6, 4.0)
                continue
            obs = 1 if d > 0 else -1
            if obs != mask_dir.get(mask, obs):
                other = 4 if mask == 1 else 1
                mask_dir[other], mask_dir[mask] = mask_dir[mask], mask_dir[other]
                print('        direction map swapped: %s' % mask_dir, flush=True)
            if obs * want < 0:
                overshoots = min(overshoots + 1, 6)
        if best and abs(best[1]) <= 20:
            print('  converge fallback: best ang=%d remaining=%+d (jog %d)'
                  % best, flush=True)
            return best[0]
        raise RuntimeError('converge failed: best=%s target=%d' % (best, target))

    # ---------------- run ----------------
    send('s'); poll(1.0)
    if not frames:
        raise RuntimeError('no status frames on %s' % args.port)
    print('P0 fw=%s up=%s st=%s ready=%s' % (last().get('fw'), last().get('up'),
                                             last().get('st'), last().get('ready')),
          flush=True)
    if last().get('fw') != '20261017.10':
        raise RuntimeError('unexpected firmware: %s' % last().get('fw'))
    dump_cfg('P0 cfg')
    oc_read('P0 clear')

    if last().get('ready') != '1':
        if not calibrate():
            raise RuntimeError('calibration failed')

    results = {}
    # A: voltage mode from the current (good) position
    results['A'] = move('A-voltage-good')
    # B: current loop ON, next turn
    mark = len(notes)
    send('l'); poll(.5)
    print('L ON: %s' % (' | '.join(note_since(mark)) or 'no reply'), flush=True)
    results['B'] = move('B-loop-good')
    if results['B']['fault'] or not results['B']['done']:
        recover(tag='after-B')

    # C: converge onto the bad window
    converge(args.window, args.tol)

    # D: current loop ON from the bad window (the decisive test)
    results['D'] = move('D-loop-bad', timeout=90.0)
    if results['D']['fault']:
        if not recover(tag='after-D'):
            raise RuntimeError('cannot recover after D')
    else:
        send('s'); poll(.8)

    # E: voltage mode from the bad window
    mark = len(notes)
    send('l'); poll(.5)
    print('L OFF: %s' % (' | '.join(note_since(mark)) or 'no reply'), flush=True)
    f = last()
    if abs(step(int(f['ang']), args.window)) > args.tol:
        converge(args.window, args.tol)
    results['E'] = move('E-voltage-bad', timeout=90.0)
    if results['E']['fault']:
        recover(tag='after-E')

    # end state
    dump_cfg('END cfg')
    oc_read('END')
    send('s'); poll(.8)
    end = last()
    print('END_STATE', {k: end.get(k) for k in
          ('st', 'out', 'brk', 'ready', 'aligned', 'cl', 'fault')}, flush=True)

print('LOG', log_path)
print('%-16s %-8s %-9s %-9s %-8s %-8s %s' %
      ('phase', 'result', 'turns', 'rpm', 'peak_vq', 'glitch', 'notes'))
for k in ('A', 'B', 'D', 'E'):
    r = results.get(k, {})
    if r.get('fault'):
        print('%-16s %-8s %-9s %-9s %-8s %-8s FAULT: %s' %
              (k, 'FAULT', '-', '-', '-', '-', r['fault']))
    elif r.get('done'):
        print('%-16s %-8s %-9.3f %-9.2f %-8d %-8d iq mean=%.1f iref=%d step_std=%.1f' %
              (k, 'DONE', r['travel'], r['rpm'], r['peak_vq'], r['glitches'],
               r['iq_mean'], r['iref'], r['step_std']))
    else:
        print('%-16s %-8s (incomplete)' % (k, 'NONE'))
raise SystemExit(0 if all(results.get(k, {}).get('done') or results.get(k, {}).get('fault')
                          for k in ('A', 'B', 'D', 'E')) else 1)
