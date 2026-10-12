#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AG32 简易波形发生器上位机
================================
控制对象（通过 USB CDC 虚拟串口）:
  PIN_11 : DAC0 模拟波形输出 —— 正弦 / 方波 / 锯齿 / 三角，频率 1 Hz 起
  PIN_5  : 数字输出 —— 1 Hz..100 MHz 方波  或  延时触发/脉冲引擎

通信协议: SUMP 扩展帧（5 字节 = 操作码 + 32 位小端负载）
  0x84 GEN_WAVE    [7:0]波形 [15:8]幅度% [16]输出使能
  0x85 GEN_FREQ    32 位频率 (Hz)
  0x86 P5_CFG      [1:0]模式 [2]电平 [3]空闲电平 [5:4]时基 [8]方波选通
  0x87 P5_DELAY    32 位延时 (tick)
  0x88 P5_WIDTH    32 位脉宽 (tick)
  0x89 P5_CTRL     [0]布防 [1]触发 [2]复位
  0x8A SQ_FREQ     32 位方波频率 (Hz)
  0x8B GEN_RATE    DAC 采样率上限 (Hz)
  0x8C GET_INFO    读取状态 -> [0xAA][20][载荷]
  0x8D P5_QUERY    读取触发状态 -> [0xAA][7][载荷]

