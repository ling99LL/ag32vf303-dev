"""FOC2205 unattended SPIN acceptance runner.

Exercises the endless-rotation mode across speed, force and direction while
keeping the firmware's one-second host watchdog fed.  Every run is stopped by
the host, followed by an F read, so a stale over-current capture cannot leak
into the next condition.  A final silent interval verifies that a missing host
causes a bounded ramp-down and output release.

Usage:
  python experiments/tests/spin/accept_spin.py
  python experiments/tests/spin/accept_spin.py --forces 20,40 --speeds V2
"""
import argparse, json, re, statistics, time
from pathlib import Path
import serial


RAW_TURN = 16384
GLITCH_STEP = 1200
FORCE_GEAR = {10: 'W1', 20: 'W2', 30: 'W3', 40: 'W4',
              50: 'W5', 60: 'W6', 70: 'W7', 80: 'W8'}
SPEED_RPS = {'V1': 0.05, 'V2': 0.10, 'V3': 0.25, 'V4': 1.00}
OPENLOOP_POWER_MAX = 40


def step_raw(a, b):
    return (b - a + RAW_TURN // 2) % RAW_TURN - RAW_TURN // 2


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', default='COM26')
    ap.add_argument('--forces', default='20,40,60,80')
    ap.add_argument('--speeds', default='V1,V2,V3,V4')
    ap.add_argument('--directions', default='fwd,rev')
    ap.add_argument('--mode', choices=('closed', 'open'), default='closed',
                    help='SPIN control mode (#0 closed / #1 open)')
    ap.add_argument('--dwell', type=float, default=4.0,
                    help='seconds of powered steady-state sampling per run')
    ap.add_argument('--settle', type=float, default=1.0,
                    help='seconds excluded from steady-state metrics')
    ap.add_argument('--disconnect-only', action='store_true',
                    help='only verify the host-loss stop path')
    ap.add_argument('--tag', default='spin-accept')
    return ap.parse_args()


args = parse_args()
forces = [int(x) for x in args.forces.split(',') if x.strip()]
speeds = [x.strip().upper() for x in args.speeds.split(',') if x.strip()]
directions = [x.strip().lower() for x in args.directions.split(',') if x.strip()]
if any(f not in FORCE_GEAR for f in forces):
    raise SystemExit('force must be one of 10..80 in 10%% steps')
if args.mode == 'open':
    forces = sorted(set(min(f, OPENLOOP_POWER_MAX) for f in forces))
if any(v not in SPEED_RPS for v in speeds):
    raise SystemExit('speed must be V1, V2, V3 or V4')
if any(d not in ('fwd', 'rev') for d in directions):
    raise SystemExit('direction must be fwd or rev')

ROOT = Path(__file__).resolve().parents[3]
LOG_DIR = ROOT / 'experiments' / 'logs' / 'powered-20261017'
LOG_DIR.mkdir(parents=True, exist_ok=True)
STAMP = time.strftime('%H%M%S')
log_path = LOG_DIR / ('%s-%s.txt' % (STAMP, args.tag))
res_path = LOG_DIR / ('%s-%s.json' % (STAMP, args.tag))

frames, notes, oc_lines, records = [], [], [], []
pending = b''
ser = None
log = None


def say(*parts):
    text = ' '.join(str(x) for x in parts)
    print(text, flush=True)
    if log:
        log.write('NOTE ' + text + '\n')
        log.flush()


def send(cmd):
    ser.write(cmd.encode('ascii'))
    ser.flush()
    if log:
        log.write('HOST ' + cmd + '\n')
        log.flush()


def read():
    global pending
    data = ser.read(max(1, ser.in_waiting))
    if not data:
        return
    pending += data
    while b'\n' in pending:
        line, pending = pending.split(b'\n', 1)
        text = line.decode('utf-8', 'replace').rstrip('\r')
        if log:
            log.write(text + '\n')
        if text.startswith('#FOC,'):
            frames.append((time.monotonic(), dict(
                item.split('=', 1) for item in text.split(',')[1:] if '=' in item)))
        elif text.startswith('OC:') or text.startswith('OC snap:'):
            oc_lines.append(text)
        elif text and not text.startswith('isr='):
            notes.append((time.monotonic(), text))
    if log:
        log.flush()


def poll(seconds, interval=.1):
    end = time.monotonic() + seconds
    nxt = 0.0
    while time.monotonic() < end:
        now = time.monotonic()
        if now >= nxt:
            send('?')
            nxt = now + interval
        read()


def last():
    return frames[-1][1] if frames else {}


def wait_for(predicate, timeout, interval=.1):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        poll(interval, interval)
        if predicate(last()):
            return True
    return False


def query(wait=.35):
    global pending
    ser.reset_input_buffer()
    pending = b''
    before = len(frames)
    poll(wait)
    return frames[-1][1] if len(frames) > before else last()


def require_ready():
    frame = query(.5)
    required = ('drvok', 'encok', 'adcok', 'cal', 'ready', 'aligned')
    bad = {k: frame.get(k) for k in required if frame.get(k) != '1'}
    if bad or frame.get('st') != '0' or frame.get('out') != '0' or frame.get('brk') != '0':
        raise RuntimeError('board not ready: %s' % json.dumps(frame, sort_keys=True))
    if frame.get('fw') != '20261017.10':
        raise RuntimeError('unexpected firmware: %s' % frame.get('fw'))
    say('READY fw=%s hz=%s calst=%s calok=%s aligned=%s'
        % (frame.get('fw'), frame.get('hz'), frame.get('calst'),
           frame.get('calok'), frame.get('aligned')))
    return frame


def read_oc():
    global oc_lines
    oc_lines = []
    send('F')
    poll(.45)
    result = {'over': 0, 'maxrun': 0, 'glitch': 0,
              'pk': [0, 0, 0], 'lines': list(oc_lines)}
    for line in oc_lines:
        match = re.search(r'pkA=(-?\d+) pkB=(-?\d+) pkC=(-?\d+) lsb over=(\d+) '
                          r'maxrun=(\d+) glitch=(\d+)', line)
        if match:
            result['pk'] = [int(match.group(i)) for i in range(1, 4)]
            result['over'] = int(match.group(4))
            result['maxrun'] = int(match.group(5))
            result['glitch'] = int(match.group(6))
        if line.startswith('OC snap:'):
            result['snap'] = line
    return result


def stop_and_wait(timeout=5.0):
    send('s')
    ok = wait_for(lambda f: f.get('st') in ('0', '4') and f.get('out') == '0', timeout)
    if not ok:
        send('s')
        ok = wait_for(lambda f: f.get('st') in ('0', '4') and f.get('out') == '0', 2.0)
    poll(.25)
    return ok


def run_spin(force, speed_gear, direction, index):
    rps = SPEED_RPS[speed_gear]
    direction_name = 'forward' if direction > 0 else 'reverse'
    tag = '%02d-%s-W%d-%s' % (index, speed_gear, force, direction_name)
    say('START %s force=%d%% speed=%s %.2f rev/s direction=%s'
        % (tag, force, speed_gear, rps, direction_name))

    send('#1' if args.mode == 'open' else '#0')
    poll(.15)
    send(speed_gear)
    poll(.15)
    send(FORCE_GEAR[force])
    poll(.15)
    pre = last()
    if pre.get('st') != '0' or pre.get('out') != '0':
        raise RuntimeError('%s: not idle before start: %s' % (tag, json.dumps(pre)))

    t_start = time.monotonic()
    send('p' if direction > 0 else 'P')
    if not wait_for(lambda f: f.get('mode') == '2' and f.get('st') == '1' and
                    f.get('out') == '1', 3.0):
        raise RuntimeError('%s: SPIN did not start: %s' % (tag, json.dumps(last())))

    run_frames = []
    end = time.monotonic() + args.dwell
    while time.monotonic() < end:
        poll(.1)
        cur = last()
        if cur.get('st') == '3':
            raise RuntimeError('%s: fault during spin: %s' % (tag, json.dumps(cur)))
        if cur.get('st') != '1' or cur.get('out') != '1':
            raise RuntimeError('%s: output released unexpectedly: %s'
                               % (tag, json.dumps(cur)))
        if int(cur.get('pct', -1)) != force:
            raise RuntimeError('%s: force cap mismatch pct=%s' % (tag, cur.get('pct')))
        if cur.get('cl') != '1':
            if args.mode == 'closed':
                raise RuntimeError('%s: current loop not active: cl=%s'
                                   % (tag, cur.get('cl')))
        if int(cur.get('open', 0)) != (1 if args.mode == 'open' else 0):
            raise RuntimeError('%s: mode mismatch open=%s' % (tag, cur.get('open')))
        run_frames.append((time.monotonic(), dict(cur)))

    stopped = stop_and_wait()
    post = query(.35)
    oc = read_oc()
    post = query(.25)

    rec = {'tag': tag, 'force': force, 'speed_gear': speed_gear,
           'commanded_rps': rps, 'direction': direction_name,
           'started': True, 'stopped': stopped,
           'elapsed_s': round(time.monotonic() - t_start, 2),
           'mode': post.get('mode'), 'st': post.get('st'), 'out': post.get('out'),
           'pct_commanded': force,
           'oc': {k: oc[k] for k in ('over', 'maxrun', 'glitch', 'pk')}}
    if oc.get('snap'):
        rec['oc']['snap'] = oc['snap']

    signed = []
    for _, frame in run_frames:
        try:
            signed.append((int(frame['up']), int(frame['ang']), frame))
        except (KeyError, ValueError):
            pass
    samples = []
    for (up0, ang0, _), (up1, ang1, frame1) in zip(signed, signed[1:]):
        dt_ms = up1 - up0
        if dt_ms <= 20:
            continue
        samples.append({'t_ms': up1, 'dt_ms': dt_ms,
                        'v': step_raw(ang0, ang1) * 1000.0 / dt_ms,
                        'frame': frame1})
    steady = [s for s in samples if s['t_ms'] - signed[0][0] >= args.settle * 1000.0]
    rec['n_samples'] = len(steady)
    if steady:
        ideal = rps * RAW_TURN
        glitch_limit = max(GLITCH_STEP, 2.0 * ideal / 10.0)
        values = [s['v'] for s in steady]
        mean = statistics.mean(values)
        sd = statistics.pstdev(values) if len(values) > 1 else 0.0
        rec.update({
            'rpm_mean': round(mean * 60.0 / RAW_TURN, 3),
            'rpm_error_pct': round(100.0 * (mean - direction * ideal) /
                                   (direction * ideal), 2),
            'cv_pct': round(100.0 * sd / abs(mean), 2) if mean else None,
            'stall_pct': round(100.0 * sum(abs(v) < .3 * ideal for v in values) /
                               len(values), 1),
            'reverse_steps': sum(1 for a, b in zip(values, values[1:])
                                 if abs(a) >= 3 and abs(b) >= 3 and a * b < 0),
            'step100max': round(max(abs(s['v']) / 10.0 for s in steady), 1),
            'glitches': sum(1 for s in steady
                            if abs(s['v']) / 10.0 > glitch_limit),
            'vq_peak': max(abs(int(s['frame'].get('vq', 0))) for s in steady),
            'iq_peak': max(abs(int(s['frame'].get('iq', 0))) for s in steady),
            'iref_peak': max(abs(int(s['frame'].get('iref', 0))) for s in steady),
            'err_peak': max(abs(int(s['frame'].get('err', 0))) for s in steady),
        })
    rec['passed'] = bool(
        rec['stopped'] and rec['n_samples'] >= 8 and post.get('st') in ('0', '4') and
        post.get('out') == '0' and oc['maxrun'] < 3 and
        rec.get('cv_pct') is not None and rec['cv_pct'] <= 15.0 and
        rec.get('stall_pct', 100.0) <= 10.0 and rec.get('reverse_steps', 99) <= 2 and
        rec.get('glitches', 99) == 0 and abs(rec.get('rpm_error_pct', 999)) <= 20.0)
    say('RESULT %s %s rpm=%s err=%s%% cv=%s%% stall=%s%% rev=%s g=%s '
        'vq/iq/iref=%s/%s/%s oc=%s/%s/%s pct=%s st=%s out=%s'
        % (tag, 'PASS' if rec['passed'] else 'FAIL', rec.get('rpm_mean', '-'),
           rec.get('rpm_error_pct', '-'), rec.get('cv_pct', '-'),
           rec.get('stall_pct', '-'), rec.get('reverse_steps', '-'),
           rec.get('glitches', '-'), rec.get('vq_peak', '-'), rec.get('iq_peak', '-'),
           rec.get('iref_peak', '-'), oc['over'], oc['maxrun'], oc['glitch'],
           rec['pct_commanded'], post.get('st'), post.get('out')))
    return rec


def disconnect_test(force=40, speed_gear='V2'):
    say('DISCONNECT start %s W%d, then 3.5 s of host silence' % (speed_gear, force))
    send('#1' if args.mode == 'open' else '#0')
    poll(.15)
    send(speed_gear)
    poll(.15)
    send(FORCE_GEAR[force])
    poll(.15)
    send('p')
    if not wait_for(lambda f: f.get('mode') == '2' and f.get('out') == '1', 3.0):
        raise RuntimeError('disconnect: SPIN did not start')
    poll(.5)
    # The firmware watchdog trips after 1 s and allows up to 2 s for the
    # bounded ramp-down, so sample beyond the worst-case 3 s release time.
    time.sleep(3.5)                       # intentionally send no keepalive
    first = query(.4)
    second = query(.6)
    rec = {'force': force, 'speed_gear': speed_gear,
           'elapsed_after_silence_s': 3.5 + 0.4 + 0.6,
           'first': {k: first.get(k) for k in ('mode', 'st', 'out', 'pct', 'fault')},
           'second': {k: second.get(k) for k in ('mode', 'st', 'out', 'pct', 'fault')}}
    rec['passed'] = bool(first.get('out') == '0' and second.get('out') == '0' and
                         second.get('st') in ('0', '4') and
                         second.get('mode') == '0')
    say('DISCONNECT %s first=%s second=%s'
        % ('PASS' if rec['passed'] else 'FAIL', rec['first'], rec['second']))
    return rec


def main():
    global ser, log
    with serial.Serial(args.port, 115200, timeout=.02, write_timeout=.5) as port, \
            log_path.open('w', encoding='utf-8') as handle:
        ser, log = port, handle
        try:
            send('s')
            poll(.8)
            require_ready()
            if args.disconnect_only:
                disconnect = disconnect_test()
            else:
                index = 0
                for force in forces:
                    for speed_gear in speeds:
                        for direction, name in ((1, 'fwd'), (-1, 'rev')):
                            if name not in directions:
                                continue
                            index += 1
                            rec = run_spin(force, speed_gear, direction, index)
                            records.append(rec)
                            if not rec['passed']:
                                raise RuntimeError('%s failed acceptance; stopping sweep' % rec['tag'])
                disconnect = disconnect_test()
        except Exception as exc:
            say('ABORT', exc)
            try:
                send('s')
                poll(1.0)
            except Exception:
                pass
            disconnect = None
            failure = str(exc)
        else:
            failure = None
        finally:
            try:
                send('s')
                poll(.5)
            except Exception:
                pass

    summary = {'log': str(log_path), 'args': vars(args), 'records': records,
               'disconnect': disconnect, 'failure': failure}
    res_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding='utf-8')
    print('LOG', log_path)
    print('JSON', res_path)
    print('SUMMARY passed=%d failed=%d disconnect=%s' % (
        sum(r['passed'] for r in records), sum(not r['passed'] for r in records),
        'PASS' if disconnect and disconnect['passed'] else 'FAIL' if disconnect else 'SKIP'))
    return 0 if failure is None and disconnect and disconnect['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
