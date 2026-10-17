"""FOC2205 2026-10-17: end-of-session restore + capture.

  * stop / recover if needed
  * current loop OFF (boot default is FOC_CURRENT_LOOP_DEFAULT=0)
  * speed -> 0.05 rev/s
  * dump 'd' + final status frame to final-state-ED.txt
"""
import time
from pathlib import Path
import serial

PORT = 'COM26'
ROOT = Path(__file__).resolve().parents[3]
LOG = ROOT / 'experiments' / 'logs' / 'powered-20261017'
log_path = LOG / 'final-state-ED.txt'
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

    def last():
        for t in reversed(notes):
            if t.startswith('#FOC,'):
                return dict(v.split('=', 1) for v in t.split(',')[1:] if '=' in v)
        return {}

    def curloop():
        mark = len(notes)
        send('d'); poll(.5)
        for t in notes[mark:]:
            if t.startswith('curloop='):
                return t.split()[0].split('=')[1]
        return None

    poll(1.0)
    f = last()
    say('P0 st=%s out=%s cl=%s ang=%s' % (f.get('st'), f.get('out'), f.get('cl'), f.get('ang')))
    if f.get('st') == '3':
        send('z'); poll(2.0)
    send('s'); poll(.6)

    if curloop() == '1':
        mark = len(notes)
        send('l'); poll(.6)
        say('l -> ' + ' | '.join(t for t in notes[mark:] if t.startswith('current loop')))
    say('final curloop=%s' % curloop())

    for _ in range(5):
        mark = len(notes)
        send('d'); poll(.5)
        sp = [t for t in notes[mark:] if 'speed=' in t]
        if sp and 'speed=0.05' in sp[-1]:
            break
        send('v'); poll(.4)

    mark = len(notes)
    send('d'); poll(.6)
    send('?'); poll(.6)
    send('F'); poll(.8)
    say('--- final dump ---')
    for t in notes[mark:]:
        if t and not t.startswith(('isr=', '#FOC,')):
            say('    ' + t)
    f = last()
    say('END_STATE ' + str({k: f.get(k) for k in
                            ('st', 'out', 'ready', 'cl', 'ang', 'fault', 'fw')}))
    say('LOG ' + str(log_path))
