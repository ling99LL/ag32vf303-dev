"""FOC2205 calibration runner.

Usage: python experiments/tests/calibrate.py [--port COM26] [--timeout 45]

Issues 's' (release), then 'a' (start slow calibration) and polls '?' until
`calst` reaches 7 (success) or 9 (failure). Polling also feeds the firmware's
calibration link watchdog, which aborts the run if the host goes quiet for
more than five seconds. Prints every stage transition and the final state.
"""
import argparse, time
from pathlib import Path
import serial

p = argparse.ArgumentParser()
p.add_argument('--port', default='COM26')
p.add_argument('--timeout', type=float, default=45.0)
p.add_argument('--tag', default='calibrate')
args = p.parse_args()

LOG = Path(__file__).resolve().parents[1] / 'logs' / 'powered-20261016'
LOG.mkdir(parents=True, exist_ok=True)
log_path = LOG / (time.strftime('%H%M%S-') + args.tag + '.txt')
frames = []

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
                if any(k not in f for k in ['ang', 'calst', 'ready', 'aligned']):
                    print('INCOMPLETE_FRAME', text, flush=True); continue
                frames.append(f); got.append(f)
            elif text:
                print(text, flush=True)
        return got

    def poll(seconds, interval=.2):
        end = time.monotonic() + seconds
        nxt = 0
        while time.monotonic() < end:
            now = time.monotonic()
            if now >= nxt:
                send('?'); nxt = now + interval
            read()

    try:
        send('s'); poll(.8)
        if not frames:
            raise RuntimeError('No status frames')
        f = frames[-1]
        for key in ['drvok', 'encok', 'adcok', 'cal', 'brk']:
            if f.get(key) != '1' and not (key == 'brk' and f.get(key) == '0'):
                raise RuntimeError('Prerequisite failed: %s=%s' % (key, f.get(key)))
        print('START calst=%s ready=%s aligned=%s calpk=%s' % (
            f['calst'], f['ready'], f['aligned'], f['calpk']), flush=True)

        send('a')
        last = None
        seen_active = False
        t0 = time.monotonic()
        while time.monotonic() - t0 < args.timeout:
            poll(.4)
            if not frames:
                continue
            f = frames[-1]
            if f['calst'] in ('1', '2', '3', '4', '5', '6'):
                seen_active = True
            cur = (f['calst'], f['ready'], f['aligned'], f['calpk'], f['fault'])
            if cur != last:
                print('%7.2f calst=%s ready=%s aligned=%s calpk=%s fault=%s' % (
                    time.monotonic() - t0, *cur), flush=True)
                last = cur
            if f['calst'] in ('7', '9') or (seen_active and f['calst'] == '8'):
                break
    finally:
        send('s'); poll(.6)

f = frames[-1] if frames else {}
print('LOG', log_path)
print('RESULT calst=%s ready=%s aligned=%s calpk=%s' % (
    f.get('calst'), f.get('ready'), f.get('aligned'), f.get('calpk')))
print('END_STATE', {k: f.get(k) for k in ['st', 'out', 'brk', 'fault', 'ang', 'calok']})
raise SystemExit(0 if f.get('calst') == '7' else 1)
