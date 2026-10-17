"""FOC2205 unattended closed-loop smoothness sweep (2026-10-17 night).

Operator question: with the current loop ON, do closed-loop position moves
stay smooth (on time, constant velocity, no jitter/glitches) across speeds
and force ceilings?

Blocks (all moves are 1-turn r / R closed-loop on the accept config):
  matrix : 0.05/0.10/0.25 rev/s x vq_max 2048/1536/~1024, loop ON
  slow   : 0.02 rev/s (1.2 rpm) at full force, loop ON
  ref    : loop OFF control at 0.05 and 0.25 (B-segment slowdown check)
  repeat : 4x r then 4x R at 0.10/2048, loop ON
  gains  : K/I gear scan (kp 4/16, ki 50/200) at 0.10/2048, loop ON
  tune   : one knob at a time at 0.05/2048 (ckp/kd/vel_win/filt/follow), loop ON
  cand   : kd60+filt256 spot checks across speeds/forces
  candmat: kd60+filt256 x full speed/force matrix, both directions, loop ON;
           intentionally leaves the candidate gains set at the end
  candrep: kd60+filt256 repeatability, 4x r then 4x R at 0.10/2048, loop ON
  kiscan : candidate gains, current-loop ki 50/200 clean rescan at 0.10/2048 (hyb0)
  slow2  : 0.02 rev/s (1.2 rpm) loop OFF vs ang_filt 1/64 A/B, candidate gains
  fast   : 0.5 rev/s (30 rpm) at vq_max 1013/1536/2048, loop ON, candidate gains
           (gear seek uses '0.50'; the dump prints the 0.5 gear as "0.50")
  posgain: motion kp 4/8, ki 4, kd 200, follow 200/100 scan at 0.05/2048
  accept5: 5 consecutive turns per direction at recommended speed/force caps
  accept8: same as accept5 but motion kp 8 (cross-speed check of the kp8 win)
  force8 : kp=8 force slices at 0.05/0.10/0.25 (low+max force, 2 turns each)
  slow8  : kp=8 at 0.02 rev/s (2 turns)
  edges12: fw .12 position acceleration-ramp regression at 0.25/1536
           and 0.50/1013/768, kp=8 loop ON, 5 pairs per condition
  soak   : 0.10/2048 alternating r/R x12 pairs, drift watch (crc/adce deltas)

Per move: MOVE DONE elapsed/residual/jitter, host-side device-time velocity
cv + step glitches + stalls + reversals, peak vq/iq/iref/id, crc/adc/jump
deltas, and an F read right after the move (capture resets at every begin).

Unattended safety: faults auto-recover via z (never a soft reset); on a
stuck board the script stops with END_STATE and the JSON still lands; the
current loop is left OFF and speed back at 0.05.
"""
import argparse, json, re, statistics, time
from pathlib import Path
import serial

ap = argparse.ArgumentParser()
ap.add_argument('--port', default='COM26')
ap.add_argument('--blocks', default='matrix,slow,ref,repeat,gains')
ap.add_argument('--tag', default='sweep')
ap.add_argument('--hybrid', type=int, default=1, help='hybrid commutation on/off for the sweep')
ap.add_argument('--slow-timeout', type=float, default=None,
                help='override move timeout (s) for rps <= 0.021')
args = ap.parse_args()
BLOCKS = [b.strip() for b in args.blocks.split(',') if b.strip()]

ROOT = Path(__file__).resolve().parents[3]
LOG = ROOT / 'experiments' / 'logs' / 'powered-20261017'
LOG.mkdir(parents=True, exist_ok=True)
STAMP = time.strftime('%H%M%S')
log_path = LOG / ('%s-smooth-%s.txt' % (STAMP, args.tag))
res_path = LOG / ('%s-smooth-%s.json' % (STAMP, args.tag))

RAW_TURN = 16384
GLITCH100 = 1200          # raw per 100 ms step above this = encoder glitch
frames, isrs, notes, records = [], [], [], []
pending = b''
log = None
ser = None


def say(*a):
    text = ' '.join(str(x) for x in a)
    print(text, flush=True)
    if log:
        log.write('NOTE ' + text + '\n'); log.flush()


def send(cmd):
    ser.write(cmd.encode('ascii')); ser.flush()
    log.write('HOST ' + cmd + '\n'); log.flush()


