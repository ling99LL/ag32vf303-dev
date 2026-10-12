#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AG32 信号发生器 —— 板级回环测试（Loopback Test）
====================================================
针对 PIN_x ↔ 任一 CH 输入 的跳线，自动识别被测输出引脚并完成闭环验证。

当前默认场景（跳线 PIN_10 ↔ PIN_11）:
  PIN_11 (DAC0 模拟输出)  ->  PIN_10 (bit3 / 板级 CH4 输入)
  验证: DAC 方波扫频 / 正弦 / 锯齿 / 三角 / 占空比 / 幅度 / 关闭静默

用法: python loopback_test.py [COM端口]      (默认 COM33)
"""
import serial
import time
import sys

PORT = sys.argv[1] if len(sys.argv) > 1 else 'COM33'

GEN_OP_WAVE = 0x84
GEN_OP_FREQ = 0x85
GEN_OP_SQ_FREQ = 0x8A
GEN_OP_GET_INFO = 0x8C

CH_NAMES = ['bit0/PIN_7(板级CH1)', 'bit1/PIN_8(板级CH2)', 'bit2/PIN_9(板级CH3)', 'bit3/PIN_10(板级CH4)']
WAVE_NAMES = {0: '正弦', 1: '方波', 2: '锯齿', 3: '三角'}

results = []

def check(name, ok, detail=''):
    tag = 'PASS' if ok else 'FAIL'
    results.append((name, ok))
    print('  [%s] %s %s' % (tag, name, ('- ' + detail) if detail else ''))
    return ok

def cmd5(ser, op, val32):
    ser.write(bytes([op, val32 & 0xFF, (val32 >> 8) & 0xFF, (val32 >> 16) & 0xFF, (val32 >> 24) & 0xFF]))

def read_exact(ser, count, timeout=3.0):
    buf = bytearray()
    t0 = time.time()
    while len(buf) < count and (time.time() - t0) < timeout:
        chunk = ser.read(count - len(buf))
        if chunk:
            buf += chunk
    return bytes(buf)

def read_frame(ser, timeout=0.6):
    t0 = time.time()
    while time.time() - t0 < timeout:
        b = ser.read(1)
        if not b:
            continue
        if b[0] == 0xAA:
            ln = ser.read(1)
            if not ln:
                continue
            payload = read_exact(ser, ln[0], 0.5)
            if len(payload) == ln[0]:
                return payload
    return None

def get_info(ser):
    cmd5(ser, GEN_OP_GET_INFO, 0)
    p = read_frame(ser)
    if not p or len(p) < 20:
        return None
    return {
        'ver': (p[0], p[1]), 'type': p[2], 'amp': p[3],
        'freq': p[4] | p[5] << 8 | p[6] << 16 | p[7] << 24,
        'actual': p[8] | p[9] << 8 | p[10] << 16 | p[11] << 24,
        'flags': p[12], 'log2L': p[13],
    }

def capture(ser, div, count=8192):
    ser.write(bytes([0x80, div & 0xFF, (div >> 8) & 0xFF, (div >> 16) & 0xFF, 0x00]))
    words = count // 4 - 1
    ser.write(bytes([0x81, words & 0xFF, (words >> 8) & 0xFF, words & 0xFF, (words >> 8) & 0xFF]))
    ser.write(bytes([0xC0, 0, 0, 0, 0]))
    ser.write(bytes([0xC1, 0, 0, 0, 0]))
    ser.reset_input_buffer()
    ser.write(bytes([0x01]))
    return read_exact(ser, count, 5.0 if div > 100 else 3.0)

def scan(data):
    out = []
    for bit in range(4):
        vals = [(b >> bit) & 1 for b in data]
        hi = sum(vals)
        edges = sum(1 for i in range(1, len(vals)) if vals[i] != vals[i - 1])
        out.append({'bit': bit, 'hi': hi, 'lo': len(vals) - hi, 'edges': edges})
    return out

def report_scan(scans):
    for s in scans:
        if s['edges'] >= 3:
            print('      %-22s 边沿=%5d 高=%4d/低=%4d' % (CH_NAMES[s['bit']], s['edges'], s['hi'], s['lo']))
        # 静态通道不单独打印，保持简洁

def set_wave(ser, wtype, amp, en):
    cmd5(ser, GEN_OP_WAVE, (wtype & 3) | ((amp & 0xFF) << 8) | ((en & 1) << 16))

def main():
    print('=' * 74)
    print('  AG32 信号发生器 回环测试 (Loopback, port=%s)' % PORT)
    print('  预期跳线: PIN_11 (DAC输出) <-> PIN_10 (bit3/CH4); 脚本自动识别实际通道')
    print('=' * 74)

    ser = serial.Serial(PORT, 115200, timeout=0.5)
    ser.dtr = True
    ser.rts = True
    time.sleep(0.1)

    # ---------- [0] 握手 ----------
    print('\n[0] 通信握手')
    ser.reset_input_buffer()
    for _ in range(3):
        ser.write(bytes([0x00]))
    time.sleep(0.05)
    ser.reset_input_buffer()
    ser.write(bytes([0x02]))
    probe = read_exact(ser, 4, 1.0)
    check('SUMP ID 应答', probe == b'1ALS', '应答=%r' % probe)
    info = get_info(ser)
    if not check('GET_INFO 应答', info is not None):
        ser.close()
        return
    print('      固件 v%d.%d flags=0x%02X (gen_en=%d sq_sel=%d)' % (
        info['ver'][0], info['ver'][1], info['flags'], info['flags'] & 1, (info['flags'] >> 1) & 1))

    # ---------- [1] 基线扫描（DAC 关） ----------
    print('\n[1] 基线扫描 (DAC 关闭, PIN_5 方波源) @100MSa/s')
    data = capture(ser, div=0, count=8192)
    scans = scan(data)
    report_scan(scans)
    p5_bit = next((s['bit'] for s in scans if s['edges'] >= 6), None)
    ch4_quiet = scans[3]['edges'] < 3
    if p5_bit is None:
        check('基线: CH1~CH4 全静态（无 PIN_5 跳线干扰）', ch4_quiet,
              '4 通道均无活动' if all(s['edges'] < 3 for s in scans) else '')
    else:
        print('      [注意] 检测到 PIN_5 数字方波跳线在 %s（本脚本将聚焦 DAC 路径）' % CH_NAMES[p5_bit])

    # ---------- [2] DAC 路径发现 ----------
    print('\n[2] DAC 路径发现 (PIN_11 方波 1MHz 使能) @100MSa/s')
    set_wave(ser, 1, 100, 1)
    cmd5(ser, GEN_OP_FREQ, 1000000)
    time.sleep(0.05)
    info = get_info(ser)
    check('DAC 使能 (1MHz 方波)', info and (info['flags'] & 1) == 1,
          'actual=%dHz' % info['actual'] if info else '')
    data = capture(ser, div=0, count=8192)
    scans = scan(data)
    report_scan(scans)
    dac_bit = next((s['bit'] for s in scans if s['edges'] >= 40), None)
    if not check('检测到 DAC 输出回路', dac_bit is not None,
                 '通道 = %s' % CH_NAMES[dac_bit] if dac_bit is not None else
                 '未发现活动通道 — 请确认跳线 PIN_11 -> 任一 CH 输入'):
        set_wave(ser, 0, 100, 0)
        ser.close()
        print('\n  [中止] 回环未接通，后续测试无法进行。（板子已恢复：DAC 关）')
        return
    if dac_bit == 3:
        print('      (信号位于 bit3/PIN_10，与 10-11 跳线预期一致)')
    else:
        print('      [注意] 信号在 %s，与 10-11 预期(bit3/PIN_10)不符，请确认跳线位置' % CH_NAMES[dac_bit])

    # ---------- [3] DAC 方波扫频 ----------
    print('\n[3] DAC 方波扫频（实测频率 vs 固件回报值）')
    cases = [
        ('10 kHz', 10000, 99),     # 1 MSa/s,  窗口 8.192ms
        ('100 kHz', 100000, 0),    # 100 MSa/s, 窗口 81.92us
        ('1 MHz', 1000000, 0),
        ('2.5 MHz', 2500000, 0),
    ]
    for label, f, div in cases:
        cmd5(ser, GEN_OP_FREQ, f)
        time.sleep(0.03)
        info = get_info(ser)
        actual = info['actual']
        count = 8192
        data = capture(ser, div=div, count=count)
        s = scan(data)[dac_bit]
        window = count / (100e6 / (div + 1))
        f_est = (s['edges'] / 2.0) / window if s['edges'] >= 2 else 0.0
        ok = s['edges'] >= 6 and abs(f_est - actual) <= max(0.12 * actual, 2.0 / window)
        check('方波 %-7s (设定 %-7d 实际 %-8d)' % (label, f, actual), ok,
              '边沿=%5d 实测≈%9.1f Hz 误差=%5.1f%%' % (s['edges'], f_est,
              abs(f_est - actual) / actual * 100 if actual else 100))

    # ---------- [4] 四种波形 @100kHz ----------
    print('\n[4] 四波形对比 @100kHz（相同通道）')
    for wtype in (0, 1, 2, 3):
        set_wave(ser, wtype, 100, 1)
        cmd5(ser, GEN_OP_FREQ, 100000)
        time.sleep(0.03)
        info = get_info(ser)
        data = capture(ser, div=0, count=8192)
        s = scan(data)[dac_bit]
        window = 8192 / 100e6
        f_est = (s['edges'] / 2.0) / window if s['edges'] >= 2 else 0.0
        ok = s['edges'] >= 6 and abs(f_est - info['actual']) <= max(0.12 * info['actual'], 2.0 / window)
        check('DAC %s @100kHz' % WAVE_NAMES[wtype], ok,
              '边沿=%3d 实测≈%8.0f Hz 高占比=%2.0f%%' % (s['edges'], f_est, s['hi'] / 81.92))

    # ---------- [5] 属性检查 ----------
    print('\n[5] 属性检查（方波 1MHz）')
    set_wave(ser, 1, 100, 1)
    cmd5(ser, GEN_OP_FREQ, 1000000)
    time.sleep(0.03)
    data = capture(ser, div=0, count=8192)
    s = scan(data)[dac_bit]
    duty = s['hi'] / 8192.0
    check('占空比 ≈50%%', abs(duty - 0.5) < 0.06, '高占比=%.1f%%' % (duty * 100))

    set_wave(ser, 1, 50, 1)     # 幅度 50%
    time.sleep(0.03)
    data = capture(ser, div=0, count=8192)
    s = scan(data)[dac_bit]
    check('幅度 50% 仍有效输出（阈值穿越）', s['edges'] >= 80, '边沿=%d' % s['edges'])

    # ---------- [6] 关闭静默 ----------
    print('\n[6] DAC 关闭验证')
    set_wave(ser, 0, 100, 0)
    time.sleep(0.05)
    data = capture(ser, div=0, count=8192)
    s = scan(data)[dac_bit]
    check('DAC 关闭后通道静默', s['edges'] < 3, '边沿=%d' % s['edges'])
    info = get_info(ser)
    check('协议确认输出已关', info and (info['flags'] & 1) == 0)

    # ---------- [7] 恢复默认 ----------
    print('\n[7] 恢复默认状态')
    set_wave(ser, 0, 100, 0)
    cmd5(ser, GEN_OP_SQ_FREQ, 100000)   # PIN_5 回 100kHz
    for _ in range(2):
        ser.write(bytes([0x00]))
    time.sleep(0.05)
    info = get_info(ser)
    check('恢复: DAC 关 / PIN_5 方波 100kHz', info and (info['flags'] & 1) == 0 and (info['flags'] >> 1) & 1 == 1,
          'flags=0x%02X' % info['flags'] if info else '')
    ser.close()

    # ---------- 汇总 ----------
    print('\n' + '=' * 74)
    passed = sum(1 for _, ok in results if ok)
    failed = [n for n, ok in results if not ok]
    print('  回环测试: %d 通过 / %d 失败 (共 %d 项)' % (passed, len(results) - passed, len(results)))
    if failed:
        print('  失败项:')
        for n in failed:
            print('    - %s' % n)
    print('=' * 74)

if __name__ == '__main__':
    main()
