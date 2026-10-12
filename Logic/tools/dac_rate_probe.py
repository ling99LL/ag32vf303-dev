#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DAC DMA 吞吐上限探查：扫描频率 -> 实测输出 -> 推算有效采样周期"""
import serial, time, sys

PORT = sys.argv[1] if len(sys.argv) > 1 else 'COM33'
ser = serial.Serial(PORT, 115200, timeout=0.5)
ser.dtr = True; ser.rts = True
time.sleep(0.1)

def cmd5(op, v):
    ser.write(bytes([op, v & 0xFF, (v >> 8) & 0xFF, (v >> 16) & 0xFF, (v >> 24) & 0xFF]))

def read_exact(count, timeout=3.0):
    buf = bytearray(); t0 = time.time()
    while len(buf) < count and (time.time() - t0) < timeout:
        c = ser.read(count - len(buf))
        if c: buf += c
    return bytes(buf)

def read_frame(timeout=0.6):
    t0 = time.time()
    while time.time() - t0 < timeout:
        b = ser.read(1)
        if not b: continue
        if b[0] == 0xAA:
            ln = ser.read(1)
            if not ln: continue
            p = read_exact(ln[0], 0.5)
            if len(p) == ln[0]: return p
    return None

def info():
    cmd5(0x8C, 0); p = read_frame()
    return p

def capture(div, count=8192):
    ser.write(bytes([0x80, div & 0xFF, (div >> 8) & 0xFF, (div >> 16) & 0xFF, 0]))
    w = count // 4 - 1
    ser.write(bytes([0x81, w & 0xFF, (w >> 8) & 0xFF, w & 0xFF, (w >> 8) & 0xFF]))
    ser.write(bytes([0xC0, 0, 0, 0, 0])); ser.write(bytes([0xC1, 0, 0, 0, 0]))
    ser.reset_input_buffer(); ser.write(bytes([0x01]))
    return read_exact(count, 5.0 if div > 100 else 3.0)

# reset + handshake
for _ in range(3): ser.write(bytes([0x00]))
time.sleep(0.05); ser.reset_input_buffer()

# 找 DAC 通道
cmd5(0x84, 1 | (100 << 8) | (1 << 16))   # square, 100%, on
cmd5(0x85, 1000000)
time.sleep(0.05)
d = capture(0)
bit = max(range(4), key=lambda b: sum(1 for i in range(1, len(d)) if ((d[i] >> b) & 1) != ((d[i-1] >> b) & 1)))
print('信号通道: bit%d' % bit)

# 复现固件的 gen_compute（与 main.c 相同的算法）
MINPTS = {'sq': 2, 'sin': 8, 'saw': 4, 'tri': 8}

def gen_compute(f, minpts, rate_cap=25000000):
    f = min(f, rate_cap // minpts)
    lmax = rate_cap // f
    lmin = 1
    while f * lmin * 65536 < 100000000:
        lmin *= 2
    lmin = max(lmin, minpts)
    L = minpts
    cand = 2048
    while cand >= minpts:
        if cand < lmin: break
        if cand > lmax:
            cand >>= 1; continue
        L = cand; break
    div = (100000000 + (f * L) // 2) // (f * L)
    if div > 0: div -= 1
    div = min(div, 65535)
    actual = 100000000 // ((div + 1) * L)
    return L, div, actual

print()
print('%-9s %-7s %-6s %-10s %-12s %-12s %-8s' % ('请求f', '表长L', 'div', '固件actual', '测量周期', '理论周期', '状态'))
print('-' * 78)
freqs = [2500000, 1500000, 1000000, 700000, 500000, 350000, 250000, 170000, 100000, 50000, 20000, 10000, 5000, 1000]
for f in freqs:
    cmd5(0x85, f); time.sleep(0.03)
    p = info()
    actual = p[8] | p[9] << 8 | p[10] << 16 | p[11] << 24
    L, div, _ = gen_compute(f, 2)
    # 采样率 ≈ 100 × 目标频率（每周期 ~100 个采样点），钳制在 100kSa/s .. 100MSa/s
    target_rate = max(100e3, min(100e6, f * 100.0))
    sdiv = int(round(100e6 / target_rate)) - 1
    sdiv = max(0, min(9999, sdiv))
    count = 8192
    d = capture(sdiv, count)
    vals = [(x >> bit) & 1 for x in d]
    edges = sum(1 for i in range(1, len(vals)) if vals[i] != vals[i - 1])
    window = count / (100e6 / (sdiv + 1))
    f_meas = (edges / 2.0) / window if edges >= 2 else 0
    # 有效采样周期（100MHz 时钟周期数）
    cyc = (100e6 / (f_meas * L)) if f_meas > 0 else 0
    print('%-9d %-7d %-6d %-10d %-12.0f %-12s %s' % (
        f, L, div, actual, f_meas,
        '%.1f cyc' % cyc if cyc else '-',
        'OK' if f_meas and abs(f_meas - actual) / actual < 0.08 else '偏离'))

cmd5(0x84, 0 | (100 << 8) | 0)  # 关闭
ser.close()
