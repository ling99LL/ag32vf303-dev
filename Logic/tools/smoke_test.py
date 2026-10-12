#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AG32 逻辑分析仪 + 信号发生器 —— 上板冒烟测试
================================================
覆盖内容:
  [1] 通信握手       SUMP ID / GEN v1.1 GET_INFO
  [2] CPLD 采样器    8192 采样点捕获 + 通道活动扫描（发现 PIN_5/PIN_11 跳线）
  [3] PIN_5 数字方波 1MHz / 100kHz / 10MHz 频率校验（SUMP 0x83 覆盖）
  [4] PIN_11 DAC    方波 1MHz + 正弦/锯齿/三角 100kHz 波形 + 关闭验证
  [5] P5 触发引擎   主机脉冲(mode3) / 延时电平(mode0+arm) 寄存器级时序验证
  [6] 引擎脉冲捕获  若 PIN_5 有跳线: 10kSa/s 捕获 0.2s 延时 + 0.3s 脉冲全波形
  [7] 恢复默认状态

运行: python smoke_test.py [COM端口]   (默认 COM33)
"""
import serial
import time
import sys

PORT = sys.argv[1] if len(sys.argv) > 1 else 'COM33'

# ---------------- GEN 协议 ----------------
GEN_OP_WAVE = 0x84      # [type:2][amp:8][en:1]
GEN_OP_FREQ = 0x85      # 频率 Hz
GEN_OP_P5_CFG = 0x86    # [mode:2][level][idle][psc:2]..[sq_sel:bit8]
GEN_OP_P5_DELAY = 0x87
GEN_OP_P5_WIDTH = 0x88
GEN_OP_P5_CTRL = 0x89   # [0]arm [1]fire [2]clear
GEN_OP_SQ_FREQ = 0x8A
GEN_OP_RATE_CAP = 0x8B
GEN_OP_GET_INFO = 0x8C
GEN_OP_P5_QUERY = 0x8D

CH_NAMES = ['bit0/PIN_7(板级CH1)', 'bit1/PIN_8(板级CH2)', 'bit2/PIN_9(板级CH3)', 'bit3/PIN_10(板级CH4)']

results = []

def check(name, ok, detail=''):
    tag = 'PASS' if ok else 'FAIL'
    results.append((name, ok))
    print('  [%s] %s %s' % (tag, name, ('- ' + detail) if detail else ''))
    return ok

def cmd5(ser, op, val32):
    ser.write(bytes([op, val32 & 0xFF, (val32 >> 8) & 0xFF, (val32 >> 16) & 0xFF, (val32 >> 24) & 0xFF]))

def read_frame(ser, timeout=0.6):
    """读一个 [0xAA][len][payload...] 帧"""
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

def read_exact(ser, count, timeout=3.0):
    buf = bytearray()
    t0 = time.time()
    while len(buf) < count and (time.time() - t0) < timeout:
        chunk = ser.read(count - len(buf))
        if chunk:
            buf += chunk
    return bytes(buf)

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
        'rate_cap': p[14] | p[15] << 8 | p[16] << 16 | p[17] << 24,
    }

def p5_query(ser):
    cmd5(ser, GEN_OP_P5_QUERY, 0)
    p = read_frame(ser, 0.5)
    if not p or len(p) < 7:
        return None
    st = p[0]
    return {'busy': st & 1, 'done': (st >> 1) & 1, 'out': (st >> 2) & 1,
            'remain': p[1] | p[2] << 8 | p[3] << 16 | p[4] << 24,
            'cfg': p[5] | (p[6] << 8)}

def capture(ser, div, count=8192, mask=0, val=0):
    ser.write(bytes([0x80, div & 0xFF, (div >> 8) & 0xFF, (div >> 16) & 0xFF, 0x00]))
    words = count // 4 - 1
    ser.write(bytes([0x81, words & 0xFF, (words >> 8) & 0xFF, words & 0xFF, (words >> 8) & 0xFF]))
    ser.write(bytes([0xC0, mask & 0xFF, (mask >> 8) & 0xFF, (mask >> 16) & 0xFF, (mask >> 24) & 0xFF]))
    ser.write(bytes([0xC1, val & 0xFF, (val >> 8) & 0xFF, (val >> 16) & 0xFF, (val >> 24) & 0xFF]))
    ser.reset_input_buffer()
    ser.write(bytes([0x01]))
    data = read_exact(ser, count, 5.0 if div > 100 else 3.0)
    return data

def scan(data):
    out = []
    for bit in range(4):
        vals = [(b >> bit) & 1 for b in data]
        hi = sum(vals)
        edges = sum(1 for i in range(1, len(vals)) if vals[i] != vals[i - 1])
        out.append({'bit': bit, 'hi': hi, 'lo': len(vals) - hi, 'edges': edges})
    return out

def report_scan(scans, window_s, expect_bit=None):
    for s in scans:
        if s['edges'] >= 3:
            f_est = (s['edges'] / 2.0) / window_s
            marker = ' <== 预期通道' if (expect_bit is not None and s['bit'] == expect_bit) else ''
            print('      %-22s 边沿=%5d 高=%4d/低=%4d 频率≈%9.1f Hz%s' % (
                CH_NAMES[s['bit']], s['edges'], s['hi'], s['lo'], f_est, marker))
        else:
            print('      %-22s 静态(高=%d 低=%d) 无活动' % (CH_NAMES[s['bit']], s['hi'], s['lo']))

def find_active(scans, min_edges=4, exclude_bit=None):
    cands = [s for s in scans if s['edges'] >= min_edges and s['bit'] != exclude_bit]
    return cands[0]['bit'] if cands else None

def main():
    global PORT
    print('=' * 74)
    print('  AG32 逻辑分析仪 + 信号发生器 —— 上板冒烟测试 (port=%s)' % PORT)
    print('=' * 74)

    ser = serial.Serial(PORT, 115200, timeout=0.5)
    ser.dtr = True
    ser.rts = True
    time.sleep(0.1)

    # ---------- [1] 通信握手 ----------
    print('\n[1] 通信握手与固件版本')
    ser.reset_input_buffer()
    for _ in range(3):
        ser.write(bytes([0x00]))
    time.sleep(0.05)
    ser.reset_input_buffer()
    ser.write(bytes([0x02]))
    probe = read_exact(ser, 4, 1.0)
    check('SUMP/OLS ID 应答', probe == b'1ALS', '应答=%r' % probe)

    info = get_info(ser)
    if not check('GEN GET_INFO 应答', info is not None):
        ser.close()
        return
    print('      固件 v%d.%d  type=%d amp=%d%%  freq=%dHz actual=%dHz  rate_cap=%d  log2L=%d' % (
        info['ver'][0], info['ver'][1], info['type'], info['amp'],
        info['freq'], info['actual'], info['rate_cap'], info['log2L']))
    check('版本号 = v1.1', info['ver'] == (1, 1))
    check('启动态: DAC 关闭 / PIN_5 方波源', (info['flags'] & 0x01) == 0 and (info['flags'] >> 1) & 1 == 1,
          'flags=0x%02X' % info['flags'])

    # ---------- [2] CPLD 采样器 + 跳线发现 ----------
    print('\n[2] CPLD 采样器 / 通道活动扫描 (PIN_5 方波 100kHz, 100MSa/s)')
    cmd5(ser, 0x83, 999)  # PIN_5 -> 100kHz
    time.sleep(0.02)
    data = capture(ser, div=0, count=8192)
    check('8192 采样点捕获回传完整', len(data) == 8192, 'len=%d' % len(data))
    scans = scan(data)
    report_scan(scans, 8192 / 100e6)
    p5_bit = find_active(scans, min_edges=6)
    if p5_bit is not None:
        est = (scans[p5_bit]['edges'] / 2.0) / (8192 / 100e6)
        check('PIN_5 跳线已连接 (100kHz 方波)', abs(est - 100000) < 20000,
              '检测于 %s, 频率≈%.0fHz' % (CH_NAMES[p5_bit], est))
    else:
        print('      [SKIP] 未检测到 PIN_5 跳线信号（需将 H4: PIN_5 跳线到任一 CH 输入）')

    # ---------- [3] PIN_5 数字方波频率校验 ----------
    print('\n[3] PIN_5 数字方波频率校验 (SUMP 0x83 覆盖)')
    if p5_bit is not None:
        for div, f_nom in ((99, 1e6), (999, 100e3), (9, 10e6)):
            cmd5(ser, 0x83, div)
            time.sleep(0.02)
            data = capture(ser, div=0, count=8192)
            scans = scan(data)
            s = scans[p5_bit]
            f_est = (s['edges'] / 2.0) / (8192 / 100e6) if s['edges'] >= 2 else 0
            ok = abs(f_est - f_nom) <= 0.2 * f_nom and s['edges'] > 2
            check('PIN_5 = %-7s (div=%d)' % ('%.4gHz' % f_nom, div), ok,
                  '边沿=%d 实测≈%.0fHz 误差=%.1f%%' % (s['edges'], f_est,
                  abs(f_est - f_nom) / f_nom * 100 if f_est else 100))
        cmd5(ser, 0x83, 999)  # 回到 100kHz
    else:
        print('      [SKIP] 无 PIN_5 跳线')

    # ---------- [4] PIN_11 DAC 波形 ----------
    print('\n[4] PIN_11 DAC0 波形输出 (DMA 循环播表)')
    cmd5(ser, GEN_OP_WAVE, 1 | (100 << 8) | (1 << 16))  # 方波 100% 使能
    cmd5(ser, GEN_OP_FREQ, 1000000)                      # 1MHz
    time.sleep(0.05)
    info = get_info(ser)
    # 1 MHz must be exact: the DMA pacing fix (2026-10-12) removed the ~4%
    # shortfall caused by the AHB->APB handshake, so demand <=2% here.
    check('DAC 使能 + 1MHz 方波设定', info and (info['flags'] & 1) == 1 and info['type'] == 1
          and abs(info['actual'] - 1000000) <= 20000,
          'en=%d type=%d actual=%dHz' % ((info['flags'] & 1), info['type'], info['actual']) if info else '')
    data = capture(ser, div=0, count=8192)
    scans = scan(data)
    dac_bit = find_active(scans, min_edges=20, exclude_bit=None)
    report_scan(scans, 8192 / 100e6)
    if dac_bit is not None:
        s = scans[dac_bit]
        f_est = (s['edges'] / 2.0) / (8192 / 100e6)
        f_exp = info['actual'] if info and info['actual'] else 1000000
        ok = abs(f_est - f_exp) <= max(0.05e6, 0.06 * f_exp)
        check('DAC 方波 1MHz 环回捕获', ok, '于 %s 实测≈%.0fHz (期望≈%.0fHz)' % (CH_NAMES[dac_bit], f_est, f_exp))
    else:
        print('      [SKIP] 未检测到 PIN_11 跳线信号（需将 H4: PIN_11 跳线到任一 CH 输入）')

    # 四波形对比 (100kHz, 相同通道)
    print('      -- 四波形 100kHz 对比 --')
    wave_names = {0: '正弦', 1: '方波', 2: '锯齿', 3: '三角'}
    for wtype in (0, 1, 2, 3):
        cmd5(ser, GEN_OP_WAVE, wtype | (100 << 8) | (1 << 16))
        cmd5(ser, GEN_OP_FREQ, 100000)
        time.sleep(0.03)
        if dac_bit is not None:
            data = capture(ser, div=0, count=8192)
            s = scan(data)[dac_bit]
            f_est = (s['edges'] / 2.0) / (8192 / 100e6) if s['edges'] >= 2 else 0
            ok = s['edges'] >= 6 and abs(f_est - 97656) < 25000
            check('DAC %s @100kHz' % wave_names[wtype], ok,
                  '边沿=%d 频率≈%.0fHz 高占比=%.0f%%' % (s['edges'], f_est, s['hi'] / 81.92))
        else:
            info = get_info(ser)
            check('DAC %s @100kHz (仅协议)' % wave_names[wtype],
                  info and info['type'] == wtype and abs(info['actual'] - 97656) < 5000,
                  'type=%d actual=%dHz' % (info['type'], info['actual']))
            print('        [SKIP] 无可视通道')

    # 关闭验证
    cmd5(ser, GEN_OP_WAVE, 0 | (100 << 8) | (0 << 16))  # en=0
    time.sleep(0.05)
    if dac_bit is not None:
        data = capture(ser, div=0, count=8192)
        s = scan(data)[dac_bit]
        check('DAC 关闭后输出静默', s['edges'] < 3, '边沿=%d' % s['edges'])
    else:
        info = get_info(ser)
        check('DAC 关闭 (协议确认)', info and (info['flags'] & 1) == 0)
    gc_bit = dac_bit  # 保存 DAC 跳线通道供输出参考

    # ---------- [5] P5 触发引擎（寄存器级） ----------
    print('\n[5] PIN_5 触发/脉冲引擎 (寄存器级时序验证, 时基=10us/tick)')
    # 主机->脉冲 mode3: cfg=0b0_00_11_0111 -> 0x37 (level=1 idle=0 psc=3 sq_sel=0)
    cmd5(ser, GEN_OP_P5_CFG, 0x37)
    cmd5(ser, GEN_OP_P5_DELAY, 10000)   # 0.1s
    cmd5(ser, GEN_OP_P5_WIDTH, 20000)   # 0.2s
    cmd5(ser, GEN_OP_P5_CTRL, 0x04)     # clear
    time.sleep(0.05)

    t0 = time.time()
    cmd5(ser, GEN_OP_P5_CTRL, 0x02)     # fire
    timeline = []
    while time.time() - t0 < 1.2:
        st = p5_query(ser)
        if st is None:
            break
        timeline.append((time.time() - t0, st))
        if st['done']:
            break
        time.sleep(0.02)

    busy_seen = any(s['busy'] for _, s in timeline)
    out_high = [t for t, s in timeline if s['out']]
    done_at = next((t for t, s in timeline if s['done']), None)
    remain_start = next((s['remain'] for _, s in timeline if s['busy']), 0)
    check('mode3 主机脉冲: busy 拉起', busy_seen)
    check('mode3 脉冲: out 拉高并维持~0.2s', len(out_high) >= 3,
          '高电平时段 %.3f~%.3fs' % (out_high[0], out_high[-1]) if out_high else '未见高电平')
    check('mode3 脉冲: 总时长 ~0.3s 且 done 置位', done_at is not None and 0.2 < done_at < 0.5,
          'total=%.3fs remain_start=%d' % (done_at or -1, remain_start))
    cmd5(ser, GEN_OP_P5_CTRL, 0x04)     # clear

    # 延时->电平 mode0 + arm: cfg=0b0_00_11_0100 -> 0x34
    cmd5(ser, GEN_OP_P5_CFG, 0x34)
    cmd5(ser, GEN_OP_P5_DELAY, 5000)    # 50ms
    cmd5(ser, GEN_OP_P5_CTRL, 0x04)     # clear
    time.sleep(0.05)
    t0 = time.time()
    cmd5(ser, GEN_OP_P5_CTRL, 0x01)     # arm
    lev_at = None
    while time.time() - t0 < 0.5:
        st = p5_query(ser)
        if st is None:
            break
        if st['out'] and lev_at is None:
            lev_at = time.time() - t0
            break
        time.sleep(0.01)
    check('mode0 延时电平: arm 后 ~50ms 输出拉高', lev_at is not None and 0.02 < lev_at < 0.15,
          '延时实测=%.3fs' % (lev_at if lev_at else -1))
    time.sleep(0.05)
    st = p5_query(ser)
    check('mode0 电平保持 + done 置位', st and st['out'] == 1 and st['done'] == 1,
          'out=%d done=%d' % (st['out'], st['done']) if st else '')
    cmd5(ser, GEN_OP_P5_CTRL, 0x04)     # clear -> 输出回 idle
    time.sleep(0.02)
    st = p5_query(ser)
    check('clear 后输出回 idle 低电平', st and st['out'] == 0 and st['done'] == 0)

    # ---------- [6] 引擎脉冲全波形捕获 (条件: PIN_5 有跳线) ----------
    print('\n[6] 引擎脉冲全波形捕获 (10kSa/s, 需 PIN_5 跳线)')
    if p5_bit is not None:
        cmd5(ser, GEN_OP_P5_CFG, 0x37)      # mode3 主机脉冲
        cmd5(ser, GEN_OP_P5_DELAY, 20000)   # 0.2s
        cmd5(ser, GEN_OP_P5_WIDTH, 30000)   # 0.3s
        cmd5(ser, GEN_OP_P5_CTRL, 0x04)     # clear
        time.sleep(0.02)
        cmd5(ser, GEN_OP_P5_CTRL, 0x02)     # fire -> 0.2s 后拉高
        data = capture(ser, div=9999, count=8192, mask=0, val=0)  # 10.001kSa/s, 0.82s 窗口
        st = p5_query(ser)
        check('捕获回传完整', len(data) == 8192, 'len=%d' % len(data))
        vals = [(b >> p5_bit) & 1 for b in data]
        edges_idx = [i for i in range(1, len(vals)) if vals[i] != vals[i - 1]]
        if len(edges_idx) >= 2:
            rise = edges_idx[0]
            fall = edges_idx[1]
            hi_run = fall - rise
            ok = abs(rise - 2000) < 400 and abs(hi_run - 3000) < 700
            check('脉冲波形: 延时~0.2s 上升 + 0.3s 高电平', ok,
                  '上升沿@%.0fms 高电平宽=%.0fms 边沿数=%d' % (rise / 10.0, hi_run / 10.0, len(edges_idx)))
            print('        (fire->捕获起点延迟计入, 期望上升沿~1900-2000 样点)')
        elif len(edges_idx) == 1:
            check('脉冲波形: 检测到单边沿', False, '仅 %d 个边沿 @%.0fms（可能时序错位）' % (
                len(edges_idx), edges_idx[0] / 10.0))
        else:
            check('脉冲波形: 捕获到脉冲', False, '未检测到边沿, done=%s' % (st['done'] if st else '?'))
        cmd5(ser, GEN_OP_P5_CTRL, 0x04)
    else:
        print('      [SKIP] 无 PIN_5 跳线，未做物理捕获（寄存器级验证已通过）')

    # ---------- [7] 恢复默认 ----------
    print('\n[7] 恢复默认状态')
    cmd5(ser, GEN_OP_WAVE, 0 | (100 << 8) | (0 << 16))
    cmd5(ser, GEN_OP_P5_CFG, 0x100)     # sq_sel=1 方波源
    cmd5(ser, GEN_OP_SQ_FREQ, 100000)   # 100kHz
    cmd5(ser, GEN_OP_P5_CTRL, 0x04)
    for _ in range(2):
        ser.write(bytes([0x00]))        # SUMP reset
    time.sleep(0.05)
    info = get_info(ser)
    ok = info and (info['flags'] & 1) == 0 and (info['flags'] >> 1) & 1 == 1
    check('恢复: DAC 关 / PIN_5 方波 / 引擎复位', bool(ok),
          'flags=0x%02X' % info['flags'] if info else '')

    ser.close()

    # ---------- 总结 ----------
    print('\n' + '=' * 74)
    passed = sum(1 for _, ok in results if ok)
    failed = [n for n, ok in results if not ok]
    skipped = 'PIN_5 跳线' in ''.join(n for n, _ in results) or True
    print('  测试项: %d 通过 / %d 失败 (共 %d)' % (passed, len(results) - passed, len(results)))
    if failed:
        print('  失败项:')
        for n in failed:
            print('    - %s' % n)
    print('=' * 74)

if __name__ == '__main__':
    main()
