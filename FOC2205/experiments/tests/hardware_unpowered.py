"""Connected-board negative tests; require an unpowered/unavailable DRV8316.

Usage: python experiments/tests/hardware_unpowered.py COM26 [--reset]
The script refuses motion-command checks unless FAULT and aligned=drvok=out=0.
It does not establish physical motor/current/waveform behavior.
"""
import argparse
from datetime import datetime
from pathlib import Path
import subprocess
import sys
import time
import serial

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from foc_protocol import Status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('port')
    parser.add_argument('--reset', action='store_true')
    args = parser.parse_args()
    log_path = ROOT / 'experiments/logs' / f'unpowered-{datetime.now():%Y%m%d-%H%M%S}.txt'
    log_path.parent.mkdir(exist_ok=True)
    frames = []
    buf = b''
    with log_path.open('w',encoding='utf-8') as log, serial.Serial(args.port,115200,timeout=.05,write_timeout=.2) as port:
        def note(text):
            print(text)
            log.write(text+'\n')
            log.flush()

        def receive(seconds):
            nonlocal buf
            end = time.monotonic()+seconds
            recent = []
            while time.monotonic()<end:
                buf += port.read(4096)
                while b'\n' in buf:
                    raw,buf=buf.split(b'\n',1)
                    line=raw.decode('utf-8','replace').strip()
                    log.write(line+'\n')
                    if not line.startswith('isr=') and not line.startswith('#FOC,'):
                        print(line)
                    status=Status.parse(line)
                    if status:
                        recent.append(status)
                        frames.append(status)
            log.flush()
            return recent

        if args.reset:
            reset = subprocess.run(['cmd','/c',str(ROOT/'tools/reset_run.bat')],capture_output=True,text=True)
            log.write(reset.stdout+reset.stderr)
            note(f'reset run exit={reset.returncode}')
            assert reset.returncode == 0
            receive(3)
        port.write(b'?')
        recent=receive(.5)
        assert recent, 'No compatible diagnostic status frame'
        first=recent[-1]
        note('BASELINE '+str(first.values))
        assert first['st']==3 and first['aligned']==0 and first['drvok']==0 and first['out']==0, \
            'Precondition failed: this test requires unaligned startup FAULT with driver unavailable'
        # The firmware fault latch must reject every power-producing command.
        for command in ('r','R','o','O','b','B','t','T','m','x7','w4','z','s','f'):
            port.write(command.encode())
            receive(.15)
            port.write(b'?')
            recent=receive(.25)
            assert recent, 'No response after '+command
            for status in recent:
                assert status['st']==3 and not status['out'] and not status['mode'] and not status['ready'], command
            note('PASS rejected/released '+command)
        for _ in range(200):
            port.write(b'?')
            recent=receive(.1)
            assert recent, 'Polling response missing'
            for status in recent:
                assert status['st']==3 and not status['out'] and not status['mode']
        note(f'PASS sustained polling: {len(frames)} frames; encoder valid={sum(s["encok"] for s in frames)}/{len(frames)}')
        note('FINAL '+str(frames[-1].values))
    # Verify OS port release and reconnection separately from device reset.
    with serial.Serial(args.port,115200,timeout=.2,write_timeout=.2) as port:
        port.write(b's?')
        assert b'#FOC,' in port.read(4096)
    print('PASS close / reconnect / query; evidence:',log_path)


if __name__ == '__main__':
    main()
