"""Offline cruise-phase analyzer for smoothness_sweep logs.

Reads a smooth-*.txt log, segments it by HOST r/R lines, keeps the RUN
frames, then reports per move:
  * duration (device ms) and mean |v| vs ideal
  * cruise cv% (0.8/1.2 x ideal window, only 0.05..0.95 quantile kept)
  * spikes (|v| > 1.5 x ideal) with the encoder angle where they happen
  * micro-stall samples inside cruise
  * OC counters parsed from the script MOVE[...] NOTE line

Usage: python smooth_analyze.py <log> [--profile TAG]
"""
import argparse, re, statistics, sys
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument('log')
ap.add_argument('--profile', default=None)
args = ap.parse_args()

RAW = 16384


def step(a, b):
    return (b - a + 8192) % RAW - 8192


def parse(path):
    events = []
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            line = line.rstrip('\r\n')
            if line.startswith('#FOC,'):
                events.append(('F', dict(v.split('=', 1) for v in
                                         line.split(',')[1:] if '=' in v)))
            elif line.startswith('NOTE '):
                events.append(('N', line[5:]))
            elif line.startswith('HOST '):
                events.append(('H', line[5:]))
    return events


def ideal_of(tag):
    m = re.match(r'S(\d\d\d)', tag)
    return int(m.group(1)) / 100.0 * RAW if m else 0.1 * RAW


def segments(events):
    segs, cur = [], None
    for kind, payload in events:
        if kind == 'H' and payload in ('r', 'R'):
            cur = {'cmd': payload, 'frames': [], 'notes': []}
            segs.append(cur)
        elif cur is not None:
            if kind == 'F':
                cur['frames'].append(payload)
            elif kind == 'N':
                cur['notes'].append(payload)
                if payload.startswith('MOVE['):
                    cur = None
    return segs


def analyze(seg):
    run = [f for f in seg['frames'] if f.get('st') == '1']
    mv = next((n for n in seg['notes'] if n.startswith('MOVE[')), '')
    tm = re.search(r'MOVE\[(.+?)\] \w+ (\w+) dur=(\S+)', mv)
    tag = tm.group(1) if tm else '?'
    result = tm.group(2) if tm else '?'
    dur = tm.group(3) if tm else '-'
    oc = re.search(r'over/maxrun/glitch=(\S+)/(\S+)/(\S+)', mv)
    out = {'tag': tag, 'cmd': seg['cmd'], 'result': result, 'dur_note': dur,
           'ideal': ideal_of(tag),
           'over': oc.group(1) if oc else '-', 'maxrun': oc.group(2) if oc else '-',
           'glitch': oc.group(3) if oc else '-', 'nrun': len(run)}
    if len(run) < 4:
        return out
    ups = [int(f['up']) for f in run]
    angs = [int(f['ang']) for f in run]
    v, vt, va = [], [], []
    for i in range(len(run) - 1):
        dt = ups[i + 1] - ups[i]
        if dt <= 20:
            continue
        v.append(step(angs[i], angs[i + 1]) * 1000.0 / dt)
        vt.append((ups[i] + ups[i + 1]) / 2.0)
        va.append(angs[i + 1])
    out['dur_dev'] = (ups[-1] - ups[0]) / 1000.0
    out['v_mean'] = round(statistics.mean(v), 1)
    fid = 0.8 * out['ideal']
    idx = [i for i, x in enumerate(v) if abs(x) >= fid]
    cruise = v[idx[0]:idx[-1] + 1] if len(idx) > 4 else v
    out['cv_cruise'] = round(100.0 * statistics.pstdev(cruise) /
                             abs(statistics.mean(cruise)), 2) if len(cruise) > 2 else None
    spikes = [(vt[i], va[i], v[i]) for i in range(len(v)) if abs(v[i]) > 1.5 * out['ideal']]
    out['nspike'] = len(spikes)
    out['max_abs_v'] = round(max(abs(x) for x in v), 1)
    out['stalls'] = sum(1 for x in cruise if abs(x) < 0.3 * out['ideal'])
    out['spike_ang'] = [(int(a) // 256 * 256, round(x, 0)) for _, a, x in spikes[:14]]
    out['profile'] = list(zip([round(t) for t in vt], [round(x) for x in v],
                              [int(a) for a in va]))
    return out


def main():
    events = parse(args.log)
    segs = segments(events)
    rows = [analyze(s) for s in segs]
    print('%-20s %-7s %-8s %7s %7s %7s %8s %8s %6s %8s %6s' % (
        'tag', 'result', 'dur_note', 'dur_s', 'v_mean', 'ideal', 'cv_cruise',
        'max_abs_v', 'nspike', 'stalls', 'o/m/g'))
    for r in rows:
        print('%-20s %-7s %-8s %7s %7s %7s %8s %8s %6s %8s %6s' % (
            r['tag'], r['result'], r['dur_note'], r.get('dur_dev', '-'),
            r.get('v_mean', '-'), r['ideal'], r.get('cv_cruise', '-'),
            r.get('max_abs_v', '-'), r.get('nspike', '-'), r.get('stalls', '-'),
            '%s/%s/%s' % (r['over'], r['maxrun'], r['glitch'])))
    print()
    print('spike angle bins (256 raw = 5.6 deg):')
    for r in rows:
        if r.get('nspike'):
            print('  %-20s n=%-3d %s' % (r['tag'], r['nspike'], r['spike_ang']))
    if args.profile:
        for r in rows:
            if r['tag'] == args.profile:
                print('\nprofile %s (t_ms, v_raw/s, ang):' % r['tag'])
                prof = r.get('profile', [])
                for i in range(0, len(prof), max(1, len(prof) // 60)):
                    print('   ', prof[i])


if __name__ == '__main__':
    main()
