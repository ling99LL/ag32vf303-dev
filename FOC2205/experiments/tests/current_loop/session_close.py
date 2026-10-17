"""FOC2205: final confirmation (candidate config) + safe end state.

Candidate smoothed motion config (from the 2026-10-17 night sweep):
  hybrid OFF, kd=60/1000, ang_filt=1/256, rest accept, speed 0.05, vq_max 2048.
Confirm 2 turns with the current loop ON, then 2 turns OFF, then leave the
board in the candidate motion config with the current loop OFF (boot default).
"""
import re, time
from pathlib import Path
import serial

PORT = 'COM26'
ROOT = Path(__file__).resolve().parents[3]
LOG = ROOT / 'experiments' / 'logs' / 'powered-20261017'
log_path = LOG / (time.strftime('%H%M%S-') + 'session-close.txt')

frames, isrs, notes = [], [], []
pending = b''


def main():
    global pending
    with serial.Serial(PORT, 115200, timeout=.02, write_timeout=.5) as ser, \
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
            say(tag, 'RECOVER FAILED', {k: last().get(k) for k in ('st', 'out', 'fault')})
            return False

        def dump():
            mark = len(notes)
            send('d'); poll(.5)
            out = {}
            for _, t in notes[mark:]:
                if t.startswith(('cfg:', 'hybrid=', 'curloop=')):
                    for tok in t.split():
                        if '=' in tok and not tok.startswith(('ref=', 'elec_deg')):
                            k, _, v = tok.partition('=')
                            out.setdefault(k, v)
            return out

        def seek(key, field, want, tries=8):
            for _ in range(tries):
                if dump().get(field) == want:
                    return True
                send(key); poll(.35)
            return dump().get(field) == want

        def set_hyb(want):
            if dump().get('hybrid') == str(want):
                return True
            send('y'); poll(.4)
            return dump().get('hybrid') == str(want)

        def set_loop(on):
            if dump().get('curloop') == ('1' if on else '0'):
                return True
            send('l'); poll(.6)
            return dump().get('curloop') == ('1' if on else '0')

        def oc_read():
            mark = len(notes)
            send('F'); poll(.8)
            return [t.strip() for _, t in notes[mark:] if t.strip()]

        def move(tag, cmd):
            if not healthy() and not recover(tag + '-pre'):
                return
            fmark, nmark = len(frames), len(notes)
            t0 = time.monotonic()
            send(cmd)
            done = fault = started = False
            while time.monotonic() - t0 < 60:
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
            send('s'); poll(.3)
            mv = [t for _, t in notes[nmark:]]
            done_line = next((t for t in mv if t.startswith('MOVE DONE')), '')
            jit = next((t for t in mv if t.startswith('  jitter')), '')
            abort = next((t for t in mv if t.startswith('MOVE ABORT')), '')
            oc = oc_read()
            oc_line = next((t for t in oc if t.startswith('OC:')), '')
            say('%s %s host=%.1fs %s %s %s' % (tag, cmd, time.monotonic() - t0,
                                               done_line or abort, jit.strip(), oc_line))
            if fault:
                recover(tag + '-post')

        poll(1.0)
        say('P0 %s' % {k: last().get(k) for k in ('fw', 'st', 'out', 'cl', 'ang')})
        if last().get('st') == '3':
            recover('pre')

        # candidate config
        set_hyb(0)
        seek('j', 'kd', '60/1000')
        seek('q', 'ang_filt', '1/256')
        seek('u', 'vel_win', '256')
        seek('c', 'follow', '500')
        set_loop(True)
        say('CONFIRM cfg %s' % {k: dump().get(k) for k in
                                ('kp', 'kd', 'ki', 'follow', 'vel_win', 'ang_filt',
                                 'hybrid', 'speed', 'vq_max', 'curloop')})
        move('CONF-ON-r', 'r')
        move('CONF-ON-R', 'R')
        set_loop(False)
        move('CONF-OFF-r', 'r')
        move('CONF-OFF-R', 'R')

        say('END cfg %s' % {k: dump().get(k) for k in
                            ('kp', 'kd', 'ki', 'follow', 'vel_win', 'ang_filt',
                             'hybrid', 'speed', 'vq_max', 'curloop')})
        for t in oc_read():
            say('END ' + t)
        say('END_STATE %s' % {k: last().get(k) for k in
                              ('st', 'out', 'ready', 'cl', 'ang', 'fault')})
    print('LOG', log_path)


if __name__ == '__main__':
    main()
