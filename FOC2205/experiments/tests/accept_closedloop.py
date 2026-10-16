"""FOC2205 closed-loop (position servo) acceptance runner.

Usage: python experiments/tests/accept_closedloop.py --turns 1 --direction fwd

Chains N one-turn `r`/`R` closed-loop moves at the board's current speed gear,
polling the v2 status frame at 10 Hz. Reports, per turn: encoder travel inside
the MOE-active window, wall time, peak |error| and |vq|, the worst reverse step
and any encoder glitch, plus the final state after release.

The runner never changes gains or speed; it records the live config with `d`
so the result stays attributable to a known setup.
"""
import argparse, json, time
from pathlib import Path
import serial

GLITCH = 1200   # raw counts; 1200/16384 turn = 26 deg mech between samples

p = argparse.ArgumentParser()
p.add_argument('--turns', type=int, default=1)
p.add_argument('--direction', choices=['fwd', 'rev'], default='fwd')
p.add_argument('--port', default='COM26')
p.add_argument('--margin', type=float, default=10.0)   # extra seconds per turn
p.add_argument('--tag', default='closedloop')
args = p.parse_args()

LOG = Path(__file__).resolve().parents[1] / 'logs' / 'powered-20261016'
LOG.mkdir(parents=True, exist_ok=True)
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
                if any(k not in f for k in ['ang', 'up', 'out', 'brk', 'st', 'err']):
                    print('INCOMPLETE_FRAME', text, flush=True); continue
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

    def dump_cfg():
        before = len(notes)
        send('d'); poll(.4)
        return [t for t in notes[before:] if t.startswith('cfg:') or t.startswith('hybrid=')]

    def step(a, b):
        return (b - a + 8192) % 16384 - 8192

    sign = 1 if args.direction == 'fwd' else -1

    def unwrap(fr):
        """Accumulate the encoder angle, counting glitches and the worst step
        that goes *against* the commanded direction (the reverse-pull check)."""
        ang, glitches, back = [int(fr[0]['ang'])], 0, 0
        for prev, cur in zip(fr, fr[1:]):
            d = step(int(prev['ang']), int(cur['ang']))
            if abs(d) > GLITCH:
                glitches += 1
                continue
            ang.append(ang[-1] + d)
            if d * sign < 0 and abs(d) > abs(back):
                back = d
        return ang, glitches, back

    try:
        send('s'); poll(.8)
        if not frames:
            raise RuntimeError('No status frames')
        f = frames[-1]
        for key in ['drvok', 'encok', 'adcok', 'cal', 'ready', 'aligned']:
            if f.get(key) != '1':
                raise RuntimeError('Prerequisite failed: %s=%s' % (key, f.get(key)))
        if f.get('st') != '0' or f.get('out') != '0' or f.get('brk') != '0':
            raise RuntimeError('Not in healthy no-output idle: ' + json.dumps(f))

        print('CFG ' + ' | '.join(dump_cfg()), flush=True)
        cmd = 'r' if args.direction == 'fwd' else 'R'
        results = []
        for turn in range(1, args.turns + 1):
            before = frames[-1]
            send(cmd)
            cursor = len(frames) + 1      # skip the first frame after the command
            active, started, done = [], False, False
            t0 = time.monotonic()
            budget = 40.0 + args.margin * 3.0
            while time.monotonic() - t0 < budget:
                poll(.2)
                while cursor < len(frames):
                    f = frames[cursor]; cursor += 1
                    if f.get('st') == '1':
                        started = True
                    if f.get('out') == '1':
                        active.append(f)
                    if f.get('st') == '3':
                        raise RuntimeError('Device fault: ' + json.dumps(f))
                    if started and f.get('st') in ('4', '0') and f.get('out') == '0':
                        done = True
                        break
                if done:
                    break
            if not done:
                raise RuntimeError('Turn %d incomplete' % turn)
            if not active:
                raise RuntimeError('Turn %d had no active frames' % turn)
            ang, glitches, back = unwrap(active)
            dt = (int(active[-1]['up']) - int(active[0]['up'])) / 1000.0
            travel = ang[-1] - ang[0]
            errs = [abs(int(x['err'])) for x in active]
            vqs = [abs(int(x['vq'])) for x in active]
            r = dict(turn=turn, travel_counts=travel, travel_turns=travel / 16384.0,
                     seconds=dt, rpm=travel * 60 / 16384.0 / dt if dt else 0.0,
                     peak_err=max(errs), final_err=int(active[-1]['err']),
                     peak_vq=max(vqs), backstep=back, glitches=glitches,
                     frames=len(active))
            results.append(r)
            print('TURN %d travel=%+.3f turns (%.1f s, %.2f rpm) peak_err=%d '
                  'final_err=%d peak_vq=%d backstep=%d glitches=%d' % (
                      turn, r['travel_turns'], dt, r['rpm'], r['peak_err'],
                      r['final_err'], r['peak_vq'], r['backstep'], r['glitches']),
                  flush=True)
    finally:
        send('s'); poll(.6)

total = sum(r['travel_turns'] for r in results) if results else 0.0
print('LOG', log_path)
print('TURNS_OK', len(results), 'TOTAL_TURNS %+.3f' % total)
print('END_STATE', json.dumps({k: frames[-1].get(k) for k in
                               ['st', 'out', 'brk', 'fault', 'ang', 'err']}))
raise SystemExit(0 if len(results) == args.turns else 1)
