#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FOC Knob 上位机（AG32VF303 力反馈旋钮调试工具）

功能：
  - 串口连接固件（UART0 115200），解析 $T 遥测流（tel 命令开启）
  - 实时显示：旋钮表盘、角度/目标、速度、Uq 力矩、霍尔状态、故障标志、FOC 循环频率
  - 三路实时曲线：角度+目标（deg）、速度（rad/s）、Uq（V），时间窗 5/10/30s 可选
  - 模式切换按钮（m0..m5）、参数滑块（kp/kd/df/fi/kf/vl/n/br/ua/rs）、动作按钮
    （校准 cal / 测极对数 pp / 设中心 cd / 清零 z / 清故障 cl / 休眠 sl / 使能 en）、
    一键旋转（正转一圈 rot 360 / 反转一圈 rot -360，未校准时固件走开环步进）
  - 原始串口终端 + 任意命令发送

用法：
  python foc_tuner.py                 # 打开 GUI
  python foc_tuner.py --port COM26    # 指定串口
  python foc_tuner.py --list          # 列出可用串口
  python foc_tuner.py --selftest      # 解析器自检（无 GUI/无串口）
  python foc_tuner.py --smoke         # GUI 冒烟测试（1.5s 自动退出）

依赖：Python 3.10+，pip install pyserial
"""

import argparse
import math
import os
import queue
import sys
import threading
import time
from collections import deque

try:
    import tkinter as tk
    from tkinter import messagebox, scrolledtext, ttk
    TK_OK = True
except ImportError:  # pragma: no cover
    TK_OK = False

TELE_PREFIX = "$T,"
TELE_FIELDS = 11  # $T,mode,ang,vel,uq,tgt,hall,flags,hz,pos,subpos

MODE_NAMES = ["自由", "阻尼", "惯性", "挡位", "有界", "弹簧"]

FLAG_FAULT = 1
FLAG_LATCH = 2
FLAG_SLEEP = 4
FLAG_HALL_BAD = 8
FLAG_FOC_LIVE = 16

# (key, 标签, min, max, res, default, 发送格式)
PARAMS = [
    ("kp", "位置环 Kp (V/rad)",   0.0, 15.0, 0.1,   5.0, "kp {:.2f}"),
    ("kd", "弹簧/墙刹车幅值 (V)", 0.0,  0.5, 0.01,  0.45, "kd {:.3f}"),
    ("df", "阻尼增益 Kdamp",      0.0,  1.0, 0.01,  0.1,  "df {:.2f}"),
    ("fi", "惯性增益 Kiner",      0.0,  0.3, 0.005, 0.05, "fi {:.3f}"),
    ("kf", "有界自由区 Kfree",    0.0,  0.2, 0.005, 0.02, "kf {:.3f}"),
    ("vl", "电压限幅 Vlimit (V)", 0.2,  6.8, 0.1,   3.0,  "vl {:.1f}"),
    # m3 挡位引擎（SmartKnob 移植）：宽度按霍尔扇区(10°)取整
    ("dw", "挡位宽度 (deg)",      5.0, 90.0, 5.0,  30.0, "dw {:.0f}"),
    ("ds", "挡位力度 Dstrength",  0.0,  6.0, 0.1,   2.5, "ds {:.1f}"),
    ("es", "限位力度 Estrength",  0.0,  6.0, 0.1,   4.0, "es {:.1f}"),
    ("sp", "吸附点 SnapPoint",    0.5,  1.5, 0.05,  0.6, "sp {:.2f}"),
    ("sb", "吸附偏置 SnapBias",   0.0,  0.4, 0.05,  0.0, "sb {:.2f}"),
    ("pn", "挡位下限 Pmin",     -16.0, 16.0, 1.0,   0.0, "pn {:.0f}"),
    ("px", "挡位上限 Pmax",     -16.0, 16.0, 1.0,  -1.0, "px {:.0f}"),
    ("br", "有界边界 (deg)",      5.0, 170.0, 1.0,  45.0, "br {:.0f}"),
    ("ua", "校准电压 Ualign (V)", 0.3,  3.6, 0.1,   1.5,  "ua {:.1f}"),
    ("rs", "旋转速度 (deg/s)",    10.0, 360.0, 5.0, 120.0, "rs {:.0f}"),
]


# ---------------------------------------------------------------- telemetry
def parse_tele(line):
    """解析一行 $T 遥测，返回 dict；非遥测/坏行返回 None"""
    if not line.startswith(TELE_PREFIX):
        return None
    parts = line.split(",")
    if len(parts) != TELE_FIELDS:
        return None
    try:
        return {
            "mode": int(parts[1]),
            "ang": int(parts[2]) / 100.0,        # cdeg -> deg (连续机械角)
            "vel": int(parts[3]) / 1000.0,       # mrad/s -> rad/s
            "uq": int(parts[4]) / 1000.0,        # mV -> V
            "tgt": int(parts[5]) / 100.0,        # cdeg -> deg
            "hall": int(parts[6]),
            "flags": int(parts[7]),
            "hz": int(parts[8]),
            "pos": int(parts[9]),                # 挡位序号 (m3)
            "sub": int(parts[10]) / 100.0,       # 挡内小数位置 (-snap..+snap)
        }
    except ValueError:
        return None


class TeleBuffer:
    """遥测环形缓冲（线程内仅主线程写入）"""

    def __init__(self, maxlen=12000):
        self.rows = deque(maxlen=maxlen)  # (t, mode, ang, vel, uq, tgt, hall, flags, hz, pos, sub)
        self.count = 0
        self.errors = 0

    def feed(self, line, t=None):
        d = parse_tele(line)
        if d is None:
            if line.startswith(TELE_PREFIX):
                self.errors += 1
            return None
        row = (t if t is not None else time.perf_counter(),
               d["mode"], d["ang"], d["vel"], d["uq"], d["tgt"],
               d["hall"], d["flags"], d["hz"], d["pos"], d["sub"])
        self.rows.append(row)
        self.count += 1
        return row


# ---------------------------------------------------------------- serial
class SerialWorker:
    """后台串口读线程；write 线程安全"""

    def __init__(self, outq):
        self.outq = outq
        self.ser = None
        self._run = False
        self._thr = None

    @staticmethod
    def list_ports():
        try:
            import serial.tools.list_ports as lp
        except ImportError:
            return None
        return [p.device for p in lp.comports()]

    @staticmethod
    def find_daplink():
        """按 VID 找 AGM DAPLink 的 CDC 串口（VID 0xCAFE），找不到返回 None"""
        try:
            import serial.tools.list_ports as lp
        except ImportError:
            return None
        for p in lp.comports():
            if p.vid == 0xCAFE:
                return p.device
        return None

    def start(self, port, baud=115200):
        import serial  # 延迟导入：selftest 无需 pyserial
        self.ser = serial.Serial(port, baud, timeout=0.05)
        self._run = True
        self._thr = threading.Thread(target=self._loop, daemon=True)
        self._thr.start()

    def _loop(self):
        buf = b""
        ser = self.ser
        while self._run:
            try:
                data = ser.read(512)
            except Exception as exc:  # noqa: BLE001
                self.outq.put(("err", "串口读取: %s" % exc))
                break
            if data:
                buf += data
                while b"\n" in buf:
                    raw, buf = buf.split(b"\n", 1)
                    self.outq.put(("rx", raw.decode("ascii", "replace").rstrip("\r")))
        self.outq.put(("closed", None))

    def send(self, text):
        if self.ser is not None and self.ser.is_open:
            try:
                self.ser.write((text + "\n").encode("ascii"))
                self.outq.put(("sent", text))
            except Exception as exc:  # noqa: BLE001
                self.outq.put(("err", "串口发送: %s" % exc))
        else:
            # 静默丢弃会让人以为"点了没反应"——必须在终端说明原因
            self.outq.put(("err", "未连接，命令已丢弃: %s" % text))

    def stop(self):
        self._run = False
        if self._thr is not None:
            self._thr.join(timeout=1.0)
        if self.ser is not None:
            try:
                self.ser.close()
            except Exception:  # noqa: BLE001
                pass
        self.ser = None


# ---------------------------------------------------------------- GUI
class App:
    def __init__(self, port=None, baud=115200):
        self.q = queue.Queue()
        self.worker = SerialWorker(self.q)
        self.buf = TeleBuffer()
        self.connected = False
        self.window_s = 10.0
        self.frozen = False
        self.last = None          # 最新一行遥测 dict
        self.tel_rate = 0
        # 健康看护：让任何"看起来活着其实死了"的状态都可见
        self._last_rx = 0.0       # 最近收到固件数据的时间（monotonic）
        self._stale = False       # 遥测停滞告警中
        self._conn_text = "未连接"
        self._user_disc = False   # 用户主动断开 → 抑制自动重连
        self._reconnects = 0
        self._closing = False
        self._stall_t0 = 0.0      # |uq| 顶格且静止的起始时刻（堵转告警）

        self.root = tk.Tk()
        self.root.title("AG32 FOC 力反馈旋钮 - 调试上位机")
        self.root.geometry("1180x820")
        self.root.minsize(980, 640)
        style = ttk.Style(self.root)
        for theme in ("vista", "clam"):
            if theme in style.theme_names():
                style.theme_use(theme)
                break
        try:
            self.root.call("tk", "scaling", 1.25)
        except tk.TclError:
            pass

        self._build_topbar(port, baud)
        self._build_body()
        self._build_statusbar()
        self._refresh_views()   # 先画一遍空视图
        self.root.after(40, self._poll)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------- UI 构建 ----------
    def _build_topbar(self, port, baud):
        bar = ttk.Frame(self.root, padding=6)
        bar.pack(side="top", fill="x")

        ttk.Label(bar, text="串口:").pack(side="left")
        self.port_var = tk.StringVar(value=port or "")
        self.port_cb = ttk.Combobox(bar, textvariable=self.port_var,
                                    width=10, values=self._ports())
        self.port_cb.pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="刷新", width=5, command=self._refresh_ports).pack(side="left")
        ttk.Label(bar, text="波特率:").pack(side="left", padx=(10, 2))
        self.baud_var = tk.StringVar(value=str(baud))
        ttk.Combobox(bar, textvariable=self.baud_var, width=8,
                     values=["9600", "57600", "115200", "460800"]).pack(side="left")

        self.conn_btn = ttk.Button(bar, text="连接", width=8, command=self._toggle_conn)
        self.conn_btn.pack(side="left", padx=(14, 0))
        self.conn_dot = tk.Canvas(bar, width=12, height=12, highlightthickness=0)
        self.conn_dot.pack(side="left", padx=(6, 0))
        self._conn_dot(False)

        ttk.Label(bar, text="遥测率:").pack(side="left", padx=(20, 2))
        self.tel_var = tk.StringVar(value="50 Hz")
        tel_cb = ttk.Combobox(bar, textvariable=self.tel_var, width=8, state="readonly",
                              values=["关闭", "10 Hz", "20 Hz", "50 Hz", "100 Hz"])
        tel_cb.pack(side="left")
        tel_cb.bind("<<ComboboxSelected>>", self._on_tel_change)

        ttk.Label(bar, text="时间窗:").pack(side="left", padx=(20, 2))
        self.win_var = tk.StringVar(value="10 s")
        win_cb = ttk.Combobox(bar, textvariable=self.win_var, width=5, state="readonly",
                              values=["5 s", "10 s", "30 s"])
        win_cb.pack(side="left")
        win_cb.bind("<<ComboboxSelected>>", self._on_win_change)

        self.freeze_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="冻结曲线", variable=self.freeze_var).pack(side="left", padx=(20, 0))

    def _build_body(self):
        body = ttk.Frame(self.root)
        body.pack(side="top", fill="both", expand=True)

        # ---- 左列：模式 / 参数 / 动作 ----
        left = ttk.Frame(body, padding=4)
        left.pack(side="left", fill="y")

        ttk.Label(left, text="模式").pack(anchor="w")
        self.mode_btns = []
        mode_fr = ttk.Frame(left)
        mode_fr.pack(fill="x", pady=(0, 8))
        for i, name in enumerate(MODE_NAMES):
            b = ttk.Button(mode_fr, text="m%d %s" % (i, name), width=9,
                           command=lambda i=i: self.send("m%d" % i))
            b.grid(row=i // 2, column=i % 2, padx=2, pady=2, sticky="ew")
            self.mode_btns.append(b)
        mode_fr.columnconfigure((0, 1), weight=1)

        ttk.Separator(left).pack(fill="x", pady=4)
        ttk.Label(left, text="参数（松开滑块发送）").pack(anchor="w")
        self.scales = {}
        for key, label, lo, hi, res, dft, fmt in PARAMS:
            row = ttk.Frame(left)
            row.pack(fill="x", pady=1)
            lab = ttk.Label(row, text=label, width=17)
            lab.pack(side="left")
            val = ttk.Label(row, text=fmt.format(dft), width=7, anchor="e")
            val.pack(side="right")
            sc = tk.Scale(row, from_=lo, to=hi, resolution=res, orient="horizontal",
                          showvalue=False, length=150)
            sc.set(dft)
            sc.pack(side="left", fill="x", expand=True)
            sc.bind("<ButtonRelease-1>", lambda e, k=key, f=fmt: self._send_param(k, f))
            sc.bind("<KeyRelease>", lambda e, k=key, f=fmt: self._send_param(k, f))
            self.scales[key] = (sc, val, fmt)

        ttk.Separator(left).pack(fill="x", pady=4)
        ttk.Label(left, text="动作").pack(anchor="w")
        act = ttk.Frame(left)
        act.pack(fill="x")
        acts = [
            ("校准 cal", self._do_cal, 8), ("扫描校准 scan", self._do_scan, 9),
            ("测极对数 pp", self._do_pp, 8), ("正转一圈", lambda: self._do_rot(360), 8),
            ("反转一圈", lambda: self._do_rot(-360), 8),
            ("设中心 cd", lambda: self.send("cd"), 8), ("角度清零 z", lambda: self.send("z"), 8),
            ("清故障 cl", lambda: self.send("cl"), 8), ("休眠 sl", self._do_sleep, 8),
            ("使能 en", self._do_enable, 8), ("状态 st", lambda: self.send("st"), 8),
        ]
        for i, (txt, cb, w) in enumerate(acts):
            ttk.Button(act, text=txt, width=w, command=cb).grid(
                row=i // 2, column=i % 2, padx=2, pady=2, sticky="ew")
        act.columnconfigure((0, 1), weight=1)

        ttk.Separator(left).pack(fill="x", pady=4)
        send_fr = ttk.Frame(left)
        send_fr.pack(fill="x")
        self.cmd_var = tk.StringVar()
        cmd_ent = ttk.Entry(send_fr, textvariable=self.cmd_var, width=16)
        cmd_ent.pack(side="left", fill="x", expand=True)
        cmd_ent.bind("<Return>", lambda e: self._send_entry())
        ttk.Button(send_fr, text="发送", width=6, command=self._send_entry).pack(side="left")

        # ---- 右侧：读数 + 表盘 + 曲线 + 终端 ----
        right = ttk.Frame(body, padding=4)
        right.pack(side="left", fill="both", expand=True)

        top = ttk.Frame(right)
        top.pack(side="top", fill="x")

        self.dial = tk.Canvas(top, width=190, height=190, bg="#fafafa",
                              highlightthickness=1, highlightbackground="#bbb")
        self.dial.pack(side="left", padx=(0, 10))

        # 三路霍尔原始电平（右上角空位）：HU/HV/HW 高低电平，非法态标红
        lv = ttk.Frame(top)
        lv.pack(side="right", anchor="ne", padx=(2, 4))
        ttk.Label(lv, text="霍尔电平").pack(anchor="center", pady=(0, 2))
        lv_row = ttk.Frame(lv)
        lv_row.pack()
        self.hall_lv = []
        for name in ("HU", "HV", "HW"):
            cell = tk.Label(lv_row, text=name + "\n--", width=4, relief="groove",
                            bg="#e8e8e8", font=("Consolas", 10, "bold"))
            cell.pack(side="left", padx=2)
            self.hall_lv.append(cell)

        info = ttk.Frame(top)
        info.pack(side="left", fill="both", expand=True)
        self.lbl_angle = tk.StringVar(value="--")
        self.lbl_vel = tk.StringVar(value="--")
        self.lbl_uq = tk.StringVar(value="--")
        self.lbl_tgt = tk.StringVar(value="--")
        self.lbl_mode = tk.StringVar(value="--")
        self.lbl_hz = tk.StringVar(value="--")
        self.lbl_pos = tk.StringVar(value="--")
        for name, var in [("机械角", self.lbl_angle), ("速度", self.lbl_vel),
                          ("Uq 力矩", self.lbl_uq), ("目标角", self.lbl_tgt),
                          ("模式", self.lbl_mode), ("FOC 循环", self.lbl_hz),
                          ("挡位", self.lbl_pos)]:
            f = ttk.Frame(info)
            f.pack(anchor="w", pady=1)
            ttk.Label(f, text=name + ":", width=9).pack(side="left")
            ttk.Label(f, textvariable=var, font=("Consolas", 11, "bold")).pack(side="left")

        ttk.Label(info, text="霍尔:").pack(anchor="w", pady=(6, 0))
        hall_fr = ttk.Frame(info)
        hall_fr.pack(anchor="w")
        self.hall_leds = []
        for i in range(1, 7):
            lb = tk.Label(hall_fr, text=str(i), width=2, relief="groove",
                          bg="#e8e8e8", font=("Consolas", 9))
            lb.pack(side="left", padx=1)
            self.hall_leds.append(lb)
        self.lbl_flags = tk.StringVar(value="标志: --")
        ttk.Label(info, textvariable=self.lbl_flags).pack(anchor="w", pady=(4, 0))

        # 曲线区（3 幅，共享时间轴）
        charts = ttk.Frame(right)
        charts.pack(side="top", fill="both", expand=True, pady=(6, 0))
        self.cv_ang = tk.Canvas(charts, height=150, bg="#ffffff", highlightthickness=1,
                                highlightbackground="#ccc")
        self.cv_ang.pack(side="top", fill="both", expand=True)
        self.cv_vel = tk.Canvas(charts, height=120, bg="#ffffff", highlightthickness=1,
                                highlightbackground="#ccc")
        self.cv_vel.pack(side="top", fill="both", expand=True)
        self.cv_uq = tk.Canvas(charts, height=120, bg="#ffffff", highlightthickness=1,
                               highlightbackground="#ccc")
        self.cv_uq.pack(side="top", fill="both", expand=True)

        # 终端
        self.term = scrolledtext.ScrolledText(right, height=8, font=("Consolas", 9),
                                              state="disabled", bg="#111111", fg="#d4d4d4")
        self.term.pack(side="bottom", fill="both", pady=(6, 0))
        self.term.tag_config("sent", foreground="#6fb3ff")
        self.term.tag_config("err", foreground="#ff7070")
        self.term.tag_config("dim", foreground="#888888")

    def _build_statusbar(self):
        bar = ttk.Frame(self.root, padding=(6, 2))
        bar.pack(side="bottom", fill="x")
        self.lbl_status = tk.StringVar(value="未连接")
        ttk.Label(bar, textvariable=self.lbl_status, anchor="w").pack(side="left")
        self.lbl_stat2 = tk.StringVar(value="")
        ttk.Label(bar, textvariable=self.lbl_stat2, anchor="e").pack(side="right")

    # ---------- 事件 ----------
    def _ports(self):
        ports = SerialWorker.list_ports()
        return ports if ports else []

    def _refresh_ports(self):
        self.port_cb["values"] = self._ports()

    def _conn_dot(self, on, warn=False):
        self.conn_dot.delete("all")
        fill = "#c8c8c8"
        if on:
            fill = "#e53935" if warn else "#4caf50"   # 红 = 连着但固件无响应
        self.conn_dot.create_oval(1, 1, 11, 11, fill=fill, outline="#888")

    def _toggle_conn(self):
        if self.connected:
            self._user_disc = True
            self._reconnects = 0
            self.worker.stop()
            self.connected = False
            self.conn_btn["text"] = "连接"
            self._conn_dot(False)
            self.lbl_status.set("未连接")
            return
        port = self.port_var.get().strip()
        if not port:
            messagebox.showwarning("提示", "请先选择串口（或插上 DAPLink 后点刷新）")
            return
        try:
            self.worker.start(port, int(self.baud_var.get()))
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)
            if ("PermissionError(13" in msg or "拒绝访问" in msg
                    or "Access is denied" in msg):
                messagebox.showerror(
                    "打开串口失败",
                    "%s\n\n串口被其他程序占用：很可能已经开着另一个 FocTuner\n"
                    "（或 pio monitor / 串口助手）。请关掉它，或直接用那个窗口。" % exc)
            else:
                messagebox.showerror("打开串口失败",
                                     "%s\n\n提示: 关闭其他占用该串口的程序（如 pio monitor）" % exc)
            self.lbl_status.set("连接失败（串口被占用或不可用）")
            return
        self._user_disc = False
        self._reconnects = 0
        self.connected = True
        self._conn_text = "已连接 %s @ %s" % (port, self.baud_var.get())
        self.conn_btn["text"] = "断开"
        self._conn_dot(True)
        self.lbl_status.set(self._conn_text)
        self.send("st")            # 报一次完整状态
        self._on_tel_change()      # 连接即按所选遥测率开始推流（默认 50 Hz）

    def _auto_connect(self):
        """--port 启动时自动连接一次"""
        if not self.connected and self.port_var.get().strip():
            self._toggle_conn()

    def _auto_connect_daplink(self):
        """启动时自动寻找并连接 DAPLink（VID 0xCAFE），双击即用"""
        if self.connected:
            return
        port = SerialWorker.find_daplink()
        if port is None:
            self.lbl_status.set("未找到 DAPLink（插上后点\"刷新\"再\"连接\"）")
            return
        self.port_var.set(port)
        self._toggle_conn()

    def _on_tel_change(self, _e=None):
        rate = {"关闭": 0, "10 Hz": 10, "20 Hz": 20, "50 Hz": 50, "100 Hz": 100}[self.tel_var.get()]
        self.tel_rate = rate
        self.send("tel %d" % rate)

    def _on_win_change(self, _e=None):
        self.window_s = float(self.win_var.get().split()[0])

    def _do_cal(self):
        if messagebox.askyesno("校准", "校准时电机会自动转动约 1.5 秒！\n请确保旋钮可以自由空转。\n\n继续？"):
            self.send("cal")

    def _do_scan(self):
        if messagebox.askyesno("扫描校准 scan",
                               "固件将开环拖动一圈（约 7 秒），实测霍尔顺序/方向/锚点，\n"
                               "完成后自动进入 FOC 闭环。旋转全程本工具实时刷新。\n"
                               "请确保旋钮可以自由空转。\n\n继续？"):
            self.send("scan")

    def _do_pp(self):
        if messagebox.askyesno("测极对数", "点击确定后 6 秒内\n用手把旋钮转正好一整圈。"):
            self.send("pp")

    def _do_rot(self, deg):
        speed = int(self.scales["rs"][0].get())
        # 固件开环/闭环均为非阻塞旋转：全程持续推 $T，霍尔与曲线实时可见
        tip = ("未校准走开环拖动（速度 %d°/s），已校准走闭环轨迹。\n"
               "旋转全程上位机实时刷新，可随时再发一次 rot 中止。\n\n继续？" % speed)
        if messagebox.askyesno("旋转 %.0f°" % deg,
                               "电机将自动旋转 %.0f°（速度 %d°/s）。\n请确保旋钮可以自由空转。\n\n%s"
                               % (deg, speed, tip)):
            self.send("rot %d" % deg)

    def _do_sleep(self):
        cur = (self.last["flags"] & FLAG_SLEEP) if self.last else False
        self.send("sl %d" % (0 if cur else 1))

    def _do_enable(self):
        cur = bool(self.last["flags"] & FLAG_FOC_LIVE) if self.last else False
        self.send("en %d" % (0 if cur else 1))

    def _send_param(self, key, fmt):
        sc, _lab, _f = self.scales[key]
        self.send(fmt.format(sc.get()))

    def _send_entry(self):
        cmd = self.cmd_var.get().strip()
        if cmd:
            self.send(cmd)
            self.cmd_var.set("")

    def send(self, text):
        if self.connected:
            self.worker.send(text)
        else:
            # 静默丢弃是"点了没反应"的最大嫌疑——必须当场红字喊出来
            self._term("ERR 未连接，命令未发送: %s （请先点\"连接\"）" % text, "err")

    # ---------- 数据流 ----------
    def _poll(self):
        n = 0
        while n < 1000:
            try:
                kind, payload = self.q.get_nowait()
            except queue.Empty:
                break
            n += 1
            if kind == "rx":
                self._on_rx(payload)
            elif kind == "sent":
                self._term(">> " + payload, "sent")
            elif kind == "err":
                self._term("ERR " + payload, "err")
            elif kind == "closed":
                self.connected = False
                self.conn_btn["text"] = "连接"
                self._conn_dot(False)
                self._stale = False
                if self._user_disc or self._closing:
                    self.lbl_status.set("未连接")
                else:
                    self.lbl_status.set("串口意外断开，自动重连中…")
                    self._term("串口意外断开，1.5 秒后自动重连（最多 5 次）", "err")
                    if self._reconnects == 0:
                        self.root.after(1500, self._try_reconnect)
        self._watchdog()
        self._refresh_views()
        self.after_id = self.root.after(40, self._poll)

    def _try_reconnect(self):
        """意外断线后的自动重连；用户主动断开或窗口关闭时不插手"""
        if self._closing or self.connected or self._user_disc:
            return
        self._reconnects += 1
        try:
            self.worker.stop()   # 清掉可能残留的半开句柄
        except Exception:  # noqa: BLE001
            pass
        try:
            self.worker.start(self.port_var.get().strip(), int(self.baud_var.get()))
        except Exception:  # noqa: BLE001
            if self._reconnects >= 5:
                self.lbl_status.set("自动重连失败（5 次），请检查 DAPLink 后手动\"连接\"")
                self._term("ERR 自动重连 5 次失败，停止重试。插好 DAPLink 后手动点\"连接\"。", "err")
            else:
                self.root.after(1500, self._try_reconnect)
            return
        self.connected = True
        self._conn_text = "已连接 %s @ %s" % (self.port_var.get().strip(), self.baud_var.get())
        self.conn_btn["text"] = "断开"
        self._conn_dot(True)
        self.lbl_status.set(self._conn_text)
        self._term("自动重连成功（第 %d 次尝试）" % self._reconnects, "dim")
        self._reconnects = 0
        self.send("st")
        self.send("tel %d" % self.tel_rate)

    def _watchdog(self):
        """连着却长时间没有固件数据（被复位/占用/烧录 halt）→ 红点+提示，恢复后自动消失。
        pp/cal 期间固件主循环短暂阻塞属正常，提示几秒会自行消除。"""
        if not self.connected or self.tel_rate <= 0 or self._last_rx == 0.0:
            return
        stale = (time.monotonic() - self._last_rx) > 3.0
        if stale != self._stale:
            self._stale = stale
            self._conn_dot(True, warn=stale)
            if stale:
                self.lbl_status.set("⚠ 3 秒无遥测：固件可能被复位/占用（cal/pp 中属正常，恢复后此提示自动消失）")
            else:
                self.lbl_status.set(self._conn_text)

    def _on_rx(self, line):
        self._last_rx = time.monotonic()
        if self._stale:          # 固件恢复出声 → 撤销看门狗告警
            self._stale = False
            self._conn_dot(True)
            self.lbl_status.set(self._conn_text)
        if line.startswith(TELE_PREFIX):
            row = self.buf.feed(line)
            if row is not None:
                self.last = {
                    "mode": row[1], "ang": row[2], "vel": row[3], "uq": row[4],
                    "tgt": row[5], "hall": row[6], "flags": row[7], "hz": row[8],
                    "pos": row[9], "sub": row[10],
                }
            else:
                self._term(line, "dim")
            return  # $T 不进终端，避免刷屏
        self._term(line, None)

    def _term(self, text, tag):
        self.term["state"] = "normal"
        self.term.insert("end", text + "\n", tag or ())
        if int(self.term.index("end-1c").split(".")[0]) > 900:
            self.term.delete("1.0", "200.0")
        self.term["state"] = "disabled"
        self.term.see("end")

    # ---------- 刷新 ----------
    def _refresh_views(self):
        d = self.last
        if d is not None:
            self.lbl_angle.set("%8.2f °" % d["ang"])
            self.lbl_vel.set("%8.3f rad/s" % d["vel"])
            self.lbl_uq.set("%8.3f V" % d["uq"])
            self.lbl_tgt.set("%8.2f °" % d["tgt"])
            mode = d["mode"]
            self.lbl_mode.set("m%d %s" % (mode, MODE_NAMES[mode] if 0 <= mode < len(MODE_NAMES) else "?"))
            self.lbl_hz.set("%s Hz" % ("{:,}".format(d["hz"]) if d["hz"] else "0"))
            self.lbl_pos.set("%d  %+0.2f" % (d["pos"], d["sub"]))
            self._update_hall(d["hall"])
            self._update_hall_levels(d["hall"])
            self._update_flags(d["flags"])
            self._update_mode_btns(mode)
        # 堵转/异常告警：|uq| 接近满幅(>=2.9V) 而转子静止(|vel|<0.1) 持续 >1s
        # —— 正常调参不该出现（挡位静止保持力设计上 <2.5V 静摩擦），
        #    出现即说明力矩被幻影状态顶满或转子被卡住
        now = time.monotonic()
        stalled = (d is not None and abs(d["uq"]) >= 2.9 and abs(d["vel"]) < 0.1)
        if stalled:
            if self._stall_t0 == 0.0:
                self._stall_t0 = now
            elif now - self._stall_t0 > 1.0:
                self.lbl_stat2.set("⚠ 力矩顶格但转子静止 >1s（堵转/参数异常，发 st 查看）")
        else:
            self._stall_t0 = 0.0
            if self.lbl_stat2.get().startswith("⚠"):
                self.lbl_stat2.set("")
        self._draw_dial()
        if not self.frozen:
            self._draw_charts()
        self._update_status2()

    def _update_hall(self, hall):
        ok = 1 <= hall <= 6
        for i, lb in enumerate(self.hall_leds, start=1):
            if ok and i == hall:
                lb["bg"] = "#7bd67b"
            elif not ok:
                lb["bg"] = "#ff9a9a"
            else:
                lb["bg"] = "#e8e8e8"

    def _update_hall_levels(self, hall):
        """三根霍尔线原始电平：hall bit2/1/0 = HU/HV/HW；非法态(0/7)整组标红"""
        ok = 1 <= hall <= 6
        for i, cell in enumerate(self.hall_lv):
            hi = bool(hall & (4 >> i))
            name = ("HU", "HV", "HW")[i]
            cell["text"] = "%s\n%d" % (name, 1 if hi else 0)
            if not ok:
                cell["bg"] = "#ff9a9a"
            else:
                cell["bg"] = "#7bd67b" if hi else "#e0e0e0"

    def _update_flags(self, flags):
        names = [(FLAG_FAULT, "FAULT"), (FLAG_LATCH, "锁存"), (FLAG_SLEEP, "休眠"),
                 (FLAG_HALL_BAD, "霍尔异常"), (FLAG_FOC_LIVE, "FOC运行")]
        on = [txt for bit, txt in names if flags & bit]
        self.lbl_flags.set("标志: " + (" ".join(on) if on else "无") + (" | 未校准!" if not flags & FLAG_FOC_LIVE else ""))

    def _update_mode_btns(self, mode):
        for i, b in enumerate(self.mode_btns):
            b.state(["pressed"] if i == mode else ["!pressed"])

    def _update_status2(self):
        parts = ["遥测 %d 行" % self.buf.count]
        if self.buf.errors:
            parts.append("坏帧 %d" % self.buf.errors)
        if self.tel_rate:
            parts.append("遥测 %d Hz" % self.tel_rate)
        self.lbl_stat2.set(" | ".join(parts))

    # ---------- 绘图 ----------
    def _draw_dial(self):
        c = self.dial
        c.delete("all")
        w = int(c.winfo_width()) or 190
        h = int(c.winfo_height()) or 190
        cx, cy = w / 2.0, h / 2.0
        r = min(cx, cy) - 12
        c.create_oval(cx - r, cy - r, cx + r, cy + r, outline="#888", width=2)
        mode = self.last["mode"] if self.last else 0
        if mode == 3:   # 挡位模式：刻度按挡位宽度画
            n = max(1, int(round(360.0 / max(self.scales["dw"][0].get(), 5.0))))
        else:
            n = 12
        for i in range(n):
            a = math.radians(i * 360.0 / n - 90)
            x0, y0 = cx + (r - 10) * math.cos(a), cy + (r - 10) * math.sin(a)
            x1, y1 = cx + r * math.cos(a), cy + r * math.sin(a)
            c.create_line(x0, y0, x1, y1, fill="#bbb")
        ang = 0.0
        if self.last:
            ang = self.last["ang"]
        rad = math.radians(ang - 90)
        nx, ny = cx + (r - 18) * math.cos(rad), cy + (r - 18) * math.sin(rad)
        c.create_line(cx, cy, nx, ny, fill="#d33", width=3, arrow="last")
        c.create_oval(cx - 4, cy - 4, cx + 4, cy + 4, fill="#333")
        c.create_text(cx, cy + r - 2, text="%.1f°" % ang, font=("Consolas", 10, "bold"))

    def _window_rows(self):
        rows = self.buf.rows
        if len(rows) < 2:
            return None
        t_now = rows[-1][0]
        t0 = t_now - self.window_s
        return [r for r in rows if r[0] >= t0]

    def _draw_charts(self):
        sel = self._window_rows()
        self._chart(self.cv_ang, sel,
                    [(2, "#d33", "角度"), (5, "#3a7", "目标")], unit="deg")
        self._chart(self.cv_vel, sel, [(3, "#36c", "速度")], unit="rad/s")
        self._chart(self.cv_uq, sel, [(4, "#d82", "Uq")], unit="V")

    def _chart(self, cv, sel, traces, unit=""):
        cv.delete("all")
        w = int(cv.winfo_width())
        h = int(cv.winfo_height())
        if w < 60 or h < 40:
            return
        m_l, m_r, m_t, m_b = 46, 8, 16, 14
        pw, ph = w - m_l - m_r, h - m_t - m_b
        cv.create_rectangle(m_l, m_t, m_l + pw, m_t + ph, outline="#ccc")

        if not sel or len(sel) < 2:
            cv.create_text(w / 2, h / 2, text="等待遥测…（选择遥测率，如 50 Hz）", fill="#999")
            return

        t_end, t0 = sel[-1][0], sel[-1][0] - self.window_s

        # 垂直网格：每 1s
        sec = int(self.window_s)
        for i in range(sec + 1):
            x = m_l + pw * (1 - i / float(sec))
            cv.create_line(x, m_t, x, m_t + ph, fill="#eee")
            if i % 2 == 0 and sec <= 10 or i % 5 == 0:
                cv.create_text(x, m_t + ph + 7, text="-%ds" % i, fill="#999", font=("Consolas", 8))

        # y 范围
        vals = []
        for idx, _color, _name in traces:
            vals += [r[idx] for r in sel]
        ymin, ymax = min(vals), max(vals)
        if ymax - ymin < 1e-6:
            ymin, ymax = ymin - 1.0, ymax + 1.0
        pad = (ymax - ymin) * 0.12
        ymin, ymax = ymin - pad, ymax + pad

        def ymap(v):
            return m_t + ph - (v - ymin) / (ymax - ymin) * ph

        # 0 线与 y 标签
        if ymin < 0 < ymax:
            cv.create_line(m_l, ymap(0), m_l + pw, ymap(0), fill="#ddd", dash=(3, 3))
        cv.create_text(m_l - 4, m_t, text="%.4g" % ymax, anchor="e", fill="#666", font=("Consolas", 8))
        cv.create_text(m_l - 4, m_t + ph, text="%.4g" % ymin, anchor="e", fill="#666", font=("Consolas", 8))
        cv.create_text(m_l - 4, h / 2, text=unit, anchor="e", fill="#666", font=("Consolas", 8))

        step = max(1, len(sel) // 500)
        for idx, color, name in traces:
            pts = []
            for i in range(0, len(sel), step):
                r = sel[i]
                x = m_l + pw * (r[0] - t0) / (t_end - t0)
                pts += [x, ymap(r[idx])]
            if len(pts) >= 4:
                cv.create_line(pts, fill=color, width=1, smooth=False)
            cv.create_text(m_l + 6 + 70 * traces.index((idx, color, name)), m_t - 5,
                           text="%s %.3g %s" % (name, sel[-1][idx], unit),
                           fill=color, font=("Consolas", 8), anchor="w")

    # ---------- 退出 ----------
    def _on_close(self):
        self._closing = True
        try:
            self.worker.stop()
        except Exception:  # noqa: BLE001
            pass
        try:
            self.root.destroy()
        except Exception:  # noqa: BLE001
            pass
        # 关窗即退出：PyInstaller --windowed 下残留的后台线程会拖住解释器，
        # 串口已清理，直接结束进程，避免任务管理器里留下僵尸 FocTuner.exe
        os._exit(0)

    def run(self):
        self.root.mainloop()


# ---------------------------------------------------------------- 自检/冒烟
def selftest():
    ok = True

    def check(name, cond):
        nonlocal ok
        print(("  PASS  " if cond else "  FAIL  ") + name)
        ok = ok and cond

    row = parse_tele("$T,3,4512,-125,2340,4500,5,17,39980,2,-42")
    check("解析字段", row is not None)
    if row:
        check("mode=3", row["mode"] == 3)
        check("ang=45.12", abs(row["ang"] - 45.12) < 1e-9)
        check("vel=-0.125", abs(row["vel"] + 0.125) < 1e-9)
        check("uq=2.34", abs(row["uq"] - 2.34) < 1e-9)
        check("tgt=45.00", abs(row["tgt"] - 45.0) < 1e-9)
        check("hall=5", row["hall"] == 5)
        check("flags=17", row["flags"] == 17)
        check("hz=39980", row["hz"] == 39980)
        check("pos=2", row["pos"] == 2)
        check("sub=-0.42", abs(row["sub"] + 0.42) < 1e-9)
    check("坏行->None(不计数)", parse_tele("$T,1,2") is None)
    check("旧9字段->None", parse_tele("$T,3,4512,-125,2340,4500,5,17,39980") is None)
    check("非遥测->None", parse_tele("[FREE] ang=1.0deg") is None)

    buf = TeleBuffer()
    n = 400
    for i in range(n):
        ang = int(4500 * math.sin(i * 0.05))
        line = "$T,3,%d,%d,%d,%d,5,16,39980,1,25" % (ang, int(800 * math.cos(i * 0.05)),
                                                     int(1500 * math.sin(i * 0.1)), ang)
        buf.feed(line)
    check("缓冲 %d 行" % n, len(buf.rows) == n and buf.errors == 0)
    check("时间单调", all(buf.rows[i][0] <= buf.rows[i + 1][0] for i in range(n - 1)))

    print("SELFTEST %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def smoke():
    if not TK_OK:
        print("tkinter 不可用")
        return 1
    app = App(port=None)
    for i in range(400):
        ang = int(4500 * math.sin(i * 0.05))
        line = "$T,3,%d,%d,%d,%d,5,16,39980,1,25" % (ang, int(800 * math.cos(i * 0.05)),
                                                     int(1500 * math.sin(i * 0.1)), ang)
        app.buf.feed(line)
    if app.buf.rows:
        app.last = {"mode": 3, "ang": app.buf.rows[-1][2], "vel": app.buf.rows[-1][3],
                    "uq": app.buf.rows[-1][4], "tgt": app.buf.rows[-1][5],
                    "hall": 5, "flags": 16, "hz": 39980,
                    "pos": app.buf.rows[-1][9], "sub": app.buf.rows[-1][10]}
    app.root.after(1500, app.root.destroy)
    app.run()
    print("SMOKE OK (UI 构建/绘制正常)")
    return 0


def _acquire_single_instance():
    """双开 FocTuner 是"点了没反应"的经典来源：第二个实例抢不到串口，
    之后所有点击都被静默丢弃。用本机 TCP 端口做单实例锁，双开时提示后退出。"""
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", 47777))
        s.listen(1)
        return s
    except OSError:
        s.close()
        return None


def main():
    ap = argparse.ArgumentParser(description="AG32 FOC 力反馈旋钮上位机")
    ap.add_argument("--port", help="串口，如 COM26")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--list", action="store_true", help="列出可用串口后退出")
    ap.add_argument("--selftest", action="store_true", help="解析器自检")
    ap.add_argument("--smoke", action="store_true", help="GUI 冒烟测试（1.5s 自动退出）")
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if args.list:
        ports = SerialWorker.list_ports()
        if ports is None:
            print("pyserial 未安装: pip install pyserial")
            return 1
        print("\n".join(ports) if ports else "(无串口)")
        return 0

    if not TK_OK:
        print("tkinter 不可用，请使用官方 Python 安装包")
        return 1
    if args.smoke:
        return smoke()
    lock = _acquire_single_instance()
    if lock is None:
        root = tk.Tk()
        root.withdraw()
        messagebox.showwarning(
            "FocTuner 已在运行",
            "检测到另一个 FocTuner 窗口正在运行（串口也归它管）。\n"
            "请在任务栏找到那个窗口使用；本窗口即将关闭。")
        return 2
    app = App(port=args.port, baud=args.baud)
    if args.port:
        app.root.after(300, app._auto_connect)
    else:
        app.root.after(400, app._auto_connect_daplink)   # 双击 exe 自动连 DAPLink
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
