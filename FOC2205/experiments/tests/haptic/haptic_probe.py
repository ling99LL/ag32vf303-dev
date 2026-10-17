"""Serial helpers and metrics for FOC2205 haptic acceptance probes."""
from __future__ import annotations
import csv
import json
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import serial


ROOT = Path(__file__).resolve().parents[3]
LOG_ROOT = ROOT / 'experiments' / 'logs'


def parse_kv(line: str):
    if not line.startswith('#FOC,'):
        return None
    out = {}
    for item in line[5:].split(','):
        if '=' in item:
            key, value = item.split('=', 1)
            out[key] = value
    return out if out.get('proto') == '3' else None


def parse_tele(line: str):
    if not line.startswith('$T,3,'):
        return None
    parts = line.split(',')
    if len(parts) not in (12, 13):
        return None
    try:
        out = {
            'proto': 3,
            'hm': int(parts[2]),
            'ang': int(parts[3]) / 100.0,
            'vel': int(parts[4]) / 1000.0,
            'tq': int(parts[5]),
            'tgt': int(parts[6]) / 100.0,
            'pos': int(parts[7]),
            'sub': int(parts[8]) / 100.0,
            'st': int(parts[9]),
            'out': int(parts[10]),
            'hz': int(parts[11]),
        }
        if len(parts) == 13:
            out['raw'] = int(parts[12])
        return out
    except ValueError:
        return None


@dataclass
class Metrics:
    rows: list
    p2p: float
    tail_p2p: float
    tail_ang: float
    tail_vel: float
    tail_tq: float
    tail_tgt: float
    hz_min: int
    hz_max: int
    pos: int
    sub: float