def read():
    global pending
    data = ser.read(max(1, ser.in_waiting))
    if not data:
        return
    pending += data
    while b'\n' in pending:
        line, pending = pending.split(b'\n', 1)
        text = line.decode('utf-8', 'replace').rstrip('\r')
        log.write(text + '\n')
        if text.startswith('#FOC,'):
            frames.append((time.monotonic(), dict(
                v.split('=', 1) for v in text.split(',')[1:] if '=' in v)))
        elif text.startswith('isr='):
            tok = dict(v.split('=', 1) for v in text.split() if '=' in v)
            try:
                tok['j'] = tuple(int(x) for x in tok['j'].split('/'))
                isrs.append((time.monotonic(), tok))
            except (KeyError, ValueError):
                pass
        elif text:
            notes.append((time.monotonic(), text))
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


def healthy(f=None):
    f = f if f is not None else last()
    return (f.get('st') == '0' and f.get('out') == '0' and f.get('ready') == '1')


def step_raw(a, b):
    return (b - a + 8192) % RAW_TURN - 8192


def recover(tag='recover', timeout=15.0):
    send('s'); poll(.5)
    if healthy():
        return True
    send('z')
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        poll(.5)
        if healthy():
            say('%s: recovered (z ok)' % tag)
            return True
    say('%s: RECOVERY FAILED state=%s' % (tag, {k: last().get(k) for k in
        ('st', 'out', 'ready', 'fault')}))
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


def seek(key, field, want, tries=8):
    for _ in range(tries):
        cfg, _ = dump()
        if cfg.get(field) == want:
            return True
        send(key); poll(.35)
    return dump()[0].get(field) == want


def set_speed(want):
    ok = seek('v', 'speed', want)
    cfg, _ = dump()
    say('speed -> %s (want %s) %s' % (cfg.get('speed'), want, 'OK' if ok else 'MISS'))
    return cfg.get('speed')


