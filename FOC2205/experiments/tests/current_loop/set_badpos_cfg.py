"""FOC2205 2026-10-17: align the motion/console config with the historical
bad-position run (235017-poscheck-5pct-at-badpos.txt, fw 20261016.7):

    kp=4  kd=0  ki=10(100/10)  follow=800  vel_win=64  vq_max~410

hybrid=0, ang_filt=1/1024, speed=0.05 and curloop=0 are set by prep_ED.py.
Uses only gear keys and '+/-' (vq_max via a tiny deterministic search).
"""
import time
from pathlib import Path
import serial

PORT = 'COM26'
TARGET_VQ = 410
ROOT = Path(__file__).resolve().parents[3]
LOG = ROOT / 'experiments' / 'logs' / 'powered-20261017'
log_path = LOG / (time.strftime('%H%M%S-') + 'badpos-cfg.txt')

notes = []

with serial.Serial(PORT, 115200, timeout=.02, write_timeout=.5) as ser, \
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
            if text:
                notes.append(text)

    def poll(seconds, interval=.12):
        end = time.monotonic() + seconds
        nxt = 0.0
        while time.monotonic() < end:
            now = time.monotonic()
            if now >= nxt:
                send('?'); nxt = now + interval
            read()

    def dump():
        """Fresh 'd' dump -> parsed fields."""
        mark = len(notes)
        send('d'); poll(.5)
        out = {}
        for t in notes[mark:]:
            if t.startswith('cfg:'):
                for tok in t.split():
                    if '=' in tok:
                        k, _, v = tok.partition('=')
                        out.setdefault(k, v)
            if t.startswith('hybrid='):
                for tok in t.split():
                    if '=' in tok:
                        k, _, v = tok.partition('=')
                        out.setdefault(k, v)
            if t.startswith('curloop='):
                out['curloop'] = t.split()[0].split('=')[1]
        return out

    def press_until(key, field, want, tries=5):
        for i in range(tries):
            cur = dump()
            if cur.get(field) == want:
                return True, cur
            mark = len(notes)
            send(key); poll(.4)
            for t in notes[mark:]:
                if t and not t.startswith(('#FOC,', 'isr=')):
                    say('    %s -> %s' % (key, t))
            if i == tries - 1:
                return False, dump()
        return False, {}

    read(); poll(.5)

    ok, cur = press_until('k', 'kp', '4')
    say('kp seek ->', ok, cur.get('kp'))
    ok, cur = press_until('j', 'kd', '0/1000')
    say('kd seek ->', ok, cur.get('kd'))
    ok, cur = press_until('i', 'ki', '100/10')
    say('ki seek ->', ok, cur.get('ki'))
    ok, cur = press_until('c', 'follow', '800')
    say('follow seek ->', ok, cur.get('follow'))
    ok, cur = press_until('u', 'vel_win', '64')
    say('vel_win seek ->', ok, cur.get('vel_win'))

    # vq_max: small BFS over the two deterministic integer ops
    def ops(v):
        return {'-': v - v // 4, '+': v + v // 4}

    for _ in range(2):
        cur = dump()
        v0 = int(cur.get('vq_max', '0'))
        if abs(v0 - TARGET_VQ) <= 12:
            say('vq_max ok:', v0)
            break
        # BFS depth <= 6 for best value
        seen = {v0: ''}
        frontier = [v0]
        best = (abs(v0 - TARGET_VQ), v0, '')
        for depth in range(6):
            nxt = []
            for v in frontier:
                for key, nv in ops(v).items():
                    if nv < 32 or nv > 8192 or nv in seen:
                        continue
                    seen[nv] = seen[v] + key
                    score = (abs(nv - TARGET_VQ), nv, seen[nv])
                    if score < best:
                        best = score
                    nxt.append(nv)
            frontier = nxt
        score, tgt, seq = best
        say('vq_max %d -> %d via "%s" (err=%d)' % (v0, tgt, seq, score))
        for key in seq:
            send(key); poll(.3)

    cur = dump()
    keep = ['kp', 'kd', 'ki', 'follow', 'err_limit', 'vq_max', 'speed',
            'vel_win', 'ang_filt', 'hybrid', 'curloop']
    say('FINAL ' + ' '.join('%s=%s' % (k, cur.get(k)) for k in keep))
    fr = None
    for t in reversed(notes):
        if t.startswith('#FOC,'):
            fr = dict(v.split('=', 1) for v in t.split(',')[1:] if '=' in v)
            break
    if fr:
        say('STATE', {k: fr.get(k) for k in ('st', 'out', 'ready', 'cl', 'ang', 'fault')})
    send('s'); poll(.4)

say('LOG', log_path)
print('done')
