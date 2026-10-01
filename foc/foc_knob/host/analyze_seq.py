import json, math, statistics

p = r"C:\Users\Administrator\Documents\AG32\foc\foc_knob\hall_seq.json"
d = json.load(open(p))
fr = d["frames"]
print("edges_before=%s edges_after=%s" % (d.get("edges_before"), d.get("edges_after")))
if not fr:
    raise SystemExit("no frames captured")
print("frames=%d span=%.2fs" % (len(fr), fr[-1]["t"] - fr[0]["t"]))

# one valid cyclic order of 3-hall gray code (exactly one bit flips per step)
CYC = [1, 3, 2, 6, 4, 5]
IDX = {v: i for i, v in enumerate(CYC)}

# dedup hall states with dwell
seq = []
for f in fr:
    h = f["hall"]
    if seq and seq[-1][0] == h:
        seq[-1][2] = f["t"]
    else:
        seq.append([h, f["t"], f["t"]])

st = []  # valid states, dwell >= 20ms (glitch filter)
for h, t0, t1 in seq:
    if h in IDX and (t1 - t0) >= 0.02:
        st.append((h, t0, t1, t1 - t0))
# merge consecutive same states after filtering
mrg = []
for s in st:
    if mrg and mrg[-1][0] == s[0]:
        mrg[-1] = (s[0], mrg[-1][1], s[2], s[2] - mrg[-1][1])
    else:
        mrg.append(s)
st = mrg

print("valid dwell states (>=20ms): %d" % len(st))
print("order:", " ".join(str(s[0]) for s in st))
net = 0
odd = 0
for a, b in zip(st, st[1:]):
    dd = (IDX[b[0]] - IDX[a[0]]) % 6
    if dd == 1:
        net += 1
    elif dd == 5:
        net -= 1
    else:
        odd += 1
print("transitions=%d net=%+d odd/missed=%d" % (max(0, len(st) - 1), net, odd))
print("=> if hand turn was exactly 1 mech rev: pole pairs = |net|/6 = %.2f" % (abs(net) / 6.0))

byh = {}
for h, t0, t1, dur in st:
    byh.setdefault(h, []).append(dur)
for h in sorted(byh):
    ds = byh[h]
    print("state %d: n=%2d mean=%4.0fms min=%4.0f max=%4.0f" %
          (h, len(ds), 1000 * statistics.mean(ds), 1000 * min(ds), 1000 * max(ds)))

angs = [f["ang"] for f in fr]
tot = 0.0
prev = angs[0]
for a in angs[1:]:
    dd = a - prev
    if dd > math.pi:
        dd -= 2 * math.pi
    if dd < -math.pi:
        dd += 2 * math.pi
    tot += dd
    prev = a
print("unwrapped ang delta = %.3f rad = %.1f deg" % (tot, tot * 57.29578))
vels = [f["vel"] for f in fr]
print("vel: min=%.3f max=%.3f rad/s" % (min(vels), max(vels)))
