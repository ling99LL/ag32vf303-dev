"""FOC2205 force sweep: one closed-loop turn at each modulation limit.

Usage: python experiments/tests/force_sweep/accept_force_sweep.py --pcts 5,10,15,20

For each percentage the runner writes `g_motion_cfg.vq_max` exactly through the
debug probe (`set_vqmax.bat`, which also cross-checks the struct offsets against
the live `d` dump), runs one `r` turn and reports how evenly the rotor moved:
per-sample encoder step min/max/std, peak position error, peak modulation and
the firmware's own velocity-jitter line. vq_max is restored at the end.

Note: `cap_vq()` clamps vq_max to `MOTION_POWER_PCT_MAX` = 20% of v_limit_q
(1638/8192), so percentages above 20 need a firmware rebuild.
"""
import argparse, json, statistics, subprocess, time
from pathlib import Path
import serial

GLITCH = 1200

p = argparse.ArgumentParser()
p.add_argument('--pcts', default='5,10,15,20')
p.add_argument('--direction', choices=['fwd', 'rev'], default='fwd')
p.add_argument('--port', default='COM26')
p.add_argument('--tag', default='force-sweep')
p.add_argument('--retries', type=int, default=1,
               help='extra attempts per level after a fault/incomplete turn')
args = p.parse_args()

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
LOG = ROOT / 'experiments' / 'logs' / 'powered-20261016'
LOG.mkdir(parents=True, exist_ok=True)
log_path = LOG / (time.strftime('%H%M%S-') + args.tag + '.txt')
notes, frames = [], []

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
                f = dict(v.split('=', 1) for v in text.split(',')[1:] if '=' in v)
                if all(k in f for k in ('ang', 'up', 'out', 'brk', 'st', 'err', 'vq')):
                    frames.append(f)
            elif text:
                notes.append(text); print(text, flush=True)

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
        send('d'); poll(.4)
        for t in notes[before:]:
            if t.startswith('cfg:'):
                return int(t.split('vq_max=')[1].split()[0])
        return None

    def set_vq(target):
        out = subprocess.run(['cmd.exe', '/c', str(HERE / 'set_vqmax.bat'), str(target)],
                             cwd=ROOT, capture_output=True, timeout=60)
        text = out.stdout.decode('utf-8', 'replace')
        for line in text.splitlines():
            if line.strip():
                log.write('    | ' + line + '\n')
        log.flush()
        for line in text.splitlines():
            if line.startswith('SET '):
                print('    ' + line.strip(), flush=True)
        live = dump_vq()
        if live != target:
            raise RuntimeError('vq_max set failed: probe target %d, firmware reports %s'
                               % (target, live))
        return live

    send('s'); poll(.8)
    base = frames[-1]
    for key in ('drvok', 'encok', 'adcok', 'cal', 'ready', 'aligned'):
        if base.get(key) != '1':
            raise RuntimeError('Prerequisite failed: %s=%s' % (key, base.get(key)))
    if base.get('st') != '0' or base.get('out') != '0' or base.get('brk') != '0':
        raise RuntimeError('Not idle/healthy: ' + json.dumps(base))
    original = dump_vq()
    print('ORIGINAL vq_max=%d (%.2f%%)' % (original, 100.0 * original / 8192), flush=True)

    def healthy():
        return (frames and frames[-1].get('st') == '0'
                and frames[-1].get('out') == '0' and frames[-1].get('ready') == '1')

    def recover(timeout=8.0):
        send('z')
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            poll(.4)
            if healthy():
                return True
        return False

    cmd = 'r' if args.direction == 'fwd' else 'R'
    rows = []
    try:
        for pct in [float(x) for x in args.pcts.split(',')]:
            target = int(round(8192 * pct / 100.0))
            print('=== %g%% -> vq_max=%d' % (pct, target), flush=True)
            live = set_vq(target)
            if not healthy():
                print('    not idle before start -> recover', flush=True)
                if not recover():
                    raise RuntimeError('Board not idle before %g%%' % pct)
            row, faults = None, []
            for attempt in range(1, args.retries + 2):
                cursor = len(frames) + 1
                send(cmd)
                active, started, done, fault = [], False, False, None
                t0 = time.monotonic()
                while time.monotonic() - t0 < 70.0:
                    poll(.2)
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
                if done and active:
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
                    errs = [int(f['err']) for f in active]
                    vqs = [abs(int(f['vq'])) for f in active]
                    ideal = 819 // 10 * (1 if args.direction == 'fwd' else -1)
                    dev = [abs(s - ideal) / float(abs(ideal)) for s in steps] if steps else [0]
                    row = dict(
                        pct=pct, vq_max=live, travel_turns=travel / 16384.0,
                        seconds=dt, rpm=travel * 60 / 16384.0 / dt if dt else 0.0,
                        peak_err=max(abs(e) for e in errs), final_err=errs[-1],
                        peak_vq=max(vqs), mean_vq=sum(vqs) / len(vqs),
                        step_min=min(steps), step_max=max(steps),
                        step_std=statistics.pstdev(steps) if len(steps) > 1 else 0.0,
                        step_dev_max=max(dev), step_dev_mean=sum(dev) / len(dev),
                        glitches=glitches, samples=len(active), attempt=attempt,
                        notes='; '.join(faults) if faults else '')
                    print('    travel=%+.3f turns  %.2f rpm  peak_err=%d  peak_vq=%d(mean %.0f)  '
                          'step min/max/std=%d/%d/%.1f  |dev| mean=%.1f%% max=%.0f%%  glitch=%d%s'
                          % (row['travel_turns'], row['rpm'], row['peak_err'], row['peak_vq'],
                             row['mean_vq'], row['step_min'], row['step_max'], row['step_std'],
                             100 * row['step_dev_mean'], 100 * row['step_dev_max'], row['glitches'],
                             ('  [%s]' % row['notes']) if faults else ''),
                          flush=True)
                    break
                if fault:
                    faults.append('attempt %d: fault t=%s ms vel=%s (%s)'
                                  % (attempt, fault.get('t'), fault.get('vel'), fault.get('fault')))
                    print('    attempt %d/%d: FAULT at t=%s ms: %s'
                          % (attempt, args.retries + 1, fault.get('t'), fault.get('fault')),
                          flush=True)
                else:
                    faults.append('attempt %d: incomplete (no DONE)' % attempt)
                    print('    attempt %d/%d: incomplete turn (no DONE)'
                          % (attempt, args.retries + 1), flush=True)
                if attempt <= args.retries:
                    ok = recover()
                    print('    recover: %s' % ('ok' if ok else 'FAILED'), flush=True)
                    if not ok:
                        raise RuntimeError('Recovery failed after %g%% fault' % pct)
            if row is None:
                row = dict(pct=pct, vq_max=live, failed=True, notes='; '.join(faults))
            rows.append(row)
    finally:
        send('s'); poll(.6)
        if original:
            set_vq(original)

print('LOG', log_path)
print('%-6s %-8s %-9s %-9s %-9s %-9s %-9s %-8s %s' % (
    'pct', 'vq_max', 'turns', 'rpm', 'pk_err', 'pk_vq', 'step_std', 'dev_max%', 'notes'))
for r in rows:
    if r.get('failed'):
        print('%-6g %-8d %-9s %-9s %-9s %-9s %-9s %-8s FAULTED  %s' % (
            r['pct'], r['vq_max'], '-', '-', '-', '-', '-', '-', r.get('notes', '')))
    else:
        print('%-6g %-8d %-9.3f %-9.2f %-9d %-9d %-9.1f %-8.0f %s' % (
            r['pct'], r['vq_max'], r['travel_turns'], r['rpm'], r['peak_err'],
            r['peak_vq'], r['step_std'], 100 * r['step_dev_max'], r.get('notes', '')))
print('END_STATE', json.dumps({k: frames[-1].get(k) for k in ['st', 'out', 'brk', 'fault']}))
raise SystemExit(0 if rows and all(not r.get('failed') for r in rows) else 1)
