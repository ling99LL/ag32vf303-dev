"""Wait for the ROM UART loader, reflash MCU+logic, then run SPIN acceptance.

The program write erases the whole flash, so the CPLD image is written last
and checked with agrv32flash -K/-M.  After flashing, the helper waits for the
operator to remove the BOOT0 strap and cold-cycle the board, then hands off to
wait_and_run.py.
"""
import argparse, json, subprocess, sys, time
from pathlib import Path


FLASHER = Path(r'C:\Users\Administrator\.platformio\packages\tool-agrv_flashloader\bin\agrv32flash.exe')


def run(command):
    proc = subprocess.run([str(x) for x in command], text=True, capture_output=True)
    print(('$ ' + ' '.join(str(x) for x in command)), flush=True)
    print(proc.stdout, end='', flush=True)
    if proc.stderr:
        print(proc.stderr, end='', file=sys.stderr, flush=True)
    return proc.returncode, proc.stdout + proc.stderr


def loader_ready(port):
    code, text = run([FLASHER, '-b', '57600', port])
    return code == 0 and 'Device' in text and 'AGM32RV40xxx' in text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', default='COM26')
    parser.add_argument('--flash-timeout', type=float, default=900.0)
    parser.add_argument('--app-timeout', type=float, default=900.0)
    args = parser.parse_args()

    here = Path(__file__).resolve().parent
    root = here.parents[2]
    log_dir = root / 'experiments' / 'logs' / 'powered-20261017'
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime('%H%M%S')
    status_path = log_dir / ('%s-flash-auto-status.json' % stamp)
    mcu_readback = log_dir / ('%s-mcu-readback.bin' % stamp)
    logic_readback = log_dir / ('%s-logic-readback.bin' % stamp)
    program = root / '.pio' / 'build' / 'foc2205_bringup' / 'foc2205.bin'
    logic = root / 'logic' / 'foc2205.bin'
    if not program.is_file() or not logic.is_file():
        raise SystemExit('missing build artifacts: %s / %s' % (program, logic))

    t0 = time.monotonic()
    print('WAIT ROM UART loader on %s with BOOT0=3V3' % args.port, flush=True)
    while time.monotonic() - t0 < args.flash_timeout:
        if loader_ready(args.port):
            break
        time.sleep(2.0)
    else:
        result = {'status': 'loader-timeout', 'port': args.port}
        status_path.write_text(json.dumps(result, indent=2), encoding='utf-8')
        print('LOADER_TIMEOUT', status_path, flush=True)
        return 2

    print('LOADER_OK; writing MCU firmware first', flush=True)
    commands = [
        [FLASHER, '-b', '57600', '-S', '0x80000000', '-w', program, '-v', args.port],
        [FLASHER, '-b', '57600', '-r', mcu_readback,
         '-S', '0x80000000:%d' % program.stat().st_size, args.port],
        [FLASHER, '-b', '57600', '-S', '0x80034000', '-l', logic, '-v', args.port],
        [FLASHER, '-b', '57600', '-r', logic_readback,
         '-S', '0x80034000:%d' % (0x1100 + logic.stat().st_size), args.port],
    ]
    runs = []
    for command in commands:
        code, text = run(command)
        runs.append({'command': [str(x) for x in command], 'returncode': code,
                     'output_tail': text[-12000:]})
        if code != 0:
            result = {'status': 'flash-failed', 'runs': runs,
                      'status_path': str(status_path)}
            status_path.write_text(json.dumps(result, indent=2, ensure_ascii=False),
                                   encoding='utf-8')
            print('FLASH_FAILED', status_path, flush=True)
            return 1

    program_data = program.read_bytes()
    logic_data = logic.read_bytes()
    mcu_image = mcu_readback.read_bytes()
    logic_image = logic_readback.read_bytes()
    prefix = (root / 'logic' / 'foc2205_batch.bin').read_bytes()[0x280:0x1380]
    verified = (mcu_image == program_data and
                len(logic_image) == 0x1100 + len(logic_data) and
                logic_image[:0x1100] == prefix and
                logic_image[0x1100:] == logic_data)
    runs.append({'readback_verified': verified,
                 'mcu_sha256': __import__('hashlib').sha256(mcu_image).hexdigest(),
                 'logic_sha256': __import__('hashlib').sha256(logic_image).hexdigest()})
    if not verified:
        result = {'status': 'readback-mismatch', 'runs': runs,
                  'status_path': str(status_path)}
        status_path.write_text(json.dumps(result, indent=2, ensure_ascii=False),
                               encoding='utf-8')
        print('READBACK_MISMATCH', status_path, flush=True)
        return 1

    print('FLASH_OK. Remove BOOT0 strap, then cold power cycle the whole board.',
          flush=True)
    wait_script = here / 'wait_and_run.py'
    code, text = run([sys.executable, wait_script, '--port', args.port,
                      '--timeout', str(args.app_timeout)])
    result = {'status': 'pass' if code == 0 else 'app-test-failed',
              'flash_runs': runs, 'app_exit': code,
              'app_output_tail': text[-20000:], 'status_path': str(status_path)}
    status_path.write_text(json.dumps(result, indent=2, ensure_ascii=False),
                           encoding='utf-8')
    print('FLASH_AUTO_RESULT', result['status'], status_path, flush=True)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
