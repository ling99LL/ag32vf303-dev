import time, sys
from pathlib import Path
import serial
s = serial.Serial('COM26', 115200, timeout=.02, write_timeout=.5)
pending = b''
def send(c): s.write(c.encode()); s.flush()
def read():
    global pending
    out = []
    pending += s.read(max(1, s.in_waiting))
    while b'\n' in pending:
        line, pending = pending.split(b'\n', 1)
        t = line.decode('utf-8', 'replace').rstrip('\r')
        if t:
            out.append(t)
    return out
def poll(sec):
    end = time.monotonic()+sec; last=None
    while time.monotonic() < end:
        send('?')
        for t in read():
            if t.startswith('#FOC,'):
                last = dict(v.split('=',1) for v in t.split(',')[1:] if '=' in v)
        time.sleep(.06)
    return last
def step(a,b): return (b-a+8192)%16384-8192

send('s'); f = poll(1.0)
print('start ang', f['ang'], 'st', f['st'], 'cl', f['cl'])
for i in range(3):
    send('v'); f = poll(.4)
print('speed now', f.get('vel'), f.get('st'))
# two R moves at 0.5 rev/s
for i in range(2):
    ang0 = int(poll(.3)['ang'])
    send('R')
    t0 = time.monotonic(); done = False
    while time.monotonic()-t0 < 15:
        f = poll(.08)
        if f['st'] == '3':
            print('R%d FAULT: %s (ang %s)' % (i, f.get('fault'), f['ang'])); break
        if f['st'] in ('4','0') and f['out'] == '0':
            done = True; break
    if done:
        f = poll(.5)
        ang1 = int(f['ang'])
        print('R%d: ang %d -> %d  delta %+d  (st=%s)' % (i, ang0, ang1, step(ang0, ang1), f['st']))
    else:
        send('s'); poll(.5)
# also one r (forward) for direction check
for i in range(1):
    ang0 = int(poll(.3)['ang'])
    send('r')
    t0 = time.monotonic(); done=False
    while time.monotonic()-t0 < 15:
        f = poll(.08)
        if f['st'] == '3':
            print('r%d FAULT: %s (ang %s)' % (i, f.get('fault'), f['ang'])); break
        if f['st'] in ('4','0') and f['out'] == '0':
            done = True; break
    if done:
        f = poll(.5)
        print('r%d: ang %d -> %d  delta %+d' % (i, ang0, int(f['ang']), step(ang0, int(f['ang']))))
send('s'); poll(.5)
# restore speed to 0.05 (from 0.5: 0.02,0.05 -> 2 presses)
for i in range(2):
    send('v'); poll(.3)
f = poll(.4)
print('final speed note check: vel', f.get('vel'), 'st', f.get('st'), 'ang', f.get('ang'))
s.close()