运行: 双击 run_wavegen.bat（或 python wavegen_gui.py）
依赖: Python 3.8+ / tkinter / pyserial
"""

import struct
import sys
import threading
import time

import serial
import serial.tools.list_ports

import tkinter as tk
from tkinter import ttk, messagebox

# --------------------------------------------------------------------------
# 协议常量
# --------------------------------------------------------------------------
OP_WAVE      = 0x84
OP_FREQ      = 0x85
OP_P5_CFG    = 0x86
OP_P5_DELAY  = 0x87
OP_P5_WIDTH  = 0x88
OP_P5_CTRL   = 0x89
OP_SQ_FREQ   = 0x8A
OP_RATE_CAP  = 0x8B
OP_GET_INFO  = 0x8C
OP_P5_QUERY  = 0x8D
RESP_SYNC    = 0xAA

WAVE_NAMES = ["正弦 (Sine)", "方波 (Square)", "锯齿 (Sawtooth)", "三角 (Triangle)"]
# 每种波形每周期最少采样点数: 正弦/方波/锯齿/三角（决定各波形的最高频率）
WAVE_MIN_PTS = [8, 2, 4, 8]
DEFAULT_RATE_CAP = 5_000_000      # 默认 DAC 采样率上限 5 MSa/s（板载固件同值；连接后由设备回报覆盖）
TICK_BASE_NS = 10.0               # 触发引擎基础时基 10 ns
PRESCALES = [1, 10, 100, 1000]    # 时基倍率 10ns * {1,10,100,1000}

P5_MODE_NAMES = [
    "延时后输出电平 (延迟 -> 电平)",
    "延时后输出脉冲 (延迟 -> 脉冲)",
    "上位机触发输出电平",
    "上位机触发输出脉冲",
]

UNIT_MULT = {"Hz": 1, "kHz": 1e3, "MHz": 1e6}
TIME_MULT_NS = {"ns": 1.0, "us": 1e3, "ms": 1e6, "s": 1e9}


def fmt_freq(hz):
    if hz >= 1e6:
        return f"{hz / 1e6:.6g} MHz"
    if hz >= 1e3:
        return f"{hz / 1e3:.6g} kHz"
    return f"{hz:.6g} Hz"


def fmt_time_ns(ns):
    if ns >= 1e9:
        return f"{ns / 1e9:.6g} s"
    if ns >= 1e6:
        return f"{ns / 1e6:.6g} ms"
    if ns >= 1e3:
        return f"{ns / 1e3:.6g} us"
    return f"{ns:.6g} ns"


def encode_time(t_ns):
    """把时间（纳秒）编码为 (prescale, ticks)：选能容纳的最小时基。"""
    for p in range(4):
        tick = TICK_BASE_NS * PRESCALES[p]
        if t_ns / tick <= 0xFFFFFFFF:
            ticks = int(round(t_ns / tick))
            return p, min(max(ticks, 0), 0xFFFFFFFF)
    return 3, 0xFFFFFFFF


class WaveGenApp:
    def __init__(self, root):
        self.root = root
        self.root.title("AG32 波形发生器上位机  (PIN_11 模拟波形 / PIN_5 触发·方波)")
        self.ser = None
        self.rx_thread = None
        self.rx_run = False
        self.rx_queue = []
        self.rx_buf = bytearray()

        # 设备状态
        self.dev_connected = False
        self.info = None              # GET_INFO 缓存
        self.p5_status = None         # 最近一次 P5_QUERY 结果
        self.wave_type = 0
        self.wave_amp = 100
        self.wave_en = False
        self.rate_cap = DEFAULT_RATE_CAP

        self._build_ui()
        self.root.after(50, self._pump_rx)
        self.root.after(400, self._poll_p5)
        self.refresh_ports()

    # ------------------------------------------------------------------ UI --
    def _build_ui(self):
        pad = dict(padx=6, pady=3)

        # ---- 串口连接区 ----
        top = ttk.LabelFrame(self.root, text="串口连接 (USB CDC，物联逻辑分析仪 COM 口)")
        top.pack(fill="x", padx=8, pady=6)
        self.port_var = tk.StringVar()
        self.port_cb = ttk.Combobox(top, textvariable=self.port_var, width=18, state="readonly")
        self.port_cb.grid(row=0, column=0, **pad)
        ttk.Button(top, text="刷新", command=self.refresh_ports, width=6).grid(row=0, column=1, **pad)
        self.btn_conn = ttk.Button(top, text="连接", command=self.toggle_connect, width=8)
        self.btn_conn.grid(row=0, column=2, **pad)
        self.status_var = tk.StringVar(value="未连接")
        ttk.Label(top, textvariable=self.status_var, foreground="#a33").grid(row=0, column=3, sticky="w", **pad)

        body = ttk.Frame(self.root)
        body.pack(fill="both", expand=True, padx=8)
        left = ttk.Frame(body)
        left.pack(side="left", fill="both", expand=True)
        right = ttk.Frame(body)
        right.pack(side="right", fill="both", expand=True)

        # ---- PIN_11 波形发生器 ----
        wf = ttk.LabelFrame(left, text="PIN_11  模拟波形输出 (DAC0)")
        wf.pack(fill="x")
        self.wave_var = tk.IntVar(value=0)
        for i, name in enumerate(WAVE_NAMES):
            ttk.Radiobutton(wf, text=name, variable=self.wave_var, value=i,
                            command=self._preview).grid(row=i // 2, column=i % 2, sticky="w", **pad)

        self.canvas = tk.Canvas(wf, width=330, height=96, bg="#fbfbfb",
                                highlightthickness=1, highlightbackground="#bbb")
        self.canvas.grid(row=2, column=0, columnspan=2, padx=8, pady=4)
        self.canvas.bind("<Configure>", lambda e: self._preview())

        rf = ttk.Frame(wf)
        rf.grid(row=3, column=0, columnspan=2, sticky="we", **pad)
        ttk.Label(rf, text="频率:").pack(side="left")
        self.freq_var = tk.StringVar(value="100")
        ttk.Entry(rf, textvariable=self.freq_var, width=10).pack(side="left", padx=3)
        self.funit_var = tk.StringVar(value="kHz")
        ttk.Combobox(rf, textvariable=self.funit_var, values=list(UNIT_MULT),
                     width=5, state="readonly").pack(side="left")
        ttk.Label(rf, text="  幅度:").pack(side="left")
        self.amp_var = tk.IntVar(value=100)
        ttk.Scale(rf, from_=1, to=100, variable=self.amp_var, command=lambda v: self._preview()).pack(
            side="left", fill="x", expand=True, padx=3)
        ttk.Label(rf, textvariable=self.amp_var, width=3).pack(side="left")

        af = ttk.Frame(wf)
        af.grid(row=4, column=0, columnspan=2, sticky="we", **pad)
        self.enable_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(af, text="输出使能", variable=self.enable_var).pack(side="left")
        ttk.Button(af, text="应用波形设置", command=self.apply_wave).pack(side="left", padx=8)
        self.actual_var = tk.StringVar(value="实际输出: --")
        ttk.Label(af, textvariable=self.actual_var).pack(side="left", padx=8)

        cap = ttk.Frame(wf)
        cap.grid(row=5, column=0, columnspan=2, sticky="we", **pad)
        ttk.Label(cap, text="采样率上限:").pack(side="left")
        self.cap_var = tk.StringVar(value="25")
        ttk.Entry(cap, textvariable=self.cap_var, width=6).pack(side="left", padx=3)
        ttk.Label(cap, text="MHz  (方波/锯齿/三角/正弦 最高 = 上限/2/4/8/8)").pack(side="left")
        ttk.Button(cap, text="应用", command=self.apply_rate_cap, width=5).pack(side="left", padx=4)

        # ---- PIN_5 触发/方波 ----
        p5 = ttk.LabelFrame(right, text="PIN_5  数字输出 (触发引擎 / 方波)")
        p5.pack(fill="x")
        sf = ttk.Frame(p5)
        sf.pack(fill="x", **pad)
        ttk.Label(sf, text="输出源:").pack(side="left")
        self.p5_src_var = tk.StringVar(value="square")
        ttk.Radiobutton(sf, text="数字方波", variable=self.p5_src_var, value="square",
                        command=self._p5_src_changed).pack(side="left", padx=4)
        ttk.Radiobutton(sf, text="触发/脉冲引擎", variable=self.p5_src_var, value="engine",
                        command=self._p5_src_changed).pack(side="left", padx=4)

        sqf = ttk.Frame(p5)
        sqf.pack(fill="x", **pad)
        ttk.Label(sqf, text="方波频率:").pack(side="left")
        self.sqf_var = tk.StringVar(value="100")
        ttk.Entry(sqf, textvariable=self.sqf_var, width=10).pack(side="left", padx=3)
        self.sqfunit_var = tk.StringVar(value="kHz")
        ttk.Combobox(sqf, textvariable=self.sqfunit_var, values=list(UNIT_MULT),
                     width=5, state="readonly").pack(side="left")
        ttk.Button(sqf, text="输出方波 1Hz-100MHz", command=self.apply_square).pack(side="left", padx=6)

        self.engine_frame = ttk.Frame(p5)
        self.engine_frame.pack(fill="x")
        mf = ttk.Frame(self.engine_frame)
        mf.pack(fill="x", **pad)
        ttk.Label(mf, text="触发模式:").pack(side="left")
        self.p5_mode_var = tk.StringVar(value=P5_MODE_NAMES[0])
        ttk.Combobox(mf, textvariable=self.p5_mode_var, values=P5_MODE_NAMES,
                     width=26, state="readonly").pack(side="left", padx=3)

        lf = ttk.Frame(self.engine_frame)
        lf.pack(fill="x", **pad)
        ttk.Label(lf, text="输出电平:").pack(side="left")
        self.p5_level_var = tk.StringVar(value="高")
        ttk.Combobox(lf, textvariable=self.p5_level_var, values=["高", "低"],
                     width=4, state="readonly").pack(side="left", padx=3)
        ttk.Label(lf, text="  空闲电平:").pack(side="left")
        self.p5_idle_var = tk.StringVar(value="低")
        ttk.Combobox(lf, textvariable=self.p5_idle_var, values=["低", "高"],
                     width=4, state="readonly").pack(side="left", padx=3)

        tf = ttk.Frame(self.engine_frame)
        tf.pack(fill="x", **pad)
        ttk.Label(tf, text="延时:").pack(side="left")
        self.p5_delay_var = tk.StringVar(value="100")
        ttk.Entry(tf, textvariable=self.p5_delay_var, width=10).pack(side="left", padx=3)
        self.p5_delayunit_var = tk.StringVar(value="us")
        ttk.Combobox(tf, textvariable=self.p5_delayunit_var, values=list(TIME_MULT_NS),
                     width=4, state="readonly").pack(side="left")
        ttk.Label(tf, text=" 脉宽:").pack(side="left")
        self.p5_width_var = tk.StringVar(value="10")
        ttk.Entry(tf, textvariable=self.p5_width_var, width=10).pack(side="left", padx=3)
        self.p5_widthunit_var = tk.StringVar(value="us")
        ttk.Combobox(tf, textvariable=self.p5_widthunit_var, values=list(TIME_MULT_NS),
                     width=4, state="readonly").pack(side="left")

        bf = ttk.Frame(self.engine_frame)
        bf.pack(fill="x", **pad)
        ttk.Button(bf, text="应用设置", command=self.apply_p5).pack(side="left", padx=2)
        ttk.Button(bf, text="布防(启动延时)", command=lambda: self.p5_ctrl(0x1)).pack(side="left", padx=2)
        ttk.Button(bf, text="立即触发", command=lambda: self.p5_ctrl(0x2)).pack(side="left", padx=2)
        ttk.Button(bf, text="复位", command=lambda: self.p5_ctrl(0x4)).pack(side="left", padx=2)
        self.p5_status_var = tk.StringVar(value="状态: --")
        ttk.Label(bf, textvariable=self.p5_status_var).pack(side="left", padx=8)

        # ---- 日志 ----
        logf = ttk.LabelFrame(self.root, text="日志")
        logf.pack(fill="both", expand=True, padx=8, pady=6)
        self.log = tk.Text(logf, height=7, state="disabled", bg="#f7f7f7")
        self.log.pack(fill="both", expand=True, padx=4, pady=4)

        self._p5_src_changed()
        self._preview()
        self.logw("上位机就绪。请选择串口并连接（设备固件为 SUMP 逻辑分析仪 + 波形发生器）。")
        self.logw("提示: 与 PulseView 等 SUMP 软件不能同时占用串口。")

    # -------------------------------------------------------------- 日志 --
    def logw(self, msg):
        ts = time.strftime("%H:%M:%S")
        self.log.configure(state="normal")
        self.log.insert("end", f"[{ts}] {msg}\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    # ------------------------------------------------------------ 串口层 --
    def refresh_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.port_cb["values"] = ports
        if ports and not self.port_var.get():
            # 优先选择描述里带 CDC/USB Serial 的口
            best = ports[0]
            for p in serial.tools.list_ports.comports():
                desc = (p.description or "").lower()
                if "usb" in desc or "cdc" in desc or "serial" in desc:
                    best = p.device
                    break
            self.port_var.set(best)
        self.logw(f"发现串口: {', '.join(ports) if ports else '(无)'}")

    def toggle_connect(self):
        if self.dev_connected:
            self.disconnect()
        else:
            self.connect()

    def connect(self):
        port = self.port_var.get()
        if not port:
            messagebox.showwarning("提示", "请先选择串口")
            return
        try:
            self.ser = serial.Serial(port, 115200, timeout=0.2)
        except Exception as e:
            messagebox.showerror("串口打开失败", f"{e}\n（该串口可能被 PulseView / OLS 占用）")
            return
        self.rx_run = True
        self.rx_buf.clear()
        self.rx_thread = threading.Thread(target=self._rx_loop, daemon=True)
        self.rx_thread.start()

        # 握手：连续查询设备信息
        ok = False
        for _ in range(4):
            self.send_op(OP_GET_INFO, 0)
            t0 = time.time()
            while time.time() - t0 < 0.5:
                for frame in self._drain_frames():
                    if len(frame) == 20:
                        self.info = frame
                        ok = True
                        break
                if ok:
                    break
                time.sleep(0.02)
            if ok:
                break
        if ok:
            self.dev_connected = True
            ver = f"v{self.info[0]}.{self.info[1]}"
            self.rate_cap = struct.unpack("<I", bytes(self.info[14:18]))[0] or DEFAULT_RATE_CAP
            self.cap_var.set(f"{self.rate_cap / 1e6:g}")
            self.status_var.set(f"已连接 {port}  固件 {ver}")
            self.btn_conn.configure(text="断开")
            self.logw(f"连接成功: {port} (固件 {ver}, 采样率上限 {fmt_freq(self.rate_cap)})")
            self._sync_from_info()
        else:
            self.logw("未收到设备响应，请确认固件已烧录且无其他程序占用串口。")
            messagebox.showwarning("无响应", "未收到设备信息帧。\n请确认:\n1. 固件已烧录并运行\n2. 串口未被 PulseView/OLS 占用")
            self.disconnect()

    def disconnect(self):
        self.rx_run = False
        if self.rx_thread:
            self.rx_thread.join(timeout=1.0)
            self.rx_thread = None
        if self.ser:
            try:
                self.ser.close()
            except Exception:
                pass
            self.ser = None
        self.dev_connected = False
        self.btn_conn.configure(text="连接")
        self.status_var.set("未连接")
        self.actual_var.set("实际输出: --")
        self.p5_status_var.set("状态: --")
        self.logw("已断开连接")

    def send_op(self, op, value):
        if not self.ser:
            return
        try:
            self.ser.write(bytes([op]) + struct.pack("<I", value & 0xFFFFFFFF))
        except Exception as e:
            self.logw(f"发送失败: {e}")

    def _rx_loop(self):
        while self.rx_run and self.ser:
            try:
                data = self.ser.read(256)
            except Exception:
                break
            if data:
                self.rx_buf.extend(data)

    def _drain_frames(self):
        """从接收缓冲解析 [0xAA][len][payload...] 帧，返回载荷列表。"""
        frames = []
        buf = self.rx_buf
        while True:
            idx = buf.find(RESP_SYNC)
            if idx < 0:
                if len(buf) > 4096:
                    del buf[:-4]
                break
            if idx > 0:
                del buf[:idx]
            if len(buf) < 2:
                break
            length = buf[1]
            if len(buf) < 2 + length:
                break
            frames.append(bytes(buf[2:2 + length]))
            del buf[:2 + length]
        return frames

    def _pump_rx(self):
        for frame in self._drain_frames():
            if len(frame) == 20:
                self.info = frame
                self._update_actual()
            elif len(frame) == 7:
                self.p5_status = frame
        self.root.after(50, self._pump_rx)

    def _poll_p5(self):
        if self.dev_connected:
            self.send_op(OP_P5_QUERY, 0)
            if self.p5_status:
                st = self.p5_status[0]
                rem = struct.unpack("<I", self.p5_status[1:5])[0]
                cfg = self.p5_status[5]
                p = (cfg >> 4) & 0x3
                tick = TICK_BASE_NS * PRESCALES[p]
                busy = bool(st & 1)
                done = bool(st & 2)
                out = bool(st & 4)
                if busy:
                    self.p5_status_var.set(
                        f"状态: 运行中  剩余 {fmt_time_ns(rem * tick)}  输出={'高' if out else '低'}")
                elif done:
                    self.p5_status_var.set(f"状态: 已完成  输出={'高' if out else '低'}")
                else:
                    self.p5_status_var.set(f"状态: 空闲  输出={'高' if out else '低'}")
        self.root.after(400, self._poll_p5)

    # ------------------------------------------------------------ 状态同步 --
    def _sync_from_info(self):
        if not self.info:
            return
        t, amp, freq = self.info[2], self.info[3], struct.unpack("<I", bytes(self.info[4:8]))[0]
        self.wave_var.set(t)
        self.amp_var.set(amp)
        # 频率回填到输入框（用最合适的单位）
        if freq >= 1_000_000:
            self.freq_var.set(f"{freq / 1e6:g}"); self.funit_var.set("MHz")
        elif freq >= 1_000:
            self.freq_var.set(f"{freq / 1e3:g}"); self.funit_var.set("kHz")
        else:
            self.freq_var.set(f"{freq}"); self.funit_var.set("Hz")
        flags = self.info[12]
        self.enable_var.set(bool(flags & 1))
        self.p5_src_var.set("square" if (flags & 2) else "engine")
        self._p5_src_changed()
        self._preview()
        self._update_actual()

    def _update_actual(self):
        if not self.info:
            return
        actual = struct.unpack("<I", bytes(self.info[8:12]))[0]
        l_log2 = self.info[13]
        cap = struct.unpack("<I", bytes(self.info[14:18]))[0]
        if actual:
            self.actual_var.set(f"实际输出: {fmt_freq(actual)}  (表长 {1 << l_log2} 点, 上限 {fmt_freq(cap)})")
        else:
            self.actual_var.set("实际输出: (输出关闭)")

    # ------------------------------------------------------------ PIN_11 --
    def _preview(self):
        c = self.canvas
        c.delete("all")
        w = max(c.winfo_width(), 100)
        h = max(c.winfo_height(), 60)
        t = self.wave_var.get()
        amp = self.amp_var.get() / 100.0
        pts = []
        N = 200
        for i in range(N + 1):
            ph = (i * 2 / N) % 1.0
            if t == 0:
                v = __import__("math").sin(ph * 6.283185307179586)
            elif t == 1:
                v = 1.0 if ph < 0.5 else -1.0
            elif t == 2:
                v = ph * 2 - 1
            else:
                v = (ph * 4 - 1) if ph < 0.5 else (3 - ph * 4)
            y = h / 2 - v * amp * (h / 2 - 8)
            pts.extend([i * w / N, y])
        c.create_line(*pts, fill="#c33", width=2)

    def _current_freq_hz(self):
        v = float(self.freq_var.get())
        return int(round(v * UNIT_MULT[self.funit_var.get()]))

    def apply_wave(self):
        if not self.dev_connected:
            messagebox.showwarning("提示", "请先连接设备")
            return
        try:
            f = self._current_freq_hz()
        except ValueError:
            messagebox.showerror("输入错误", "频率格式不正确")
            return
        if f < 1:
            f = 1
        t = self.wave_var.get()
        fmax = self.rate_cap // WAVE_MIN_PTS[t]
        if f > fmax:
            if not messagebox.askokcancel(
                    "超出上限",
                    f"当前采样率上限 {fmt_freq(self.rate_cap)} 下，{WAVE_NAMES[t]} 最高约 {fmt_freq(fmax)}。\n"
                    f"将自动按 {fmt_freq(fmax)} 输出。\n\n"
                    f"（如需更高频率的方波，请使用 PIN_5 数字方波，最高 100 MHz）"):
                return
            f = fmax
        amp = self.amp_var.get()
        en = 1 if self.enable_var.get() else 0
        self.send_op(OP_WAVE, (en << 16) | (amp << 8) | t)
        self.send_op(OP_FREQ, f)
        time.sleep(0.05)
        self.send_op(OP_GET_INFO, 0)
        self.logw(f"PIN_11 设置: {WAVE_NAMES[t]}, {fmt_freq(f)}, 幅度 {amp}%, 输出{'开' if en else '关'}")

    def apply_rate_cap(self):
        if not self.dev_connected:
            messagebox.showwarning("提示", "请先连接设备")
            return
        try:
            r = int(float(self.cap_var.get()) * 1e6)
        except ValueError:
            messagebox.showerror("输入错误", "MHz 数值不正确")
            return
        r = max(2000, min(r, 100_000_000))
        self.send_op(OP_RATE_CAP, r)
        self.rate_cap = r
        time.sleep(0.05)
        self.send_op(OP_GET_INFO, 0)
        self.logw(f"DAC 采样率上限设为 {fmt_freq(r)}（如波形失真请降低；上限越高越高频）")

    # ------------------------------------------------------------ PIN_5 --
    def _p5_src_changed(self):
        if self.p5_src_var.get() == "square":
            for child in self.engine_frame.winfo_children():
                child.configure(style="")
            state = "disabled"
        else:
            state = "normal"
        # 简单做法：切换整组控件的可用性
        for child in self.engine_frame.winfo_children():
            for sub in child.winfo_children():
                if isinstance(sub, (ttk.Entry, ttk.Combobox, ttk.Button)):
                    try:
                        sub.configure(state=("readonly" if isinstance(sub, ttk.Combobox) else "normal")
                                      if state == "normal" else "disabled")
                    except Exception:
                        pass

    def apply_square(self):
        if not self.dev_connected:
            messagebox.showwarning("提示", "请先连接设备")
            return
        self.p5_src_var.set("square")
        self._p5_src_changed()
        self.send_op(OP_P5_CFG, (0x1 << 8))          # sq_sel=1
        try:
            f = int(round(float(self.sqf_var.get()) * UNIT_MULT[self.sqfunit_var.get()]))
        except ValueError:
            messagebox.showerror("输入错误", "方波频率格式不正确")
            return
        f = max(1, min(f, 100_000_000))
        self.send_op(OP_SQ_FREQ, f)
        self.logw(f"PIN_5 数字方波输出 {fmt_freq(f)} (1 Hz - 100 MHz)")

    def apply_p5(self):
        if not self.dev_connected:
            messagebox.showwarning("提示", "请先连接设备")
            return
        self.p5_src_var.set("engine")
        self._p5_src_changed()
        mode = P5_MODE_NAMES.index(self.p5_mode_var.get())
        level = 1 if self.p5_level_var.get() == "高" else 0
        idle = 1 if self.p5_idle_var.get() == "高" else 0
        try:
            d_ns = float(self.p5_delay_var.get()) * TIME_MULT_NS[self.p5_delayunit_var.get()]
            w_ns = float(self.p5_width_var.get()) * TIME_MULT_NS[self.p5_widthunit_var.get()]
        except ValueError:
            messagebox.showerror("输入错误", "延时/脉宽格式不正确")
            return
        p_d, d_ticks = encode_time(d_ns)
        p_w, w_ticks = encode_time(w_ns)
        p = max(p_d, p_w)                            # 共用时基，取较大者
        tick = TICK_BASE_NS * PRESCALES[p]
        d_ticks = min(int(round(d_ns / tick)), 0xFFFFFFFF)
        w_ticks = min(int(round(w_ns / tick)), 0xFFFFFFFF)
        cfg = (mode & 0x3) | (level << 2) | (idle << 3) | (p << 4)   # sq_sel=0
        self.send_op(OP_P5_CFG, cfg)
        self.send_op(OP_P5_DELAY, d_ticks)
        self.send_op(OP_P5_WIDTH, w_ticks)
        self.logw(f"PIN_5 触发引擎: {self.p5_mode_var.get()}, 电平={'高' if level else '低'}, "
                  f"延时={fmt_time_ns(d_ticks * tick)}, 脉宽={fmt_time_ns(w_ticks * tick)}, "
                  f"时基={tick:g}ns")
        if mode < 2:
            self.logw("  延迟模式: 点击 [布防(启动延时)] 后开始计时")

    def p5_ctrl(self, bits):
        if not self.dev_connected:
            messagebox.showwarning("提示", "请先连接设备")
            return
        self.send_op(OP_P5_CTRL, bits)
        names = {1: "布防", 2: "立即触发", 4: "复位"}
        self.logw(f"PIN_5 {names.get(bits, bits)}")


def main():
    root = tk.Tk()
    try:
        root.call("tk", "scaling", 1.2)
    except Exception:
        pass
    WaveGenApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
