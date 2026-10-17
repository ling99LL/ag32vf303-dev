#!/usr/bin/env python3
"""FOC2205 m4 bounded-wall parked-at-boundary census."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from haptic_probe import Probe


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', default='COM26')
    ap.add_argument('--tag', default='wall')
    args = ap.parse_args()
    p = Probe(args.port, args.tag)
    try:
        if not p.wait_ready():
            raise RuntimeError('device not ready; check status/fault first')
        p.set_safe_move_profile()
        p.set_center()
        for delta in (46, 48, 50, 52, 54):
            p.position_between_large(delta + 8, 46, 80)
            p.enter(4)
            p.record(f'm4 soft wall +{delta}', 'softwall', p.capture(3.0),
                     expect_tgt=45.0)
    finally:
        summary = p.finish()
        p.close()
    print(f"BAD = {summary['bad']}  log={p.outdir}")
    return 0 if summary['bad'] == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
