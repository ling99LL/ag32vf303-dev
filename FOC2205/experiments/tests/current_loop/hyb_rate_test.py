"""FOC2205: does hybrid commutation push the 20 kHz control ISR over budget?

2026-10-17 night measurement: idle ISR rate is 20.02 kHz (real, host-timed),
but during a 1-turn move at 0.05 rev/s the device only counts ~2.8 k ISRs
per 250 ms (~11.2 kHz) and the real move time is ~34.8 s instead of 20.05 s.
Last night's hyb=0 (badpos) moves were host-timed at 20.17 s.

This script flips ONLY the hybrid switch on the accept config and host-times
one turn per case, while logging the per-250ms ISR count so the actual
control-loop rate during the move can be compared directly.

  case hyb0-loopON / hyb0-loopOFF / hyb1-loopOFF   (0.05 rev/s, vq_max 2048)

Run: python experiments/tests/current_loop/hyb_rate_test.py
"""
import argparse, re, statistics, time
from pathlib import Path
import serial

ap = argparse.ArgumentParser()
ap.add_argument('--port', default='COM26')
args = ap.parse_args()

ROOT = Path(__file__).resolve().parents[3]
LOG = ROOT / 'experiments' / 'logs' / 'powered-20261017'
LOG.mkdir(parents=True, exist_ok=True)
log_path = LOG / (time.strftime('%H%M%S-') + 'hyb-rate-test.txt')

frames, isrs, notes = [], [], []
pending = b''


