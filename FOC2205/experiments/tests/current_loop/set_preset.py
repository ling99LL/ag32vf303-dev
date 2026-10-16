"""FOC2205 2026-10-17: switch console config between presets.

  accept : kp=2 kd=0.02 ki=1.5 follow=500 vel_win=256 vq_max=2048 hyb=1
           ang_filt=1/64 speed=0.05  (the A/B acceptance config)
  badpos : kp=4 kd=0    ki=10  follow=800 vel_win=64  vq_max~410 hyb=0
           ang_filt=1/1024 speed=0.05 (matches 235017-poscheck badpos run)
"""
import argparse, time
from pathlib import Path
import serial

ap = argparse.ArgumentParser()
ap.add_argument('--preset', choices=['accept', 'badpos'], required=True)
ap.add_argument('--port', default='COM26')
args = ap.parse_args()

PRESETS = {
    'accept': {'kp': '2', 'kd': '20/1000', 'ki': '15/10', 'follow': '500',
               'vel_win': '256', 'vq_max': 2048, 'ang_filt': '1/64',
               'hybrid': '1', 'speed': '0.05', 'vq_tol': 300},
    'badpos': {'kp': '4', 'kd': '0/1000', 'ki': '100/10', 'follow': '800',
               'vel_win': '64', 'vq_max': 410, 'ang_filt': '1/1024',
               'hybrid': '0', 'speed': '0.05', 'vq_tol': 12},
}
want = PRESETS[args.preset]

ROOT = Path(__file__).resolve().parents[3]
LOG = ROOT / 'experiments' / 'logs' / 'powered-20261017'
log_path = LOG / (time.strftime('%H%M%S-') + 'preset-%s.txt' % args.preset)
notes = []

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
        mark = len(notes)
        send('d'); poll(.5)
        out = {}
        for t in notes[mark:]:
            if t.startswith(('cfg:', 'hybrid=', 'curloop=')):
                for tok in t.split():
                    if '=' in tok and not tok.startswith(('ref=', 'elec_deg')):
                        k, _, v = tok.partition('=')
                        out.setdefault(k, v)
        if 'speed=0.05' in str(out.get('speed')) or True:
            for t in notes[mark:]:
                if t.startswith(('cfg:', 'hybrid=', 'curloop=')):
                    toks = t.split()
                    for k in ('speed',):
                        for tok in toks:
                            if tok.startswith(k + '='):
                                out[k] = tok.split('=')[1]
        return out

    def seek(key, field, wantv, tries=6):
        for _ in range(tries):
            cur = dump()
            got = cur.get(field)
            if got == wantv:
                return True, got
            send(key); poll(.35)
        return dump().get(field) == wantv, dump().get(field)

    read(); poll(.6)
    fr = {}
    for t in reversed(notes):
        if t.startswith('#FOC,'):
            fr = dict(v.split('=', 1) for v in t.split(',')[1:] if '=' in v)
            break
    say('P0 st=%s out=%s cl=%s ang=%s' % (fr.get('st'), fr.get('out'), fr.get('cl'), fr.get('ang')))
    if fr.get('st') == '3' or fr.get('out') == '1':
        send('s'); poll(.6)
        if fr.get('st') == '3':
            send('z'); poll(1.5)

    plan = [('k', 'kp'), ('j', 'kd'), ('i', 'ki'), ('c', 'follow'),
            ('v', 'speed'), ('u', 'vel_win')]
    for key, field in plan:
        ok, got = seek(key, field, want[field])
        say('%s -> %s (want %s) %s' % (field, got, want[field], 'OK' if ok else 'MISS'))

    # ang_filt via 'q'
    ok, got = seek('q', 'ang_filt', want['ang_filt'])
    say('ang_filt -> %s (want %s) %s' % (got, want['ang_filt'], 'OK' if ok else 'MISS'))

    # hybrid via 'y'
    for _ in range(3):
        cur = dump()
        if cur.get('hybrid') == want['hybrid']:
            break
        send('y'); poll(.35)
    say('hybrid -> %s (want %s)' % (dump().get('hybrid'), want['hybrid']))

    # vq_max via BFS on +/- ops
    def ops(v):
        return {'-': v - v // 4, '+': v + v // 4}

    for _ in range(2):
        cur = dump()
        v0 = int(cur.get('vq_max', '0'))
        if abs(v0 - want['vq_max']) <= want['vq_tol']:
            break
        best = (abs(v0 - want['vq_max']), v0, '')
        seen = {v0: ''}
        frontier = [v0]
        for depth in range(6):
            nxt = []
            for v in frontier:
                for key, nv in ops(v).items():
                    if nv < 32 or nv > 8192 or nv in seen:
                        continue
                    seen[nv] = seen[v] + key
                    score = (abs(nv - want['vq_max']), nv, seen[nv])
                    if score < best:
                        best = score
                    nxt.append(nv)
            frontier = nxt
        _, tgt, seq = best
        say('vq_max %d -> %d via "%s"' % (v0, tgt, seq))
        for key in seq:
            send(key); poll(.3)

    cur = dump()
    keep = ['kp', 'kd', 'ki', 'follow', 'vq_max', 'speed', 'vel_win',
            'ang_filt', 'hybrid', 'curloop']
    say('FINAL[' + args.preset + '] ' + ' '.join('%s=%s' % (k, cur.get(k)) for k in keep))
    send('s'); poll(.4)
    say('LOG ' + str(log_path))
