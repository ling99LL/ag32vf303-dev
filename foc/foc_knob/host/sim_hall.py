import json, math

# Faithful port of hall.c hall_commit/hall_update (pre-fix logic) fed with the
# raw hall timeline captured in hall_seq.json (5ms per frame).
d = json.load(open(r"C:\Users\Administrator\Documents\AG32\foc\foc_knob\hall_seq.json"))
raw = [f["hall"] for f in d["frames"]]
capt = [f["ang"] for f in d["frames"]]

SECTOR_MAP = [-1, 5, 3, 4, 1, 0, 2, -1]   # old assumed forward order 5,4,6,2,3,1
DEG60 = math.pi / 3.0
MIN_EDGE_US = 1500
RATE_CAP = 250.0
POLL_COMMIT_S = 0.010
PP = 6.0

def simulate(flip, a0, frames, dt=50e-6, frame_s=0.005):
    last_state = -1
    last_k = -1
    pos_sec = 0.0
    pos_est = 0.0
    t_edge_us = 0.0
    rate = 0.0
    thr_prev = None
    mech = 0.0
    out = []
    now_us = 0.0
    poll = -1
    poll_t = 0.0

    def commit(s):
        nonlocal last_state, last_k, pos_sec, pos_est, t_edge_us, rate
        if s == last_state:
            return
        k = SECTOR_MAP[s]
        last_state = s
        if k < 0:
            return
        if last_k < 0:
            last_k = k
            pos_sec = k + 0.5
            pos_est = pos_sec
            t_edge_us = now_us
            return
        dk = k - last_k
        if dk > 3: dk -= 6
        elif dk < -3: dk += 6
        last_k = k
        if dk == 0:
            return
        edt = now_us - t_edge_us
        if edt < MIN_EDGE_US:
            return
        r = 0.0
        if edt < 200000:
            r = 1.0 / (edt * 1e-6)
        if r > RATE_CAP:
            return
        pos_sec = float(k) if dk > 0 else float(k + 1)
        pos_est = pos_sec
        t_edge_us = now_us
        rate = r if dk > 0 else -r

    for h in frames:
        for _ in range(int(round(frame_s / dt))):
            now_us += dt * 1e6
            # hall_update body
            if h == poll:
                poll_t += dt
            else:
                poll = h
                poll_t = 0.0
            if poll_t >= POLL_COMMIT_S:
                commit(h)
            since = now_us - t_edge_us
            if since > 2000:
                a = dt / 0.020
                rate += (0.0 - rate) * min(a, 0.2)
            pos = pos_sec
            if since < 1e6:
                fr = since * 1e-6 * rate
                fr = max(-1.0, min(1.0, fr))
                pos += fr
            pos_est = pos
            ang = (a0 - pos) * DEG60 if flip else (pos - a0) * DEG60
            thr = ang / PP
            if thr_prev is None:
                thr_prev = thr
            mech += math.remainder(thr - thr_prev, 2 * math.pi)
            thr_prev = thr
            out.append(mech)
    # sample at frame boundaries
    return [out[int(round((i + 1) * 0.005 / dt)) - 1] for i in range(len(frames))]

N = 260  # motion phase
best = None
for flip in (False, True):
    for a10 in range(0, 61, 5):
        a0 = a10 / 10.0
        sim = simulate(flip, a0, raw[:N])
        # compare delta pattern at state-change points
        err = sum(abs(sim[i] - capt[i]) for i in range(30, N))
        if best is None or err < best[0]:
            best = (err, flip, a0, sim)

err, flip, a0, sim = best
print("best fit: flip=%s a0=%.1f err=%.1f rad" % (flip, a0, err))
print("\n i  raw  capt_deg   sim_deg")
prev = None
for i in range(N):
    if raw[i] != prev:
        print("%3d  %d   %8.2f  %8.2f" % (i, raw[i], capt[i] * 57.29578, sim[i] * 57.29578))
        prev = raw[i]
