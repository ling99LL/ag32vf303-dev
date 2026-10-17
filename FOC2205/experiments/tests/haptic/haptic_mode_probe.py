#!/usr/bin/env python3
"""FOC2205 m0-m4 automatic shake / settle census."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from haptic_probe import Probe


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', default='COM26')
    ap.add_argument('--tag', default='base')
    args = ap.parse_args()
    p = Probe(args.port, 'mode-' + args.tag)
    try:
        if not p.wait_ready():
            raise RuntimeError('device not ready; check status/fault first')
        p.set_safe_move_profile()
        p.set_center()

        p.enter(0)
        p.record('m0 center', 'zero', p.capture(2.0))
        p.position_between_large(30, 20, 45)
        p.enter(0)
        p.record('m0 land +30', 'zero', p.capture(2.0))

        p.position_between_large(30, 20, 45)
        p.enter(1)
        p.record('m1 at rest', 'settle', p.capture(2.5))

        p.position_between_large(30, 20, 45)
        p.enter(2)
        p.record('m2 at rest', 'settle', p.capture(3.0))

        p.position_between_large(0, -2, 2)
        p.enter(3)
        p.record('m3 center', 'settle', p.capture(2.5), expect_pos=0, expect_tgt=0)

        p.position_between_large(22, 19, 41)
        p.enter(3)
        p.record('m3 snap +20', 'stable', p.capture(4.0),
                 expect_pos=1, expect_tgt=30, expect_ang=30.0, ang_tol=2.5)

        p.position_between_large(-22, -41, -19)
        p.enter(3)
        p.record('m3 snap -20', 'stable', p.capture(4.0),
                 expect_pos=-1, expect_tgt=-30, expect_ang=-30.0, ang_tol=2.5)

        p.position_between_large(40, 32, 44)
        p.enter(3)
        p.record('m3 inside +40', 'stable', p.capture(4.0), expect_pos=1, expect_tgt=30)

        p.position_between_large(0, -15, 15)
        p.enter(4)
        p.record('m4 center free', 'idle', p.capture(2.0))

        p.position_between_large(60, 46, 80)
        p.enter(4)
        p.record('m4 bounded pull', 'wall', p.capture(4.0), expect_tgt=45)
    finally:
        summary = p.finish()
        p.close()
    print(f"BAD = {summary['bad']}  log={p.outdir}")
    return 0 if summary['bad'] == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