class Probe:
    def __init__(self, port: str, tag: str):
        self.port = port
        self.tag = tag
        self.ser = serial.Serial(port, 115200, timeout=0.02, write_timeout=0.3)
        self.pending = b''
        self.lines = []
        self.status = {}
        self.rows = []
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        self.outdir = LOG_ROOT / f'haptic-{stamp}-{tag}'
        self.outdir.mkdir(parents=True, exist_ok=True)
        self.results = []
        time.sleep(0.2)
        self.send('tel 100')
        self.send('s')

    def close(self):
        try:
            self.send('tel 0')
            self.send('s')
        finally:
            self.ser.close()

    def send(self, text: str):
        self.ser.write((text.rstrip('\n') + '\n').encode('ascii'))
        self.ser.flush()
        self.lines.append('HOST ' + text.rstrip('\n'))

    def _read(self):
        data = self.ser.read(max(1, self.ser.in_waiting))
        if not data:
            return
        self.pending += data
        while b'\n' in self.pending:
            raw, self.pending = self.pending.split(b'\n', 1)
            line = raw.decode('utf-8', 'replace').strip()
            if not line:
                continue
            self.lines.append(line)
            st = parse_kv(line)
            if st:
                self.status = st
                continue
            tele = parse_tele(line)
            if tele:
                self.rows.append(tele)

    def poll(self, seconds: float, keepalive: bool = True):
        end = time.monotonic() + seconds
        next_poll = 0.0
        while time.monotonic() < end:
            now = time.monotonic()
            if keepalive and now >= next_poll:
                self.send('?')
                next_poll = now + 0.5
            self._read()

    def wait_ready(self, timeout=5.0):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            self.send('?')
            self.poll(0.15, keepalive=False)
            if self.status.get('ready') == '1' and self.status.get('st') in ('0', '4'):
                return True
            if self.status.get('st') == '3':
                self.send('z')
        return False

    def query_cfg(self):
        self.send('d')
        self.poll(0.25, keepalive=False)
        for line in reversed(self.lines):
            if line.startswith('cfg:'):
                values = {}
                for token in line.split():
                    if '=' in token:
                        key, value = token.split('=', 1)
                        values[key] = value
                return values
        return {}

    def set_safe_move_profile(self, speed='0.02', vq_max=512):
        """Keep setup moves below the current trip envelope.

        The haptic mode itself uses its own 20% force limit; this profile is
        only for rot-based positioning between haptic captures.
        """
        for _ in range(8):
            cfg = self.query_cfg()
            if cfg.get('speed') == speed:
                break
            self.send('v')
            self.poll(0.2, keepalive=False)
        else:
            raise RuntimeError(f'could not select positioning speed {speed}')

        for _ in range(8):
            cfg = self.query_cfg()
            current = int(cfg.get('vq_max', '0'))
            if abs(current - vq_max) <= 64:
                break
            self.send('-' if current > vq_max else '+')
            self.poll(0.2, keepalive=False)
        else:
            raise RuntimeError(f'could not select positioning vq_max near {vq_max}')
        cfg = self.query_cfg()
        print(f"position profile: speed={cfg.get('speed')} vq_max={cfg.get('vq_max')}", flush=True)

    def set_center(self):
        self.send('m0')
        self.poll(0.25)
        self.send('cd')
        self.poll(0.25)

    def relative_angle(self):
        return self.rows[-1]['ang'] if self.rows else None

    def return_center(self):
        self.release()
        self.poll(0.2, keepalive=False)
        angle = self.relative_angle()
        if angle is None:
            raise RuntimeError('no telemetry while returning to center')
        if abs(angle) > 0.3 and not self.rotate(-angle):
            raise RuntimeError(f'return-to-center rot {-angle:.2f} failed')

    def position_to(self, target_deg, tries=6):
        """Correct the free-coast error so an m3/m4 capture starts at a known angle."""
        self.release()
        current = None
        for _ in range(tries):
            self.poll(0.15, keepalive=False)
            current = self.relative_angle()
            if current is None:
                raise RuntimeError('no telemetry while positioning')
            error = target_deg - current
            if abs(error) <= 0.6:
                return current
            if not self.rotate(error):
                raise RuntimeError(f'rot {error:.2f} while positioning to {target_deg:.2f} failed')
        self.poll(0.15, keepalive=False)
        current = self.relative_angle()
        if current is None or abs(target_deg - current) > 3.0:
            raise RuntimeError(f'positioning target {target_deg:.2f} missed (got {current})')
        return current

    def position_outside(self, target_deg, minimum_deg=50.0):
        """Approach a boundary target; overshoot outside the wall is acceptable."""
        try:
            self.position_to(target_deg)
        except RuntimeError:
            pass
        self.poll(0.08, keepalive=False)
        current = self.relative_angle()
        if current is None or current < minimum_deg:
            raise RuntimeError(
                f'outside positioning missed: want >= {minimum_deg:.1f}, got {current}')
        return current

    def position_range(self, target_deg, low_deg, high_deg, tries=8):
        """Position the rotor into a behaviorally valid angle interval."""
        self.release()
        current = None
        for _ in range(tries):
            self.poll(0.15, keepalive=False)
            current = self.relative_angle()
            if current is None:
                raise RuntimeError('no telemetry while positioning')
            if low_deg <= current <= high_deg:
                return current
            correction = target_deg - current
            correction = max(-8.0, min(8.0, correction))
            if abs(correction) <= 0.6:
                break
            if not self.rotate(correction):
                raise RuntimeError(
                    f'rot {correction:.2f} while positioning to {target_deg:.2f} failed')
        self.poll(0.15, keepalive=False)
        current = self.relative_angle()
        if current is None or not (low_deg <= current <= high_deg):
            raise RuntimeError(
                f'positioning range [{low_deg:.1f},{high_deg:.1f}] missed (got {current})')
        return current

    def position_between_large(self, target_deg, low_deg, high_deg, tries=3):
        """Use full-size moves; small moves can be pulled back by motor cogging."""
        self.release()
        current = None
        for _ in range(tries):
            self.poll(0.12, keepalive=False)
            current = self.relative_angle()
            if current is None:
                raise RuntimeError('no telemetry while positioning')
            if low_deg <= current <= high_deg:
                return current
            correction = target_deg - current
            if not self.rotate(correction):
                raise RuntimeError(
                    f'rot {correction:.2f} while positioning to {target_deg:.2f} failed')
        self.poll(0.08, keepalive=False)
        current = self.relative_angle()
        if current is None or not (low_deg <= current <= high_deg):
            raise RuntimeError(
                f'positioning range [{low_deg:.1f},{high_deg:.1f}] missed (got {current})')
        return current

    def enter(self, mode: int):
        self.rows.clear()
        self.send(f'm{mode}')
        self.poll(0.35)

    def release(self):
        self.send('s')
        self.poll(0.25)

    def rotate(self, deg: float, timeout=25.0):
        if not self.wait_ready():
            raise RuntimeError('device not ready before rot')
        self.rows.clear()
        mark = len(self.lines)
        self.send(f'rot {deg:g}')
        end = time.monotonic() + timeout
        next_poll = 0.0
        while time.monotonic() < end:
            now = time.monotonic()
            if now >= next_poll:
                self.send('?')
                next_poll = now + 0.4
            self._read()
            recent = self.lines[mark:]
            if any('MOVE DONE' in x for x in recent):
                return True
            if any('MOVE ABORT' in x for x in recent):
                self.poll(0.3)
                return False
        return False

    def capture(self, seconds=2.5):
        self.rows.clear()
        self.poll(seconds)
        usable = self.rows[-800:]
        if len(usable) < 30:
            return None
        ang = [r['ang'] for r in usable]
        tail = usable[-80:]
        return Metrics(
            rows=usable,
            p2p=max(ang) - min(ang),
            tail_p2p=max(r['ang'] for r in tail) - min(r['ang'] for r in tail),
            tail_ang=tail[-1]['ang'],
            tail_vel=max(abs(r['vel']) for r in tail),
            tail_tq=max(abs(r['tq']) for r in tail),
            tail_tgt=tail[-1]['tgt'],
            hz_min=min(r['hz'] for r in usable),
            hz_max=max(r['hz'] for r in usable),
            pos=tail[-1]['pos'],
            sub=tail[-1]['sub'],
        )

    def record(self, label: str, expected: str, metrics: Metrics | None,
               expect_pos: int | None = None, expect_tgt: float | None = None,
               expect_ang: float | None = None, ang_tol: float = 2.0):
        ok = metrics is not None
        if metrics:
            if any(r['st'] == 3 for r in metrics.rows):
                ok = False
            if not 19000 <= metrics.hz_min <= 21000:
                ok = False
            if expected == 'zero':
                ok = ok and metrics.tail_tq <= 5 and metrics.tail_vel <= 0.2
            elif expected == 'settle':
                ok = ok and metrics.tail_tq <= 80 and metrics.tail_vel <= 0.2 and metrics.tail_p2p <= 1.0
            elif expected == 'stable':
                ok = ok and metrics.tail_vel <= 0.2 and metrics.tail_p2p <= 1.0
            elif expected == 'wall':
                ok = ok and metrics.tail_vel <= 0.2 and metrics.tail_p2p <= 1.0
                ok = ok and abs(metrics.tail_ang - 45.0) <= 3.0
            elif expected == 'softwall':
                ok = ok and metrics.tail_vel <= 0.2 and metrics.tail_p2p <= 1.0
                ok = ok and metrics.tail_ang >= 44.5 and metrics.tail_tq >= 10
            elif expected == 'idle':
                ok = ok and metrics.tail_vel <= 0.2
            if expect_pos is not None:
                ok = ok and metrics.pos == expect_pos
            if expect_tgt is not None:
                ok = ok and abs(metrics.tail_tgt - expect_tgt) <= 5.0
            if expect_ang is not None:
                ok = ok and abs(metrics.tail_ang - expect_ang) <= ang_tol
        item = {
            'label': label,
            'expected': expected,
            'ok': ok,
            'metrics': None if metrics is None else metrics.__dict__,
        }
        self.results.append(item)
        if metrics:
            csv_path = self.outdir / (label.replace(' ', '_') + '.csv')
            with csv_path.open('w', encoding='utf-8-sig', newline='') as fh:
                writer = csv.DictWriter(fh, fieldnames=list(metrics.rows[0]))
                writer.writeheader()
                writer.writerows(metrics.rows)
            print(f"{label:24s} {'PASS' if ok else 'FAIL'}  "
                  f"p2p={metrics.tail_p2p:5.2f}deg vel={metrics.tail_vel:5.2f} "
                  f"tq={metrics.tail_tq:4.0f} pos={metrics.pos:+d} hz={metrics.hz_min}-{metrics.hz_max}")
        else:
            print(f'{label:24s} FAIL  no telemetry')

    def finish(self):
        summary = {
            'tag': self.tag,
            'port': self.port,
            'results': self.results,
            'bad': sum(not r['ok'] for r in self.results),
        }
        (self.outdir / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
        (self.outdir / 'serial.log').write_text('\n'.join(self.lines), encoding='utf-8')
        return summary
