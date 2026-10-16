"""FOC2205 2026-10-17: single decisive move runner for the bad-window E/D tests.

Assumes the rotor is parked inside the bad window (snap_walk.py first).

  E: --tag E            voltage mode move (curloop must be OFF)
  D: --tag D --loop on  current loop ON (toggled here when idle)

Captures: start ang, done/abort text (incl. 'MOVE ABORT: current ADC
threshold ... n=?' from the guard), latched fault, travel, peak |vq|,
and the full 'F' OC snapshot after the move (counters + frozen window).
Recovers a latched fault with 'z' before exiting.
"""
import argparse, time
from pathlib import Path
import serial

ap = argparse.ArgumentParser()
ap.add_argument('--port', default='COM26')
ap.add_argument('--tag', default='E')
ap.add_argument('--cmd', default='r')
ap.add_argument('--loop', choices=['keep', 'on', 'off'], default='keep')
ap.add_argument('--timeout', type=float, default=90.0)
args = ap.parse_args()

ROOT = Path(__file__).resolve().parents[3]
LOG = ROOT / 'experiments' / 'logs' / 'powered-20261017'
LOG.mkdir(parents=True, exist_ok=True)
log_path = LOG / (time.strftime('%H%M%S-') + 'window-%s.txt' % args.tag)

