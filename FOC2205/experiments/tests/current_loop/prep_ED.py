"""FOC2205 2026-10-17: bring the board to a known idle state before the
bad-window E/D runs.

  * stop any move; recover latched faults with 'z' if needed
  * current loop OFF (toggle 'l' only when idle; verify via 'd')
  * speed gear -> 0.05 rev/s ('v' until it reports 0.05)
  * E-run fidelity config: hybrid OFF ('y' if ON), angle filter 1/1024
    ('q' until ang_filt=1/1024), vq_max -> first gear <= 500 ('-' presses)
  * 'F' baseline: print old OC counters, then reset the capture
  * final '?' + 'd' dump

All traffic is logged to experiments/logs/powered-20261017/<time>-prep-ED.txt
"""
import time
from pathlib import Path
import serial

PORT = 'COM26'
ROOT = Path(__file__).resolve().parents[3]
LOG = ROOT / 'experiments' / 'logs' / 'powered-20261017'
LOG.mkdir(parents=True, exist_ok=True)
log_path = LOG / (time.strftime('%H%M%S-') + 'prep-ED.txt')

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

    def last_frame():
        for t in reversed(notes):
            if t.startswith('#FOC,'):
                return dict(v.split('=', 1) for v in t.split(',')[1:] if '=' in v)
        return {}

    def cfg_text():
        return [t for t in notes if t.startswith(('cfg:', 'hybrid=', 'curloop='))]

    read(); poll(.5)
    say('P0', {k: last_frame().get(k) for k in
               ('fw', 'st', 'out', 'ready', 'cl', 'ang', 'fault')})

    # --- stop whatever is running, recover if faulted ---
    mark = len(notes)
    send('s'); poll(.6)
    say('stop ->', [t for t in notes[mark:] if t.startswith('released')] or 'no released line')
    fr = last_frame()
    if fr.get('st') == '3':
        mark = len(notes)
        send('z'); poll(2.0)
        say('z ->', [t for t in notes[mark:] if t.startswith('recovered')] or 'no recovered line')
    fr = last_frame()
    if not (fr.get('st') == '0' and fr.get('out') == '0'):
        raise RuntimeError('not idle after stop: %s' % {k: fr.get(k) for k in ('st', 'out', 'fault')})
    say('idle ok ang=%s' % fr.get('ang'))

    # --- current loop off ---
    mark = len(notes)
    send('d'); poll(.5)
    cur = [t for t in cfg_text() if t.startswith('curloop=')]
    say('cfg before:', ' | '.join(notes[mark:] and [t for t in notes[mark:] if t.startswith(('cfg:', 'hybrid=', 'curloop='))] or []))
    if not cur or not cur[-1].startswith('curloop=0'):
        mark = len(notes)
        send('l'); poll(.5)
        say('l ->', [t for t in notes[mark:] if t.startswith('current loop')] or 'no line')
        mark = len(notes)
        send('d'); poll(.5)
        cur = [t for t in notes[mark:] if t.startswith('curloop=')]
    if not cur or not cur[-1].startswith('curloop=0'):
        raise RuntimeError('current loop still on: %s' % cur)
    say('curloop off ok:', cur[-1] if cur else '?')

    # --- speed 0.05 ---
    for _ in range(5):
        mark = len(notes)
        send('d'); poll(.5)
        sp = [t for t in notes[mark:] if 'speed=' in t]
        if sp and 'speed=0.05 rev/s' in sp[-1]:
            break
        send('v'); poll(.4)
    say('speed ok:', [t for t in notes[-8:] if 'speed=' in t][-1:])

    # --- hybrid off ---
    mark = len(notes)
    send('d'); poll(.5)
    hy = [t for t in notes[mark:] if t.startswith('hybrid=')]
    if hy and 'hybrid=0' not in hy[-1]:
        mark = len(notes)
        send('y'); poll(.4)
        say('y ->', [t for t in notes[mark:] if t.startswith('hybrid')] or 'no line')

    # --- angle filter 1/1024 ---
    for _ in range(6):
        mark = len(notes)
        send('d'); poll(.5)
        af = [t for t in notes[mark:] if 'ang_filt=' in t]
        if af and 'ang_filt=1/1024' in af[-1]:
            break
        send('q'); poll(.4)
    say('ang_filt ok:', [t for t in notes[-8:] if 'ang_filt=' in t][-1:])

    # --- vq_max toward <=500 (original badpos was 410) ---
    for _ in range(8):
        mark = len(notes)
        send('d'); poll(.5)
        cf = [t for t in notes[mark:] if t.startswith('cfg:')]
        vq = None
        if cf:
            for tok in cf[-1].split():
                if tok.startswith('vq_max='):
                    vq = int(tok.split('=')[1])
        if vq is None:
            break
        if vq <= 500:
            say('vq_max ok: %d' % vq)
            break
        mark = len(notes)
        send('-'); poll(.4)
        say('- ->', [t for t in notes[mark:] if t.startswith('vq_max=')] or 'no line')

    # --- OC baseline + clear ---
    mark = len(notes)
    send('F'); poll(.8)
    say('F baseline:')
    for t in notes[mark:]:
        if t and not t.startswith('isr='):
            say('    ' + t)

    # --- final dumps ---
    mark = len(notes)
    send('d'); poll(.6)
    send('s'); poll(.5)
    for t in notes[mark:]:
        if t.startswith(('cfg:', 'hybrid=', 'curloop=')):
            say('FINAL ' + t)
    fr = last_frame()
    say('END_STATE', {k: fr.get(k) for k in
                      ('st', 'out', 'ready', 'cl', 'ang', 'fault', 'fw', 'ocn', 'ocmx', 'ocg')})

say('LOG', log_path)