def set_vqmax(want, tol=20):
    ops = {'-': lambda v: max(v - v // 4, 32),
           '+': lambda v: min(v + v // 4, 2048)}
    for _ in range(3):
        cur = int(dump()[0].get('vq_max', '0'))
        if abs(cur - want) <= tol:
            break
        best = (abs(cur - want), cur, '')
        seen = {cur: ''}
        frontier = [cur]
        for _depth in range(8):
            nxt = []
            for v in frontier:
                for key, fn in ops.items():
                    nv = fn(v)
                    if nv in seen:
                        continue
                    seen[nv] = seen[v] + key
                    score = (abs(nv - want), nv, seen[nv])
                    if score < best:
                        best = score
                    nxt.append(nv)
            frontier = nxt
        _, tgt, seq = best
        say('vq_max %d -> %d via "%s" (want %d)' % (cur, tgt, seq, want))
        for key in seq:
            send(key); poll(.3)
    cur = int(dump()[0].get('vq_max', '0'))
    say('vq_max now %d (want %d +-%d) %s'
        % (cur, want, tol, 'OK' if abs(cur - want) <= tol else 'MISS'))
    return cur


def set_loop(on):
    cur = dump()[1].get('curloop')
    if cur == ('1' if on else '0'):
        return True
    if last().get('st') not in ('0', '4'):
        say('set_loop: refusing, state=%s' % last().get('st'))
        return False
    mark = len(notes)
    send('l'); poll(.6)
    cur = dump()[1].get('curloop')
    line = [t for _, t in notes[mark:] if t.startswith('current loop') or 'stop first' in t]
    say('loop %s -> %s %s' % ('ON' if on else 'OFF', cur, line))
    return cur == ('1' if on else '0')


def set_ckp(want, field='kp', key='K'):
    for _ in range(7):
        if dump()[1].get(field) == str(want):
            return True
        send(key); poll(.3)
    return dump()[1].get(field) == str(want)


def save_results():
    with res_path.open('w', encoding='utf-8') as jf:
        json.dump(records, jf, indent=1)


def oc_read():
    mark = len(notes)
    send('F'); poll(.8)
    return [t.strip() for _, t in notes[mark:] if t.strip()]


def move_timeout(rps):
    if rps <= 0.021 and args.slow_timeout:
        return args.slow_timeout
    return max(35.0, 1.0 / max(rps, 0.005) + 25.0)


def run_move(tag, cmd, rps):
    """One 1-turn closed-loop move; returns a metrics dict."""
    rec = {'tag': tag, 'cmd': cmd, 'rps': rps, 'result': 'NONE'}
    save_results()
    if not healthy():
        if not recover(tag + '-pre'):
            rec['result'] = 'RECOVER-FAIL'
            return rec
    pre = last()
    pre_ang = int(pre['ang'])
    crc0 = int(pre.get('crc', 0)); adce0 = int(pre.get('adce', 0))
    j0 = isrs[-1][1]['j'] if isrs else None
    fcur = len(frames); icur = len(isrs); nmark = len(notes)
    t_send = time.monotonic()
    send(cmd)
    started = done = fault = False
    timeout = move_timeout(rps)
    while time.monotonic() - t_send < timeout:
        poll(.1)
        new = [f for _, f in frames[fcur:]]
        fcur = len(frames)
        for f in new:
            if f.get('st') == '1':
                started = True
            elif f.get('st') == '3':
                fault = True
            elif started and f.get('st') in ('4', '0') and f.get('out') == '0':
                done = True
        if fault or done:
            break
    t_end = time.monotonic()
    send('s'); poll(.4)
    rec['host_s'] = round(t_end - t_send, 2)
    rec['done'] = done; rec['fault'] = fault

    lines = [t for _, t in notes[nmark:]]
    m = next((re.search(r'MOVE DONE: travelled ([+-])(\d+) raw \((\d+)/1000 turn\) '
                        r'in (\d+) ms, residual ([+-])(\d+) raw', t) for t in lines
              if t.startswith('MOVE DONE')), None)
    if m:
        rec['result'] = 'DONE'
        rec['turns_travel'] = int(m.group(3))
        rec['elapsed_ms'] = int(m.group(4))
        rec['residual'] = int(m.group(6)) * (-1 if m.group(5) == '-' else 1)
        rec['travel_sign'] = m.group(1)
    jm = next((re.search(r'\|vm\| mean=(-?\d+) peak=(-?\d+) raw/s \(ideal (\d+) raw/s\)',
                         t) for t in lines if t.startswith('  jitter:')), None)
    if jm:
        rec['jit_mean'] = abs(int(jm.group(1)))
        rec['jit_peak'] = int(jm.group(2))
        rec['ideal_rawps'] = int(jm.group(3))
    am = next((re.search(r'MOVE ABORT: (.+) \(err=(-?\d+) raw, vel=(-?\d+) raw/s, '
                         r'vq=(-?\d+), t=(\d+) ms\)', t) for t in lines
               if t.startswith('MOVE ABORT')), None)
    if am:
        rec['result'] = 'ABORT'
        rec['fault_msg'] = am.group(1)
        rec['abort_t_ms'] = int(am.group(5))
    if rec['result'] == 'NONE':
        rec['result'] = 'TIMEOUT'

    mv_frames = [f for t, f in frames if t_send <= t <= t_end]
    mv_isrs = [s for t, s in isrs if t_send <= t <= t_end and s.get('st') == '1']
    rec['n_frames'] = len(mv_frames)

    peak = {'vq': 0, 'iq': 0, 'iref': 0, 'id': 0, 'slip': 0, 'iacc': 0}
    for f in mv_frames:
        for k in peak:
            try:
                v = abs(int(f.get(k, 0)))
            except (TypeError, ValueError):
                continue
            if v > peak[k]:
                peak[k] = v
    rec.update({'pk_' + k: v for k, v in peak.items()})

    running = [f for f in mv_frames if f.get('st') == '1']
    vdev, dangs, dts = [], [], []
    for a, b in zip(running, running[1:]):
        try:
            dt = int(b['up']) - int(a['up'])
        except (KeyError, ValueError):
            continue
        if dt <= 20:
            continue
        d = step_raw(int(a['ang']), int(b['ang']))
        vdev.append(d * 1000.0 / dt)
        dangs.append(d); dts.append(dt)
    rec['n_vdev'] = len(vdev)
    if len(vdev) >= 8:
        trim = vdev[3:-3]
        mean = statistics.mean(trim) if trim else statistics.mean(vdev)
        sd = statistics.pstdev(trim) if len(trim) > 1 else 0.0
        rec['vdev_mean'] = round(mean, 1)
        rec['cv_pct'] = round(100.0 * sd / abs(mean), 2) if mean else None
        exp = rps * RAW_TURN
        rec['stall_pct'] = round(100.0 * sum(
            1 for v in trim if abs(v) < 0.5 * exp) / max(1, len(trim)), 1)
        rec['rev'] = sum(1 for a, b in zip(dangs[3:-3], dangs[4:-2])
                         if abs(a) >= 3 and abs(b) >= 3 and a * b < 0)
        rec['step100max'] = round(max((abs(d) / dt * 100.0)
                                      for d, dt in zip(dangs, dts)), 1)
        rec['step_glitches'] = sum(1 for d, dt in zip(dangs, dts)
                                   if abs(d) / dt * 100.0 > GLITCH100)
    if mv_isrs:
        vms = [int(s.get('vm', 0)) for s in mv_isrs]
        rec['vm_mean'] = round(statistics.mean(vms), 1)
        rec['vm_std'] = round(statistics.pstdev(vms), 1) if len(vms) > 1 else 0.0
    post = last()
    rec['crc_delta'] = int(post.get('crc', 0)) - crc0
    rec['adce_delta'] = int(post.get('adce', 0)) - adce0
    if isrs and j0:
        j1 = isrs[-1][1]['j']
        rec['jump_delta'] = [j1[0] - j0[0], j1[1] - j0[1]]
    rec['start_ang'] = pre_ang
    rec['end_ang'] = int(post.get('ang', pre_ang))

    oc = oc_read()
    rec['oc_lines'] = oc[:12]
    for t in oc:
        m2 = re.search(r'over=(\d+) maxrun=(\d+) glitch=(\d+)', t)
        if m2:
            rec['over'] = int(m2.group(1))
            rec['maxrun'] = int(m2.group(2))
            rec['glitch'] = int(m2.group(3))
        if t.startswith('OC snap:'):
            rec['snap'] = t

    if fault and not recover(tag + '-post'):
        rec['result'] = 'RECOVER-FAIL'
    say('MOVE[%s] %s %s dur=%s resid=%s jit=%s/%s vq=%s iq=%s iref=%s cv=%s%% '
        'g100=%s over/maxrun/glitch=%s/%s/%s%s'
        % (tag, cmd, rec['result'], rec.get('elapsed_ms', rec.get('abort_t_ms', '-')),
           rec.get('residual', '-'), rec.get('jit_mean', '-'), rec.get('jit_peak', '-'),
           rec.get('pk_vq', '-'), rec.get('pk_iq', '-'), rec.get('pk_iref', '-'),
           rec.get('cv_pct', '-'), rec.get('step100max', '-'),
           rec.get('over', '-'), rec.get('maxrun', '-'), rec.get('glitch', '-'),
           ' SNAP' if rec.get('snap') else ''))
    return rec


def condition(speed, vqmax, loop, cmds=('r', 'R')):
    set_speed(speed)
    set_vqmax(vqmax)
    set_loop(loop)
    cfg, cl = dump()
    say('COND speed=%s vq_max=%s loop=%s cl_kp=%s cl_ki=%s'
        % (cfg.get('speed'), cfg.get('vq_max'), cl.get('curloop'),
           cl.get('kp'), cl.get('ki')))
    rps = float(cfg.get('speed', speed))
    for cmd in cmds:
        rec = run_move('S%s-F%s-%s' % (speed.replace('.', ''), cfg.get('vq_max'), cmd),
                       cmd, rps)
        rec.update({'cond_speed': cfg.get('speed'), 'cond_vq_max': cfg.get('vq_max'),
                    'cond_loop': cl.get('curloop'), 'cond_ckp': cl.get('kp'),
                    'cond_cki': cl.get('ki')})
        records.append(rec)


def two(tag):
    """r + R pair at the current config."""
    cfg0, _ = dump()
    rps = float(cfg0.get('speed'))
    for cmd in ('r', 'R'):
        rec = run_move(tag + '-' + cmd, cmd, rps)
        rec.update({'cond_speed': cfg0.get('speed'),
                    'cond_vq_max': cfg0.get('vq_max')})
        records.append(rec)


class WindowsAwake:
    ES_CONTINUOUS = 0x80000000
    ES_SYSTEM_REQUIRED = 0x00000001

    @staticmethod
    def on():
        import ctypes
        ctypes.windll.kernel32.SetThreadExecutionState(
            WindowsAwake.ES_CONTINUOUS | WindowsAwake.ES_SYSTEM_REQUIRED)

    @staticmethod
    def off():
        import ctypes
        ctypes.windll.kernel32.SetThreadExecutionState(WindowsAwake.ES_CONTINUOUS)


def main():
    global log, ser
    try:
        WindowsAwake.on()
    except Exception:
        pass
    with serial.Serial(args.port, 115200, timeout=.02, write_timeout=.5) as s, \
            log_path.open('w', encoding='utf-8') as lg:
        ser, log = s, lg
        say('START blocks=%s log=%s' % (','.join(BLOCKS), log_path))
        poll(1.2)
        f = last()
        if not f:
            say('FATAL: no frames on %s -- board off or port busy' % args.port)
            return
        say('P0 fw=%s up=%s st=%s out=%s ready=%s cl=%s ang=%s'
            % (f.get('fw'), f.get('up'), f.get('st'), f.get('out'),
               f.get('ready'), f.get('cl'), f.get('ang')))
        fw = f.get('fw', '')
        try:
            fw_build = int(fw.rsplit('.', 1)[-1])
        except (AttributeError, ValueError):
            fw_build = -1
        if not fw.startswith('20261017.') or fw_build < 10:
            say('FATAL: unexpected firmware %s (need >=20261017.10)' % fw)
            return
        if f.get('st') == '3' and not recover('pre'):
            say('FATAL: fault not recoverable at start')
            return
        if not healthy() and not recover('pre2'):
            say('FATAL: not idle/healthy at start')
            return

        for key, field, want in (('k', 'kp', '2'), ('j', 'kd', '20/1000'),
                                 ('i', 'ki', '15/10'), ('c', 'follow', '500'),
                                 ('u', 'vel_win', '256'), ('q', 'ang_filt', '1/64')):
            ok = seek(key, field, want)
            say('cfg %s=%s (want %s) %s' % (field, dump()[0].get(field), want,
                                            'OK' if ok else 'MISS'))
        for _ in range(4):
            if dump()[0].get('hybrid') == str(args.hybrid):
                break
            send('y'); poll(.35)
        say('baseline hybrid=%s vel_win=%s ang_filt=%s'
            % (dump()[0].get('hybrid'), dump()[0].get('vel_win'),
               dump()[0].get('ang_filt')))
        cfg, cl = dump()
        say('P1 preflight ok cl_kp=%s cl_ki=%s cl_filt=%s cl_cap=%s'
            % (cl.get('kp'), cl.get('ki'), cl.get('filt'), cl.get('cap')))

        if 'matrix' in BLOCKS:
            say('===== BLOCK matrix (loop ON) =====')
            for speed in ('0.05', '0.10', '0.25'):
                for vq in (2048, 1536, 1024):
                    condition(speed, vq, True)
        if 'slow' in BLOCKS:
            say('===== BLOCK slow 1.2 rpm =====')
            condition('0.02', 2048, True)
        if 'ref' in BLOCKS:
            say('===== BLOCK voltage-mode reference (loop OFF) =====')
            condition('0.05', 2048, False)
            condition('0.25', 2048, False)
            set_loop(True)
        if 'repeat' in BLOCKS:
            say('===== BLOCK repeatability (0.10/2048, loop ON) =====')
            set_speed('0.10'); set_vqmax(2048); set_loop(True)
            cfg, _ = dump()
            rps = float(cfg.get('speed'))
            for i in range(4):
                records.append(run_move('REP-r%d' % i, 'r', rps))
            for i in range(4):
                records.append(run_move('REP-R%d' % i, 'R', rps))
        if 'gains' in BLOCKS:
            say('===== BLOCK current-loop gain scan (0.10/2048, loop ON) =====')
            set_speed('0.10'); set_vqmax(2048); set_loop(True)
            for kp in (4, 16):
                set_ckp(kp)
                _, cl = dump()
                say('gain scan cl_kp=%s cl_ki=%s' % (cl.get('kp'), cl.get('ki')))
                for cmd in ('r', 'R'):
                    records.append(run_move('K%s-%s' % (kp, cmd), cmd, 0.10))
            set_ckp(8)
            for ki in (50, 200):
                set_ckp(ki, field='ki', key='I')
                _, cl = dump()
                say('gain scan cl_kp=%s cl_ki=%s' % (cl.get('kp'), cl.get('ki')))
                for cmd in ('r', 'R'):
                    records.append(run_move('I%s-%s' % (ki, cmd), cmd, 0.10))
            set_ckp(100, field='ki', key='I')
        if 'tune' in BLOCKS:
            say('===== BLOCK tune, one knob at a time (0.05/2048, loop ON) =====')
            set_speed('0.05'); set_vqmax(2048); set_loop(True)
            two('T-BASE')
            set_ckp(4);  two('T-CKP4');  set_ckp(8)
            set_ckp(16); two('T-CKP16'); set_ckp(8)
            seek('j', 'kd', '60/1000');       two('T-KD60');    seek('j', 'kd', '20/1000')
            seek('u', 'vel_win', '64');       two('T-WIN64');   seek('u', 'vel_win', '256')
            seek('q', 'ang_filt', '1/256');   two('T-FILT256'); seek('q', 'ang_filt', '1/64')
            seek('c', 'follow', '800');       two('T-FOL800');  seek('c', 'follow', '500')
        if 'cand' in BLOCKS:
            say('===== BLOCK cand: kd60+filt256 across speeds/forces =====')
            set_loop(True)
            seek('j', 'kd', '60/1000'); seek('q', 'ang_filt', '1/256')
            set_speed('0.05'); set_vqmax(2048); two('C-S005-F2048')
            set_speed('0.10'); two('C-S010-F2048')
            set_speed('0.25'); two('C-S025-F2048')
            set_vqmax(1024);    two('C-S025-F1024')
            set_speed('0.02'); set_vqmax(2048); two('C-S002-F2048')
            seek('j', 'kd', '20/1000'); seek('q', 'ang_filt', '1/64')
        if 'candmat' in BLOCKS:
            say('===== BLOCK candmat: candidate gains x speed/force matrix =====')
            set_loop(True)
            seek('j', 'kd', '60/1000'); seek('q', 'ang_filt', '1/256')
            for speed in ('0.05', '0.10', '0.25'):
                for vq in (2048, 1536, 1024):
                    condition(speed, vq, True)
            say('candmat done (candidate gains intentionally left set: kd=60/1000, ang_filt=1/256)')
        if 'candrep' in BLOCKS:
            say('===== BLOCK candrep: candidate gains repeatability (0.10/2048, loop ON) =====')
            set_loop(True)
            seek('j', 'kd', '60/1000'); seek('q', 'ang_filt', '1/256')
            set_speed('0.10'); set_vqmax(2048)
            cfg, _ = dump()
            rps = float(cfg.get('speed'))
            for i in range(4):
                records.append(run_move('CREP-r%d' % i, 'r', rps))
            for i in range(4):
                records.append(run_move('CREP-R%d' % i, 'R', rps))
        if 'kiscan' in BLOCKS:
            say('===== BLOCK kiscan: candidate gains, ki 50/200 clean rescan (0.10/2048, loop ON) =====')
            set_loop(True)
            seek('j', 'kd', '60/1000'); seek('q', 'ang_filt', '1/256')
            set_speed('0.10'); set_vqmax(2048)
            for ki in (50, 200):
                set_ckp(ki, field='ki', key='I')
                _, cl = dump()
                say('kiscan cl_kp=%s cl_ki=%s' % (cl.get('kp'), cl.get('ki')))
                two('KI%s' % ki)
            set_ckp(100, field='ki', key='I')
        if 'slow2' in BLOCKS:
            say('===== BLOCK slow2: 0.02 rev/s loop OFF / filt A-B (candidate gains) =====')
            seek('j', 'kd', '60/1000'); seek('q', 'ang_filt', '1/256')
            set_speed('0.02'); set_vqmax(2048)
            set_loop(False); two('SL2-OFF')
            set_loop(True);  two('SL2-F256')
            seek('q', 'ang_filt', '1/64'); two('SL2-F64')
            seek('q', 'ang_filt', '1/256')
        if 'fast' in BLOCKS:
            say('===== BLOCK fast: 0.5 rev/s (30 rpm), loop ON, candidate gains =====')
            set_loop(True)
            seek('j', 'kd', '60/1000'); seek('q', 'ang_filt', '1/256')
            ok = seek('v', 'speed', '0.50')
            cfg, _ = dump()
            say('fast speed -> %s (want 0.50) %s' % (cfg.get('speed'), 'OK' if ok else 'MISS'))
            if cfg.get('speed') == '0.50':
                set_vqmax(1013); two('F2-F1013')
                set_vqmax(1536); two('F2-F1536')
                set_vqmax(2048); two('F2-F2048')
            else:
                say('fast: skipping block, speed gear mismatch (would run at %s)' % cfg.get('speed'))
        if 'edges12' in BLOCKS:
            say('===== BLOCK edges12: position accel ramp, kp=8 loop ON =====')
            set_loop(True)
            seek('j', 'kd', '60/1000'); seek('q', 'ang_filt', '1/256'); seek('k', 'kp', '8')
            set_speed('0.25'); set_vqmax(1536)
            for i in range(5): two('E12-S025-F1536-%d' % i)
            set_speed('0.50'); set_vqmax(1013)
            for i in range(5): two('E12-S050-F1013-%d' % i)
            set_vqmax(768)
            for i in range(5): two('E12-S050-F768-%d' % i)
            seek('k', 'kp', '2')
            set_loop(False)
            set_speed('0.05'); set_vqmax(2048)
        if 'posgain' in BLOCKS:
            say('===== BLOCK posgain: motion kp/ki/kd/follow scan (0.05/2048, loop ON) =====')
            set_loop(True)
            seek('j', 'kd', '60/1000'); seek('q', 'ang_filt', '1/256')
            set_speed('0.05'); set_vqmax(2048)
            seek('k', 'kp', '4');  two('PG-KP4')
            seek('k', 'kp', '8');  two('PG-KP8')
            seek('k', 'kp', '2')
            seek('i', 'ki', '40/10'); two('PG-KI4')
            seek('i', 'ki', '15/10')
            seek('j', 'kd', '200/1000'); two('PG-KD200')
            seek('j', 'kd', '60/1000')
            seek('c', 'follow', '200'); two('PG-FOL200')
            seek('c', 'follow', '100'); two('PG-FOL100')
            seek('c', 'follow', '500')
        if 'accept5' in BLOCKS:
            say('===== BLOCK accept5: 5 consecutive turns per direction at recommended caps =====')
            set_loop(True)
            seek('k', 'kp', '2'); seek('i', 'ki', '15/10')
            seek('j', 'kd', '60/1000'); seek('q', 'ang_filt', '1/256')
            seek('c', 'follow', '500')
            for speed, vq, tag in (('0.05', 2048, 'A5-S005-F2048'),
                                   ('0.10', 2048, 'A5-S010-F2048'),
                                   ('0.25', 1536, 'A5-S025-F1536'),
                                   ('0.50', 1013, 'A5-S050-F1013')):
                set_speed(speed); set_vqmax(vq)
                cfg, _ = dump()
                if cfg.get('speed') != speed:
                    say('accept5: speed mismatch %s want %s, skip condition' % (cfg.get('speed'), speed))
                    continue
                rps = float(cfg.get('speed'))
                for cmd in ('r', 'R'):
                    for i in range(5):
                        records.append(run_move('%s-%s%d' % (tag, cmd, i), cmd, rps))
        if 'accept8' in BLOCKS:
            say('===== BLOCK accept8: kp=8 cross-speed check (5 turns per direction) =====')
            set_loop(True)
            seek('k', 'kp', '8'); seek('i', 'ki', '15/10')
            seek('j', 'kd', '60/1000'); seek('q', 'ang_filt', '1/256')
            seek('c', 'follow', '500')
            for speed, vq, tag in (('0.05', 2048, 'A8-S005-F2048'),
                                   ('0.10', 2048, 'A8-S010-F2048'),
                                   ('0.25', 1536, 'A8-S025-F1536'),
                                   ('0.50', 1013, 'A8-S050-F1013'),
                                   ('0.50', 768, 'A8-S050-F768')):
                set_speed(speed); set_vqmax(vq)
                cfg, _ = dump()
                if cfg.get('speed') != speed:
                    say('accept8: speed mismatch %s want %s, skip condition' % (cfg.get('speed'), speed))
                    continue
                rps = float(cfg.get('speed'))
                for cmd in ('r', 'R'):
                    for i in range(5):
                        records.append(run_move('%s-%s%d' % (tag, cmd, i), cmd, rps))
            seek('k', 'kp', '2')
        if 'force8' in BLOCKS:
            say('===== BLOCK force8: kp=8 force slices (2 turns each) =====')
            set_loop(True)
            seek('k', 'kp', '8'); seek('i', 'ki', '15/10')
            seek('j', 'kd', '60/1000'); seek('q', 'ang_filt', '1/256')
            seek('c', 'follow', '500')
            for speed, vq, tag in (('0.05', 1024, 'F8-S005-F1024'),
                                   ('0.10', 1536, 'F8-S010-F1536'),
                                   ('0.25', 1024, 'F8-S025-F1024'),
                                   ('0.25', 2048, 'F8-S025-F2048')):
                set_speed(speed); set_vqmax(vq)
                cfg, _ = dump()
                if cfg.get('speed') != speed:
                    say('force8: speed mismatch %s want %s, skip condition' % (cfg.get('speed'), speed))
                    continue
                rps = float(cfg.get('speed'))
                for cmd in ('r', 'R'):
                    records.append(run_move('%s-%s' % (tag, cmd), cmd, rps))
            seek('k', 'kp', '2')
        if 'slow8' in BLOCKS:
            say('===== BLOCK slow8: kp=8 at 0.02 rev/s (2 turns) =====')
            set_loop(True)
            seek('k', 'kp', '8'); seek('i', 'ki', '15/10')
            seek('j', 'kd', '60/1000'); seek('q', 'ang_filt', '1/256')
            seek('c', 'follow', '500')
            set_speed('0.02'); set_vqmax(2048)
            cfg, _ = dump()
            rps = float(cfg.get('speed'))
            for cmd in ('r', 'R'):
                records.append(run_move('S8-S002-F2048-%s' % cmd, cmd, rps))
            seek('k', 'kp', '2')
        if 'soak' in BLOCKS:
            say('===== BLOCK soak: 0.10/2048 alternating r/R x12 pairs =====')
            set_loop(True)
            seek('k', 'kp', '2'); seek('i', 'ki', '15/10')
            seek('j', 'kd', '60/1000'); seek('q', 'ang_filt', '1/256')
            set_speed('0.10'); set_vqmax(2048)
            cfg, _ = dump()
            rps = float(cfg.get('speed'))
            for i in range(12):
                records.append(run_move('SOAK-r%d' % i, 'r', rps))
                records.append(run_move('SOAK-R%d' % i, 'R', rps))

        send('s'); poll(.5)
        if last().get('st') == '3':
            recover('end')
        set_loop(False)
        set_speed('0.05')
        set_vqmax(2048)
        cfg, cl = dump()
        say('END cfg speed=%s vq_max=%s hybrid=%s curloop=%s ckp=%s cki=%s'
            % (cfg.get('speed'), cfg.get('vq_max'), cfg.get('hybrid'),
               cl.get('curloop'), cl.get('kp'), cl.get('ki')))
        for t in oc_read():
            say('END ' + t)
        say('END_STATE ' + str({k: last().get(k) for k in
              ('st', 'out', 'ready', 'cl', 'ang', 'fault')}))


if __name__ == '__main__':
    try:
        main()
    finally:
        try:
            WindowsAwake.off()
        except Exception:
            pass
        save_results()
        print('\n=== SUMMARY (%d moves) ===' % len(records), flush=True)
        hdr = ('tag', 'result', 'elapsed', 'turns', 'resid', 'jit mean/peak', 'ideal',
               'vq', 'iq', 'iref', 'cv%', 'g100', 'o/m/g')
        print('%-20s %-7s %8s %5s %6s %14s %6s %5s %5s %5s %6s %7s %9s' % hdr)
        for r in records:
            print('%-20s %-7s %8s %5s %6s %14s %6s %5s %5s %5s %6s %7s %9s' % (
                r.get('tag'), r.get('result'),
                r.get('elapsed_ms', r.get('abort_t_ms', '-')),
                r.get('turns_travel', '-'), r.get('residual', '-'),
                '%s/%s' % (r.get('jit_mean', '-'), r.get('jit_peak', '-')),
                r.get('ideal_rawps', '-'), r.get('pk_vq', '-'), r.get('pk_iq', '-'),
                r.get('pk_iref', '-'), r.get('cv_pct', '-'), r.get('step100max', '-'),
                '%s/%s/%s' % (r.get('over', '-'), r.get('maxrun', '-'),
                              r.get('glitch', '-'))))
        print('LOG', log_path)
        print('JSON', res_path)
