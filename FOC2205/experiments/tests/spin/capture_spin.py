"""Capture high-rate SPIN telemetry for vibration diagnosis.

Usage:
  python experiments/tests/spin/capture_spin.py --speed V4 --force 80 --seconds 3

The console is polled at 50 Hz by default, well above the 10 Hz used by the
acceptance matrix.  The output JSON contains the raw frames and a simple FFT
summary of velocity, iq and vq.  This is diagnostic data, not a calibrated
mechanical vibration measurement.
"""
import argparse, json, statistics, time
from pathlib import Path
import numpy as np
import serial


SPEED_RPS = {'V1': 0.05, 'V2': 0.10, 'V3': 0.25, 'V4': 1.00}
FORCE_GEAR = {10: 'W1', 20: 'W2', 30: 'W3', 40: 'W4',
              50: 'W5', 60: 'W6', 70: 'W7', 80: 'W8'}
RAW = 16384


def step(a, b):
    return (b - a + RAW // 2) % RAW - RAW // 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', default='COM26')
    ap.add_argument('--speed', choices=sorted(SPEED_RPS), default='V4')
    ap.add_argument('--force', type=int, choices=sorted(FORCE_GEAR), default=80)
    ap.add_argument('--seconds', type=float, default=3.0)
    ap.add_argument('--rate', type=float, default=20.0)
    ap.add_argument('--q-steps', type=int, default=0,
                    help='send q this many times after start (angle-filter gear)')
    ap.add_argument('--tag', default='spin-capture')
    args = ap.parse_args()
    rps = SPEED_RPS[args.speed]

    root = Path(__file__).resolve().parents[3]
    log_dir = root / 'experiments' / 'logs' / 'powered-20261017'
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime('%H%M%S')
    log_path = log_dir / ('%s-%s.txt' % (stamp, args.tag))
    out_path = log_dir / ('%s-%s.json' % (stamp, args.tag))
    frames = []
    pending = b''
    notes = []

    with serial.Serial(args.port, 115200, timeout=.02, write_timeout=.5) as ser, \
            log_path.open('w', encoding='utf-8') as log:
        def send(cmd):
            ser.write(cmd.encode('ascii')); ser.flush()
            log.write('HOST ' + cmd + '\n'); log.flush()

        def read():
            nonlocal pending
            pending += ser.read(max(1, ser.in_waiting))
            while b'\n' in pending:
                line, pending = pending.split(b'\n', 1)
                text = line.decode('utf-8', 'replace').rstrip('\r')
                log.write(text + '\n')
                if text.startswith('#FOC,'):
                    frames.append((time.monotonic(), dict(
                        item.split('=', 1) for item in text.split(',')[1:] if '=' in item)))
                elif text and not text.startswith('isr='):
                    notes.append(text)
            log.flush()

        def poll(seconds, interval):
            end = time.monotonic() + seconds
            nxt = 0.0
            while time.monotonic() < end:
                now = time.monotonic()
                if now >= nxt:
                    send('?'); nxt = now + interval
                read()

        send('s'); poll(.8, .2)
        send(args.speed); poll(.15, .1)
        send(FORCE_GEAR[args.force]); poll(.15, .1)
        send('p'); poll(1.0, .1)       # let the 1.33 s ramp finish
        for _ in range(args.q_steps):
            send('q'); poll(.15, .1)
        if args.q_steps:
            poll(.5, .1)               # let the filter change settle
        capture_start = len(frames)
        send('?'); poll(args.seconds, 1.0 / args.rate)
        capture_end = len(frames)
        send('s'); poll(1.0, .2)

    frames = frames[capture_start:capture_end]
    samples = []
    for (_, a), (_, b) in zip(frames, frames[1:]):
        try:
            dt = int(b['up']) - int(a['up'])
            if dt <= 10:
                continue
            d = step(int(a['ang']), int(b['ang']))
            samples.append({'up': int(b['up']), 'dt_ms': dt,
                            'v_enc': d * 1000.0 / dt,
                            'v_fw': float(b['vel']),
                            'iq': float(b['iq']), 'vq': float(b['vq']),
                            'iref': float(b['iref']), 'err': float(b['err'])})
        except (KeyError, ValueError):
            pass
    if len(samples) < 16:
        raise SystemExit('too few samples: %d' % len(samples))

    def spectrum(key):
        y = np.asarray([s[key] for s in samples], dtype=float)
        y -= y.mean()
        fs = 1000.0 / statistics.mean(s['dt_ms'] for s in samples)
        y = np.nan_to_num(y)
        spec = np.abs(np.fft.rfft(y * np.hanning(len(y))))
        freqs = np.fft.rfftfreq(len(y), d=1.0 / fs)
        if len(spec) > 2:
            k = 1 + int(np.argmax(spec[1:]))
            return {'rms': round(float(np.sqrt(np.mean(y * y))), 2),
                    'peak_hz': round(float(freqs[k]), 2),
                    'peak_amp': round(float(spec[k] * 2.0 / len(y)), 2)}
        return {'rms': round(float(np.sqrt(np.mean(y * y))), 2)}

    summary = {
        'port': args.port, 'speed': args.speed, 'rps': rps,
        'force': args.force, 'seconds': args.seconds, 'rate_hz': args.rate,
        'n_samples': len(samples), 'mean_dt_ms': round(
            statistics.mean(s['dt_ms'] for s in samples), 2),
        'v_enc_mean': round(statistics.mean(s['v_enc'] for s in samples), 1),
        'v_enc_std': round(statistics.pstdev(s['v_enc'] for s in samples), 1),
        'v_fw_std': round(statistics.pstdev(s['v_fw'] for s in samples), 1),
        'iq_std': round(statistics.pstdev(s['iq'] for s in samples), 2),
        'vq_std': round(statistics.pstdev(s['vq'] for s in samples), 2),
        'spectrum': {key: spectrum(key) for key in ('v_enc', 'v_fw', 'iq', 'vq')},
        'notes': notes[-20:], 'samples': samples,
    }
    out_path.write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps({k: summary[k] for k in summary if k != 'samples'}, indent=2))
    print('LOG', log_path)
    print('JSON', out_path)


if __name__ == '__main__':
    main()