def main():
    global pending
    with serial.Serial(args.port, 115200, timeout=.02, write_timeout=.5) as ser, \
            log_path.open('w', encoding='utf-8') as log:
        def say(*a):
            t = ' '.join(str(x) for x in a)
            print(t, flush=True)
            log.write('NOTE ' + t + '\n'); log.flush()

        def send(cmd):
            ser.write(cmd.encode('ascii')); ser.flush()
            log.write('HOST ' + cmd + '\n'); log.flush()

        def read():
            global pending
            pending += ser.read(max(1, ser.in_waiting))
            while b'\n' in pending:
                line, pending = pending.split(b'\n', 1)
                s = line.decode('utf-8', 'replace').rstrip('\r')
                log.write(s + '\n')
                if s.startswith('#FOC,'):
                    frames.append((time.monotonic(), dict(
                        v.split('=', 1) for v in s.split(',')[1:] if '=' in v)))
                elif s.startswith('isr='):
                    d = dict(v.split('=', 1) for v in s.split() if '=' in v)
                    try:
                        isrs.append((time.monotonic(), int(d['isr'])))
                    except (KeyError, ValueError):
                        pass
                elif s:
                    notes.append((time.monotonic(), s))
            log.flush()

        def poll(seconds, interval=.1):
            end = time.monotonic() + seconds
            nxt = 0.0
            while time.monotonic() < end:
                now = time.monotonic()
                if now >= nxt:
                    send('?'); nxt = now + interval
                read()

        def last():
            return frames[-1][1] if frames else {}

        def healthy():
            f = last()
            return f.get('st') == '0' and f.get('out') == '0' and f.get('ready') == '1'

        def recover(tag, timeout=12.0):
            send('s'); poll(.5)
            if healthy():
                return True
            send('z')
            end = time.monotonic() + timeout
            while time.monotonic() < end:
                poll(.5)
                if healthy():
                    say(tag, 'recovered')
                    return True
            say(tag, 'RECOVER FAILED', {k: last().get(k) for k in
                                         ('st', 'out', 'fault')})
            return False

        def dump():
            mark = len(notes)
            send('d'); poll(.5)
            cfg, cl = {}, {}
            for _, t in notes[mark:]:
                if t.startswith(('cfg:', 'hybrid=')):
                    for tok in t.split():
                        if '=' in tok and not tok.startswith(('ref=', 'elec_deg')):
                            k, _, v = tok.partition('=')
                            cfg.setdefault(k, v)
                elif t.startswith('curloop='):
                    for tok in t.split():
                        if '=' in tok:
                            k, _, v = tok.partition('=')
                            cl.setdefault(k, v)
            return cfg, cl

        def set_hyb(want):
            for _ in range(4):
                if dump()[0].get('hybrid') == str(want):
                    return True
                send('y'); poll(.35)
            return dump()[0].get('hybrid') == str(want)

        def set_loop(on):
            if dump()[1].get('curloop') == ('1' if on else '0'):
                return True
            send('l'); poll(.6)
            return dump()[1].get('curloop') == ('1' if on else '0')

        def set_speed(want):
            for _ in range(6):
                if dump()[0].get('speed') == want:
                    return True
                send('v'); poll(.35)
            return dump()[0].get('speed') == want

        def run_case(tag, hyb, loop):
            set_speed('0.05')
            set_hyb(hyb)
            set_loop(loop)
            cfg, cl = dump()
            say('CASE %s start cfg speed=%s vq=%s hybrid=%s curloop=%s'
                % (tag, cfg.get('speed'), cfg.get('vq_max'), cfg.get('hybrid'),
                   cl.get('curloop')))
            if not healthy() and not recover(tag):
                return None
            fmark, imark, nmark = len(frames), len(isrs), len(notes)
            t0 = time.monotonic()
            send('r')
            done = fault = started = False
            while time.monotonic() - t0 < 120:
                poll(.1)
                for _, f in frames[fmark:]:
                    if f.get('st') == '1':
                        started = True
                    elif f.get('st') == '3':
                        fault = True
                    elif started and f.get('st') in ('4', '0') and f.get('out') == '0':
                        done = True
                fmark = len(frames)
                if done or fault:
                    break
            host = time.monotonic() - t0
            send('s'); poll(.4)
            seg_isrs = [n for _, n in isrs[imark:]]
            seg_frames = [f for _, f in frames[len(frames) - len(frames):] ]
            mv = [t for _, t in notes[nmark:]]
            done_line = next((t for t in mv if t.startswith('MOVE DONE')), '')
            dur = re.search(r'in (\d+) ms', done_line)
            say('CASE %s host=%.1fs started=%s done=%s fault=%s dev=%s isr_deltas=%s'
                % (tag, host, started, done, fault,
                   dur.group(1) + 'ms' if dur else '-',
                   ','.join(str(x) for x in seg_isrs[:8])))
            if fault:
                recover(tag + '-post')
            return {'tag': tag, 'host': round(host, 2),
                    'dev_ms': int(dur.group(1)) if dur else None,
                    'isr_deltas': seg_isrs,
                    'rate_hz': round(sum(seg_isrs) /
                                     max(1e-9, len(seg_isrs) * .25), 1)}

        poll(1.0)
        say('P0 fw=%s st=%s cl=%s ang=%s' % (last().get('fw'), last().get('st'),
                                             last().get('cl'), last().get('ang')))
        if last().get('st') == '3':
            recover('pre')
        results = []
        results.append(run_case('hyb0-loopON', 0, True))
        results.append(run_case('hyb0-loopOFF', 0, False))
        results.append(run_case('hyb1-loopOFF', 1, False))
        set_loop(False)
        set_hyb(1)
        set_speed('0.05')
        say('END cfg %s' % {k: dump()[0].get(k) for k in
                            ('speed', 'hybrid', 'vq_max')})
        say('END_STATE %s' % {k: last().get(k) for k in
                              ('st', 'out', 'ready', 'cl', 'ang', 'fault')})
        for r in results:
            if r:
                say('RESULT %-12s host=%ss device=%sms isr_rate=%sHz deltas=%s'
                    % (r['tag'], r['host'], r['dev_ms'], r['rate_hz'],
                       r['isr_deltas'][:6]))
    print('LOG', log_path)


if __name__ == '__main__':
    main()
