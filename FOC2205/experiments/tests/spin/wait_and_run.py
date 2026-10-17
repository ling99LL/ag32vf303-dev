"""Wait for a cold power cycle, calibrate, then run the SPIN acceptance matrix.

This helper exists because the current board revision cannot reliably reload
the CPLD on a debug-only reset.  It never resets or flashes the target: it
waits for a human cold power cycle, validates the expected firmware and safe
idle state, runs the existing calibration runner if needed, then invokes
accept_spin.py.
"""
import argparse, json, subprocess, sys, time
from pathlib import Path
import serial


def parse_frame(text):
    if not text.startswith('#FOC,'):
        return None
    values = dict(item.split('=', 1) for item in text.split(',')[1:] if '=' in item)
    if 'fw' not in values or 'st' not in values:
        return None
    return values


def probe(port, seconds=.7):
    try:
        with serial.Serial(port, 115200, timeout=.02, write_timeout=.3) as ser:
            ser.reset_input_buffer()
            ser.write(b'?')
            ser.flush()
            end = time.monotonic() + seconds
            pending = b''
            last = None
            while time.monotonic() < end:
                pending += ser.read(max(1, ser.in_waiting))
                while b'\n' in pending:
                    line, pending = pending.split(b'\n', 1)
                    text = line.decode('utf-8', 'replace').rstrip('\r')
                    frame = parse_frame(text)
                    if frame:
                        last = frame
            return last
    except (serial.SerialException, OSError):
        return None


def safe_idle(frame):
    return (frame and frame.get('proto') == '3' and
            frame.get('st') == '0' and frame.get('out') == '0' and
            frame.get('brk') == '0' and frame.get('calst') not in
            ('1', '2', '3', '4', '5', '6') and
            all(frame.get(k) == '1' for k in ('drvok', 'encok', 'adcok', 'cal')))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', default='COM26')
    parser.add_argument('--timeout', type=float, default=1800.0)
    parser.add_argument('--position', action='store_true',
                        help='also run the closed-loop position force8 slice')
    args = parser.parse_args()

    here = Path(__file__).resolve().parent
    tests = here.parent
    root = tests.parent
    log_dir = root / 'logs' / 'powered-20261017'
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime('%H%M%S')
    status_path = log_dir / ('%s-spin-auto-status.json' % stamp)
    t0 = time.monotonic()
    boot = None

    print('WAIT cold power cycle on %s (timeout %.0f s)' % (args.port, args.timeout),
          flush=True)
    while time.monotonic() - t0 < args.timeout:
        frame = probe(args.port)
        if safe_idle(frame):
            boot = frame
            break
        time.sleep(2.0)

    if not boot:
        result = {'status': 'timeout', 'port': args.port,
                  'elapsed_s': round(time.monotonic() - t0, 1)}
        status_path.write_text(json.dumps(result, indent=2), encoding='utf-8')
        print('WAIT_TIMEOUT', status_path, flush=True)
        return 2

    print('BOOT fw=%s up=%s ready=%s aligned=%s calok=%s stage=%s'
          % (boot.get('fw'), boot.get('up'), boot.get('ready'),
             boot.get('aligned'), boot.get('calok'), boot.get('stage')), flush=True)

    commands = []
    if boot.get('ready') != '1' or boot.get('aligned') != '1':
        commands.append([sys.executable, str(tests / 'calibrate.py'),
                         '--port', args.port, '--timeout', '60',
                         '--tag', 'spin-auto-cal'])
    commands.append([sys.executable, str(here / 'accept_spin.py'),
                     '--port', args.port, '--tag', 'spin-auto'])
    if args.position:
        commands.append([sys.executable, str(tests / 'current_loop' / 'smoothness_sweep.py'),
                         '--blocks', 'force8', '--tag', 'spin-auto-position'])

    runs = []
    failure = None
    for command in commands:
        print('RUN', ' '.join(command), flush=True)
        proc = subprocess.run(command, cwd=str(tests.parents[1]), text=True,
                              capture_output=True)
        runs.append({'command': command, 'returncode': proc.returncode,
                     'stdout_tail': proc.stdout[-12000:],
                     'stderr_tail': proc.stderr[-4000:]})
        print(proc.stdout, end='', flush=True)
        if proc.stderr:
            print(proc.stderr, end='', file=sys.stderr, flush=True)
        if proc.returncode != 0:
            failure = 'command failed with %d: %s' % (proc.returncode, command[1])
            break

    result = {'status': 'pass' if failure is None else 'fail',
              'port': args.port, 'boot': boot, 'runs': runs,
              'failure': failure,
              'elapsed_s': round(time.monotonic() - t0, 1),
              'status_path': str(status_path)}
    status_path.write_text(json.dumps(result, indent=2, ensure_ascii=False),
                           encoding='utf-8')
    print('AUTO_RESULT', result['status'], status_path, flush=True)
    return 0 if failure is None else 1


if __name__ == '__main__':
    raise SystemExit(main())