frames, notes = [], []

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
            if text.startswith('#FOC,'):
                frames.append(dict(v.split('=', 1) for v in text.split(',')[1:] if '=' in v))
            elif text:
                notes.append(text)

    def poll(seconds, interval=.12):
        end = time.monotonic() + seconds
        nxt = 0.0
        while time.monotonic() < end:
            now = time.monotonic()
            if now >= nxt:
                send('?'); nxt = now + interval
            read()

    def last():
        return frames[-1] if frames else {}

    def healthy(f):
        return (f and f.get('st') == '0' and f.get('out') == '0' and f.get('ready') == '1')

    def dump_curloop():
        mark = len(notes)
        send('d'); poll(.5)
        for t in notes[mark:]:
            if t.startswith('curloop='):
                return t.split()[0].split('=')[1]
        return None

    def recover(timeout=12.0, tag='recover'):
        send('s'); poll(.5)
        if healthy(last()):
            return True
        send('z')
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            poll(.5)
            if healthy(last()):
                say('%s: ok' % tag)
                return True
        say('%s: FAILED %s' % (tag, {k: last().get(k) for k in ('st', 'out', 'ready', 'fault')}))
        return False

    def oc_dump(tag):
        mark = len(notes)
        send('F'); poll(.9)
        lines = [t for t in notes[mark:] if t and not t.startswith(('isr=', '#FOC,'))]
        say('OC[%s]' % tag)
        for t in lines:
            say('    ' + t)
        return lines

    # ---------------- run ----------------
    poll(1.0)
    if not frames:
        raise RuntimeError('no frames on %s' % args.port)
    say('RUN tag=%s cmd=%s loop=%s fw=%s start_ang=%s st=%s out=%s cl=%s'
        % (args.tag, args.cmd, args.loop, last().get('fw'), last().get('ang'),
           last().get('st'), last().get('out'), last().get('cl')))
    if last().get('st') == '3' or not healthy(last()):
        recover(tag='pre')

    cur = dump_curloop()
    say('curloop now = %s' % cur)
    if args.loop == 'on' and cur == '0':
        mark = len(notes)
        send('l'); poll(.6)
        say('l on  ->', [t for t in notes[mark:] if t.startswith('current loop')])
        say('curloop verify = %s' % dump_curloop())
    elif args.loop == 'off' and cur == '1':
        mark = len(notes)
        send('l'); poll(.6)
        say('l off ->', [t for t in notes[mark:] if t.startswith('current loop')])
        say('curloop verify = %s' % dump_curloop())

    # baseline: clear OC counters right before the move
    oc_dump('before-' + args.tag)

    if not healthy(last()):
        raise RuntimeError('not idle before move: %s'
                           % {k: last().get(k) for k in ('st', 'out', 'fault')})
    start_ang = int(last()['ang'])
    say('=== %s: SEND %s from ang=%d cl=%s vq_max-cfg speed=%s ==='
        % (args.tag, args.cmd, start_ang, last().get('cl'), last().get('vel')))
    send(args.cmd); poll(.2)

    cursor = len(frames)
    started = False
    fault_frame = None
    done_frame = None
    peak = {'vq': 0, 'ia': 0, 'ib': 0, 'ic': 0, 'ipa': 0, 'ipb': 0, 'ipc': 0,
            'vel': 0, 'iq': 0, 'iref': 0}
    note_mark = len(notes)
    t0 = time.monotonic()
    while time.monotonic() - t0 < args.timeout:
        poll(.06 if time.monotonic() - t0 < 2.5 else .15)
        while cursor < len(frames):
            f = frames[cursor]; cursor += 1
            if f.get('st') == '1':
                started = True
            for k in peak:
                try:
                    v = abs(int(f.get(k, 0)))
                except (TypeError, ValueError):
                    continue
                if v > peak[k]:
                    peak[k] = v
            if f.get('st') == '3':
                fault_frame = f
                break
            if started and f.get('st') in ('4', '0') and f.get('out') == '0':
                done_frame = f
                break
        if fault_frame or done_frame:
            break
    elapsed = time.monotonic() - t0
    send('s'); poll(.5)
    end = last()
    end_ang = int(end.get('ang', start_ang))

    # lines the firmware printed during/after the move (abort/done text)
    tail = [t for t in notes[note_mark:] if not t.startswith(('isr=', '#FOC,'))]
    say('--- console lines during move ---')
    for t in tail:
        say('    ' + t)
    say('--- move result: elapsed=%.2fs started=%s done=%s fault=%s'
        % (elapsed, started, done_frame is not None, fault_frame is not None))
    say('    ang %d -> %d (step %+d)' % (start_ang, end_ang,
                                         (end_ang - start_ang + 8192) % 16384 - 8192))
    say('    peak |vq|=%d |vel|=%d |ia|=%d |ib|=%d |ic|=%d |ipa|=%d |ipb|=%d |ipc|=%d |iq|=%d |iref|=%d'
        % (peak['vq'], peak['vel'], peak['ia'], peak['ib'], peak['ic'],
           peak['ipa'], peak['ipb'], peak['ipc'], peak['iq'], peak['iref']))
    if fault_frame:
        say('    FAULT: %s' % fault_frame.get('fault'))
    if done_frame:
        say('    DONE frame ok')

    oc_lines = oc_dump(args.tag)

    # verdict
    abort_txt = [t for t in tail if t.startswith('MOVE ABORT')]
    verdict = []
    if abort_txt:
        verdict.append('ABORT: ' + abort_txt[-1])
        if 'current ADC threshold' in abort_txt[-1]:
            n = '?'
            for tok in abort_txt[-1].split():
                if tok.startswith('n='):
                    n = tok.split('=')[1]
            verdict.append('current-guard tripped at n=%s (>=3 means real consecutive over-current)' % n)
    elif done_frame:
        verdict.append('COMPLETED with no trip')
    else:
        verdict.append('INCOMPLETE (timeout)')
    for t in oc_lines:
        if t.startswith('OC:'):
            verdict.append('counters: ' + t)
        if t.startswith('OC snap:') and 'kind=trip' in t:
            verdict.append('snapshot: ' + t)
    say('VERDICT[%s] %s' % (args.tag, ' | '.join(verdict)))

    if fault_frame:
        recover(tag='after-' + args.tag)
    say('END_STATE[%s] %s' % (args.tag, {k: last().get(k) for k in
                                         ('st', 'out', 'ready', 'cl', 'ang', 'fault')}))
    say('LOG ' + str(log_path))
