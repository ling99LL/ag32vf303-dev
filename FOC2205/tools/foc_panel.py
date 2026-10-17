"""FOC2205 diagnostics panel. Run with Python 3 + pyserial + tkinter."""
from collections import deque
import csv
from datetime import datetime
import math
from pathlib import Path
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import serial
import serial.tools.list_ports
from foc_protocol import PanelState, Status, Telemetry, STATE_NAMES, HAPTIC_MODE_NAMES

POLL_MS = 100
ENCODER_DISPLAY_DIRECTION = -1  # physical magnet/knob orientation on this board
LOG_DIR = Path(__file__).resolve().parents[1] / 'experiments' / 'logs'
SPIN_SPEED_PRESETS = (3, 6, 15, 60)
SPIN_OPENLOOP_POWER_MAX = 20
SPIN_VEL_KP_DEFAULT = 0.010
SPIN_VEL_KI_DEFAULT = 0.050
SPIN_VEL_FF_DEFAULT = 0.000
SPIN_VEL_FR_DEFAULT = 0.000
HAPTIC_PARAMS = [
    ('df', 'm1 阻尼 df', 0.0, 1.0, 0.01, 0.10, '{:.2f}', 'df {:.2f}'),
    ('fi', 'm2 惯性 fi', 0.0, 0.3, 0.005, 0.05, '{:.3f}', 'fi {:.3f}'),
    ('dw', 'm3 挡宽 dw(deg)', 5.0, 90.0, 1.0, 30.0, '{:.0f}', 'dw {:.0f}'),
    ('ds', 'm3 挡力 ds', 0.0, 6.0, 0.1, 2.5, '{:.1f}', 'ds {:.1f}'),
    ('es', 'm3 限位 es', 0.0, 6.0, 0.1, 4.0, '{:.1f}', 'es {:.1f}'),
    ('sp', 'm3 吸附 sp', 0.5, 1.5, 0.05, 0.6, '{:.2f}', 'sp {:.2f}'),
    ('sb', 'm3 偏置 sb', 0.0, 0.49, 0.05, 0.0, '{:.2f}', 'sb {:.2f}'),
    ('pn', 'm3 下限 pn', -16.0, 16.0, 1.0, 0.0, '{:.0f}', 'pn {:.0f}'),
    ('px', 'm3 上限 px', -16.0, 16.0, 1.0, -1.0, '{:.0f}', 'px {:.0f}'),
    ('br', 'm4 边界 br(deg)', 5.0, 170.0, 1.0, 45.0, '{:.0f}', 'br {:.0f}'),
    ('kp', 'm4 回拉 kp', 0.0, 15.0, 0.1, 5.0, '{:.1f}', 'kp {:.1f}'),
    ('kd', 'm4 阻尼 kd', 0.0, 2.0, 0.01, 0.30, '{:.2f}', 'kd {:.2f}'),
    ('kf', 'm4 区轻阻尼 kf', 0.0, 0.5, 0.005, 0.02, '{:.3f}', 'kf {:.3f}'),
    ('vl', '力度上限 vl(%)', 5.0, 25.0, 1.0, 20.0, '{:.0f}', 'vl {:.0f}'),
]
def list_ports():
    return sorted(p.device for p in serial.tools.list_ports.comports())


class App:
    def __init__(self, root):
        self.root = root
        root.title('FOC2205 调试台 — 设备诊断 / 角度 / 控制')
        root.geometry('1240x920')
        root.minsize(1080, 820)
        self.ser = None
        self.reader_thread = None
        self.stop_evt = threading.Event()
        self.rxq = queue.Queue()
        self.model = PanelState()
        self.model.encoder_direction = ENCODER_DISPLAY_DIRECTION
        self.history = deque(maxlen=5000)
        self.log_lines = deque(maxlen=2000)
        self.last_summary = None
        self.timeout_stopped = False
        self.command_pending_until = 0.0
        self.spin_stop_at = 0.0
        self.record_file = None
        self.record_writer = None
        self.trace_file = None
        self.trace_writer = None
        self.haptic_history = deque(maxlen=12000)
        self.haptic_latest = None
        self.haptic_last_draw = 0.0
        self.tel_requested = False
        self.next_status_poll = 0.0
        self.last_record_flush = 0.0
        self.haptic_scales = {}
        self.haptic_mode_buttons = []
        self._build_ui()
        self._clear_values()
        self._enable_controls()
        root.protocol('WM_DELETE_WINDOW', self._close)
        root.bind('<Escape>', lambda event: self._emergency_stop())
        self.timer = root.after(POLL_MS, self._tick)

    def _build_ui(self):
        style = ttk.Style(self.root)
        style.theme_use('clam')
        style.configure('TLabel', font=('Microsoft YaHei UI', 10))
        style.configure('TLabelframe.Label', font=('Microsoft YaHei UI', 10, 'bold'))
        top = ttk.Frame(self.root, padding=10)
        top.pack(fill='x')
        self.btn_stop = tk.Button(
            self.root, text='紧急停止 · 立即释放功率级  [Esc]',
            font=('Microsoft YaHei UI', 12, 'bold'), bg='#ba2836', fg='white',
            activebackground='#8f1725', activeforeground='white',
            command=self._emergency_stop, height=2)
        self.btn_stop.pack(fill='x', padx=10, pady=(0, 8))
        ttk.Label(top, text='串口 115200 / 8N1').pack(side='left')
        ports = list_ports()
        self.port = ttk.Combobox(top, width=12, values=ports)
        self.port.set(ports[0] if ports else '')
        self.port.pack(side='left', padx=8)
        ttk.Button(top, text='刷新端口', command=self._refresh_ports).pack(side='left')
        self.btn_conn = ttk.Button(top, text='连接', command=self._toggle_conn)
        self.btn_conn.pack(side='left', padx=8)
        self.lbl_conn = ttk.Label(top, text='未连接')
        self.lbl_conn.pack(side='left')
        ttk.Label(top, text='遥测率:').pack(side='left', padx=(20, 2))
        self.tel_rate = tk.StringVar(value='50 Hz')
        tel_cb = ttk.Combobox(top, textvariable=self.tel_rate, width=8, state='readonly',
                              values=['关闭', '10 Hz', '20 Hz', '50 Hz', '100 Hz'])
        tel_cb.pack(side='left')
        tel_cb.bind('<<ComboboxSelected>>', self._telemetry_changed)
        self.banner = tk.Label(self.root, text='连接设备后读取健康状态', anchor='w',
                               bg='#e8edf4', fg='#28374d', padx=14, pady=10,
                               font=('Microsoft YaHei UI', 12, 'bold'))
        self.banner.pack(fill='x', padx=10)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=(0, 10))
        status_tab = ttk.Frame(self.notebook)
        haptic_tab = ttk.Frame(self.notebook)
        self.notebook.add(status_tab, text='设备与动作')
        self.notebook.add(haptic_tab, text='力反馈手感')
        status_shell = ttk.Frame(status_tab)
        status_shell.pack(fill='both', expand=True)
        self.status_canvas = tk.Canvas(status_shell, highlightthickness=0)
        status_scroll = ttk.Scrollbar(status_shell, orient='vertical',
                                      command=self.status_canvas.yview)
        self.status_canvas.configure(yscrollcommand=status_scroll.set)
        self.status_canvas.pack(side='left', fill='both', expand=True)
        status_scroll.pack(side='right', fill='y')
        status_body = ttk.Frame(self.status_canvas)
        status_window = self.status_canvas.create_window(
            (0, 0), window=status_body, anchor='nw')
        status_body.bind(
            '<Configure>',
            lambda event: self.status_canvas.configure(
                scrollregion=self.status_canvas.bbox('all')))
        self.status_canvas.bind(
            '<Configure>',
            lambda event: self.status_canvas.itemconfigure(
                status_window, width=event.width))
        self.status_canvas.bind(
            '<Enter>',
            lambda event: self.status_canvas.bind_all(
                '<MouseWheel>',
                lambda wheel: self.status_canvas.yview_scroll(
                    -int(wheel.delta / 120), 'units')))
        self.status_canvas.bind(
            '<Leave>',
            lambda event: self.status_canvas.unbind_all('<MouseWheel>'))
        body = ttk.Frame(status_body, padding=10)
        body.pack(fill='x')
        left = ttk.LabelFrame(body, text='MT6701 编码器', padding=10)
        left.pack(side='left', fill='y', padx=(0, 10))
        self.canvas = tk.Canvas(left, width=220, height=220, bg='#172337', highlightthickness=0)
        self.canvas.pack()
        cx = cy = 110
        for i in range(12):
            a = math.radians(i * 30 - 90)
            self.canvas.create_line(cx+85*math.cos(a), cy+85*math.sin(a),
                                    cx+98*math.cos(a), cy+98*math.sin(a), fill='#8092ac', width=2)
        for deg, x, y in [(0,110,30), (90,192,110), (180,110,190), (270,28,110)]:
            self.canvas.create_text(x, y, text=str(deg), fill='#c4d0e0')
        self.needle = self.canvas.create_line(110,110,110,35,fill='#44d7b6',width=4, state='hidden')
        self.angle_text = tk.StringVar(value='--.-°')
        ttk.Label(left, textvariable=self.angle_text, font=('Consolas', 26, 'bold')).pack(pady=2)
        current_title = ttk.Frame(left)
        current_title.pack(fill='x', pady=(0, 2))
        ttk.Label(current_title, text='三相电流', font=('Microsoft YaHei UI', 9, 'bold')).pack(side='left')
        ttk.Label(current_title, text='ADC LSB', foreground='#5a6474',
                  font=('Microsoft YaHei UI', 8)).pack(side='right')
        current_row = ttk.Frame(left)
        current_row.pack(fill='x', pady=(0, 5))
        self.current_vars = {}
        for index, (name, color) in enumerate((('A', '#d95f69'), ('B', '#3b82b8'),
                                               ('C', '#d58a2f'))):
            box = ttk.Frame(current_row)
            box.pack(side='left', expand=True, fill='x', padx=(0 if index == 0 else 5, 0))
            ttk.Label(box, text=name, foreground=color,
                      font=('Consolas', 10, 'bold')).pack(side='left')
            value = tk.StringVar(value='---')
            self.current_vars[name] = value
            ttk.Label(box, textvariable=value, anchor='e',
                      font=('Consolas', 15, 'bold')).pack(side='right', fill='x', expand=True)
        self.encoder_text = tk.StringVar(value='等待有效采样')
        ttk.Label(left, textvariable=self.encoder_text).pack()
        self.turns_text = tk.StringVar(value='相对累计  +0.000 圈')
        ttk.Label(left, textvariable=self.turns_text).pack(pady=4)
        ttk.Label(left, text='累计为轮询估算；中断后不跨段累加', font=('Microsoft YaHei UI', 8)).pack()
        right = ttk.Frame(body)
        right.pack(side='left', fill='both', expand=True)
        health = ttk.LabelFrame(right, text='健康状态与采样', padding=10)
        self.health_box = health
        health.pack(fill='x')
        self.health_vars = {}
        for label in ('驱动', '编码器', 'ADC', '控制', '固件'):
            row = ttk.Frame(health)
            row.pack(fill='x', pady=3)
            ttk.Label(row, text=label, width=7).pack(side='left')
            var = tk.StringVar(value='--')
            self.health_vars[label] = var
            ttk.Label(row, textvariable=var, font=('Microsoft YaHei UI', 10)).pack(side='left')
        self.fault_text = tk.StringVar(value='故障原因：等待设备状态')
        ttk.Label(health, textvariable=self.fault_text, foreground='#a72c36', wraplength=680).pack(anchor='w', pady=(6,0))
        control = ttk.LabelFrame(right, text='动作控制', padding=10)
        control.pack(fill='x', pady=8)
        row = ttk.Frame(control)
        row.pack(fill='x')
        self.drive_buttons = []
        for label, command in [('位置 +1 圈', 'rot 360\n'), ('位置 -1 圈', 'rot -360\n')]:
            btn = ttk.Button(row, text=label, command=lambda c=command: self._send(c))
            btn.pack(side='left', padx=(0,6))
            self.drive_buttons.append(btn)
        self.btn_recover = ttk.Button(row, text='检查并恢复', command=lambda: self._send('z'))
        self.btn_recover.pack(side='left')
        self.btn_cal = ttk.Button(row, text='开始慢速校准', command=lambda: self._send('a'))
        self.btn_cal.pack(side='left', padx=(8, 0))
        ttk.Label(control, text='位置按钮使用安全/低抖动档：0.05 圈/秒，vq≤512，kp=4/kd=0.2/ki=0',
                  foreground='#9a4e18', font=('Microsoft YaHei UI', 9)).pack(anchor='w', pady=(6,0))
        self.control_text = tk.StringVar(value='设备未就绪')
        ttk.Label(control, textvariable=self.control_text).pack(anchor='w', pady=(6,0))
        spin = ttk.LabelFrame(right, text='无限旋转 SPIN', padding=10)
        spin.pack(fill='x', pady=8)
        row = ttk.Frame(spin)
        row.pack(fill='x')
        ttk.Label(row, text='方向').pack(side='left', padx=(0,6))
        self.spin_dir = tk.IntVar(value=1)
        self.spin_dir_buttons = []
        for text, value in (('正向', 1), ('反向', -1)):
            btn = ttk.Radiobutton(row, text=text, value=value, variable=self.spin_dir)
            btn.pack(side='left', padx=(0,8))
            self.spin_dir_buttons.append(btn)
        ttk.Label(row, text='模式').pack(side='left', padx=(12,6))
        self.spin_mode = tk.StringVar(value='closed')
        self.spin_mode_buttons = []
        for text, value in (('闭环', 'closed'), ('开环', 'open')):
            btn = ttk.Radiobutton(row, text=text, value=value, variable=self.spin_mode,
                                  command=self._spin_mode_changed)
            btn.pack(side='left', padx=(0,8))
            self.spin_mode_buttons.append(btn)
        speed_row = ttk.Frame(spin)
        speed_row.pack(fill='x', pady=(7, 0))
        ttk.Label(speed_row, text='速度').pack(side='left', padx=(0,6))
        self.spin_speed_rpm = tk.IntVar(value=6)
        self.spin_speed_text = tk.StringVar(value='6 rpm')
        self.spin_speed_scale = tk.Scale(
            speed_row, from_=3, to=60, resolution=1, orient='horizontal', length=200,
            showvalue=False, variable=self.spin_speed_rpm,
            command=self._spin_speed_changed, font=('Microsoft YaHei UI', 9))
        self.spin_speed_scale.pack(side='left')
        self.spin_speed_scale.bind(
            '<ButtonRelease-1>', lambda event: self._apply_spin_speed())
        self.spin_speed_scale.bind(
            '<KeyRelease>', lambda event: self._apply_spin_speed())
        ttk.Label(speed_row, textvariable=self.spin_speed_text, width=7,
                  font=('Consolas', 10, 'bold')).pack(side='left', padx=(5, 8))
        self.spin_speed_preset_buttons = []
        for rpm in SPIN_SPEED_PRESETS:
            btn = ttk.Button(speed_row, text=str(rpm), width=3,
                             command=lambda value=rpm: self._set_spin_speed_preset(value))
            btn.pack(side='left', padx=1)
            self.spin_speed_preset_buttons.append(btn)
        row = ttk.Frame(spin)
        row.pack(fill='x', pady=(8,0))
        ttk.Label(row, text='力度上限').pack(side='left', padx=(0,6))
        self.spin_power = tk.IntVar(value=20)
        self.spin_scale = tk.Scale(row, from_=10, to=80, resolution=10, length=190,
                                   orient='horizontal', variable=self.spin_power,
                                   font=('Microsoft YaHei UI', 9))
        self.spin_scale.pack(side='left')
        self.spin_scale.bind('<ButtonRelease-1>', lambda event: self._apply_spin_power())
        self.btn_spin = ttk.Button(row, text='开始无限旋转', command=self._toggle_spin)
        self.btn_spin.pack(side='left', padx=(10,8))
        self.spin_status = tk.StringVar(value='待机')
        ttk.Label(row, textvariable=self.spin_status).pack(side='left')
        ttk.Label(spin, text='闭环最高 80%，开环最高 20%；电流环由 l 控制；主机 1 秒无命令自动减速释放。',
                  foreground='#9a4e18', font=('Microsoft YaHei UI', 9)).pack(anchor='w', pady=(6,0))
        vel_row = ttk.Frame(spin)
        vel_row.pack(fill='x', pady=(7,0))
        ttk.Label(vel_row, text='闭环速度环').pack(side='left', padx=(0,6))
        self.spin_vp = tk.DoubleVar(value=SPIN_VEL_KP_DEFAULT)
        self.spin_vi = tk.DoubleVar(value=SPIN_VEL_KI_DEFAULT)
        self.spin_vff = tk.DoubleVar(value=SPIN_VEL_FF_DEFAULT)
        self.spin_vfr = tk.DoubleVar(value=SPIN_VEL_FR_DEFAULT)
        self.spin_vel_controls = []
        for label, var, lo, hi, inc in (
                ('P', self.spin_vp, 0.0, 0.2, 0.001),
                ('I', self.spin_vi, 0.0, 2.0, 0.005),
                ('前馈', self.spin_vff, 0.0, 0.2, 0.005),
                ('摩擦', self.spin_vfr, 0.0, 500.0, 10.0)):
            ttk.Label(vel_row, text=label).pack(side='left', padx=(4,1))
            box = ttk.Spinbox(vel_row, width=6, from_=lo, to=hi, increment=inc,
                              textvariable=var, format='%.3f')
            box.pack(side='left')
            self.spin_vel_controls.append(box)
        self.btn_spin_vel = ttk.Button(vel_row, text='应用', command=self._apply_spin_velocity)
        self.btn_spin_vel.pack(side='left', padx=(8,0))
        ttk.Label(spin, text='闭环采用速度 PI + 同步换向前馈，低速不再在静摩擦点卡跳；开环为固定电压矢量。',
                  foreground='#52637a', font=('Microsoft YaHei UI', 9)).pack(anchor='w', pady=(5,0))
        manual = ttk.LabelFrame(right, text='三相手动调试', padding=10)
        manual.pack(fill='x')
        ttk.Label(manual, text='调制幅度不代表电流限制。最后一次操作后 30 秒自动释放。',
                  foreground='#9a4e18', font=('Microsoft YaHei UI',9)).pack(anchor='w')
        row = ttk.Frame(manual)
        row.pack(fill='x', pady=6)
        self.btn_manual = ttk.Button(row, text='进入手动（中性）', command=self._toggle_manual)
        self.btn_manual.pack(side='left', padx=(0,10))
        self.phase_buttons = []
        for i, name in enumerate('ABC'):
            btn = ttk.Button(row, text=f'{name} 低', width=7, command=lambda i=i: self._toggle_phase(i))
            btn.pack(side='left', padx=3)
            self.phase_buttons.append(btn)
        row = ttk.Frame(manual)
        row.pack(fill='x')
        ttk.Label(row, text='幅度').pack(side='left', padx=(0,8))
        self.pct = tk.IntVar(value=10)
        self.pct_buttons = []
        for pct in (5,10,15,20):
            btn = ttk.Radiobutton(row, text=f'{pct}%', value=pct, variable=self.pct, command=self._send_pct)
            btn.pack(side='left', padx=6)
            self.pct_buttons.append(btn)
        log = ttk.LabelFrame(status_tab, text='设备日志', padding=8)
        log.pack(fill='both', expand=True, padx=10, pady=(0,10))
        actions = ttk.Frame(log)
        actions.pack(fill='x', pady=(0,6))
        self.read_buttons = []
        for label, command in [('读故障寄存器', 'f'), ('读取参数', 'd'), ('帮助', 'h')]:
            btn = ttk.Button(actions, text=label, command=lambda c=command: self._send(c))
            btn.pack(side='left', padx=(0,6))
            self.read_buttons.append(btn)
        ttk.Button(actions, text='导出采样 CSV', command=self._export_csv).pack(side='right')
        ttk.Button(actions, text='保存日志', command=self._export_log).pack(side='right', padx=6)
        self.txt = tk.Text(log, height=8, wrap='word', font=('Consolas',9), state='disabled')
        scroll = ttk.Scrollbar(log, orient='vertical', command=self.txt.yview)
        scroll.pack(side='right', fill='y')
        self.txt.configure(yscrollcommand=scroll.set)
        self.txt.pack(fill='both', expand=True)
        self._build_haptic_tab(haptic_tab)

    def _build_haptic_tab(self, tab):
        left = ttk.LabelFrame(tab, text='m0–m4 手感模式', padding=10)
        left.pack(side='left', fill='y', padx=(10, 8), pady=10)
        modes = ttk.Frame(left)
        modes.pack(fill='x')
        for i in sorted(HAPTIC_MODE_NAMES):
            name = HAPTIC_MODE_NAMES[i]
            b = ttk.Button(modes, text=f'm{i} {name}', width=12,
                           command=lambda i=i: self._send(f'm{i}\n'))
            b.grid(row=i // 2, column=i % 2, padx=3, pady=3, sticky='ew')
            self.haptic_mode_buttons.append(b)
        modes.columnconfigure(0, weight=1)
        modes.columnconfigure(1, weight=1)
        row = ttk.Frame(left)
        row.pack(fill='x', pady=(8, 4))
        ttk.Button(row, text='当前位置设中心', command=lambda: self._send('cd\n')).pack(side='left')
        ttk.Button(row, text='释放输出', command=lambda: self._send('s')).pack(side='left', padx=6)
        ttk.Label(left, text='参数松开发送；m3/m4 共用中心。', foreground='#5a6474').pack(anchor='w')

        params_box = ttk.Frame(left)
        params_box.pack(fill='both', expand=True, pady=(4, 0))
        self.haptic_param_canvas = tk.Canvas(params_box, highlightthickness=0, width=390)
        param_scroll = ttk.Scrollbar(params_box, orient='vertical',
                                     command=self.haptic_param_canvas.yview)
        self.haptic_param_canvas.configure(yscrollcommand=param_scroll.set)
        self.haptic_param_canvas.pack(side='left', fill='both', expand=True)
        param_scroll.pack(side='right', fill='y')
        param_inner = ttk.Frame(self.haptic_param_canvas)
        param_window = self.haptic_param_canvas.create_window(
            (0, 0), window=param_inner, anchor='nw')
        param_inner.bind(
            '<Configure>',
            lambda event: self.haptic_param_canvas.configure(
                scrollregion=self.haptic_param_canvas.bbox('all')))
        self.haptic_param_canvas.bind(
            '<Configure>',
            lambda event: self.haptic_param_canvas.itemconfigure(
                param_window, width=event.width))
        self.haptic_param_canvas.bind(
            '<Enter>',
            lambda event: self.haptic_param_canvas.bind_all(
                '<MouseWheel>',
                lambda wheel: self.haptic_param_canvas.yview_scroll(
                    -1 if wheel.delta > 0 else 1, 'units')))
        self.haptic_param_canvas.bind(
            '<Leave>',
            lambda event: self.haptic_param_canvas.unbind_all('<MouseWheel>'))

        for key, label, lo, hi, res, dft, shown, wire in HAPTIC_PARAMS:
            row = ttk.Frame(param_inner)
            row.pack(fill='x', pady=1)
            ttk.Label(row, text=label, width=19).pack(side='left')
            val = ttk.Label(row, text=shown.format(dft), width=7, anchor='e')
            val.pack(side='right')
            sc = tk.Scale(row, from_=lo, to=hi, resolution=res, orient='horizontal',
                          showvalue=False, length=180)
            sc.set(dft)
            sc.pack(side='left', fill='x', expand=True)
            sc.bind('<ButtonRelease-1>', lambda e, k=key, f=wire: self._apply_haptic_param(k, f))
            sc.bind('<KeyRelease>', lambda e, k=key, f=wire: self._apply_haptic_param(k, f))
            self.haptic_scales[key] = (sc, val, shown, wire)

        right = ttk.LabelFrame(tab, text='实时曲线 / MT6701 原生角度', padding=10)
        right.pack(side='left', fill='both', expand=True, padx=(2, 10), pady=10)
        self.haptic_live = tk.StringVar(value='连接后等待 $T 遥测')
        ttk.Label(right, textvariable=self.haptic_live, font=('Consolas', 11),
                  wraplength=480, justify='left').pack(anchor='w')
        self.haptic_canvas = tk.Canvas(right, bg='#111a2a', highlightthickness=0, height=520)
        self.haptic_canvas.pack(fill='both', expand=True, pady=(8, 0))
        ttk.Label(right, text='上：角度/目标(deg)  中：速度(rad/s)  下：力矩(Q12)',
                  foreground='#5a6474').pack(anchor='w', pady=(5, 0))

    def _apply_haptic_param(self, key, wire):
        sc, val, shown, _ = self.haptic_scales[key]
        x = sc.get()
        val.configure(text=shown.format(x))
        if self.ser:
            self._send((wire.format(x) + '\n'))

    def _telemetry_changed(self, event=None):
        text = self.tel_rate.get()
        hz = 0 if text == '关闭' else int(text.split()[0])
        self.tel_requested = True
        if self.ser:
            self._send(f'tel {hz}\n')

    def _refresh_ports(self):
        self.port['values'] = list_ports()

    def _toggle_conn(self):
        self._disconnect() if self.ser else self._connect()

    def _connect(self):
        try:
            port = serial.Serial(self.port.get(), 115200, timeout=0.1, write_timeout=0.2)
        except (serial.SerialException, ValueError) as exc:
            self._log(f'打开串口失败：{exc}')
            return
        self.ser = port
        self.model = PanelState()
        self.model.encoder_direction = ENCODER_DISPLAY_DIRECTION
        self.last_summary = None
        self.timeout_stopped = False
        self.command_pending_until = 0
        self.spin_stop_at = 0.0
        self.tel_requested = False
        self.next_status_poll = 0.0
        self.haptic_history.clear()
        self.haptic_latest = None
        self.rxq = queue.Queue()
        self.stop_evt = threading.Event()
        self.reader_thread = threading.Thread(target=self._reader, args=(port,self.stop_evt,self.rxq), daemon=True)
        self.reader_thread.start()
        self.port.configure(state='disabled')
        self.btn_conn.configure(text='断开')
        self.lbl_conn.configure(text=f'{port.port} 已打开 / 等待状态')
        self._log(f'已连接 {port.port}，等待诊断协议')
        try:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            stamp = f'{datetime.now():%Y%m%d-%H%M%S-%f}'
            self.record_path = LOG_DIR / f'panel-{stamp}.csv'
            self.record_file = self.record_path.open('w',encoding='utf-8-sig',newline='')
            self.record_writer = None
            self.trace_path = LOG_DIR / f'haptic-{stamp}.csv'
            self.trace_file = self.trace_path.open('w',encoding='utf-8-sig',newline='')
            self.trace_writer = None
            self._log(f'采样自动记录：{self.record_path.name} / {self.trace_path.name}')
        except OSError as exc:
            self._log(f'记录文件不可用：{exc}')
        self._send('s')
        self._send('?\n')
        self._enable_controls()

    @staticmethod
    def _reader(port, stop_evt, rxq):
        buf = b''
        try:
            while not stop_evt.is_set():
                buf += port.read(1024)
                while b'\n' in buf:
                    line, buf = buf.split(b'\n',1)
                    rxq.put(('line',line.decode('utf-8','replace').strip()))
                if len(buf) > 8192:
                    buf = b''
                    rxq.put(('line','接收行过长，已丢弃'))
        except (serial.SerialException, OSError) as exc:
            if not stop_evt.is_set():
                rxq.put(('error',str(exc)))

    def _disconnect(self):
        if not self.ser:
            return
        port, self.ser = self.ser, None
        self.stop_evt.set()
        try:
            port.write(b'tel 0\ns\n')
            port.close()
        except (serial.SerialException, OSError):
            port.close()
        if self.reader_thread:
            self.reader_thread.join(timeout=0.4)
        if self.record_file:
            self.record_file.close()
            self.record_file = self.record_writer = None
        if self.trace_file:
            self.trace_file.close()
            self.trace_file = self.trace_writer = None
        self.tel_requested = False
        self.model = PanelState()
        self.model.encoder_direction = ENCODER_DISPLAY_DIRECTION
        self.port.configure(state='normal')
        self.btn_conn.configure(text='连接')
        self.lbl_conn.configure(text='未连接')
        self._log('已断开；已尝试发送释放命令')
        self._clear_values()
        self._enable_controls()

    def _send(self, command):
        if not self.ser:
            return False
        now = time.monotonic()
        cmd = command.strip()
        word = cmd.split()[0] if cmd else ''
        haptic_params = {p[0] for p in HAPTIC_PARAMS}
        if cmd == 'a':
            allowed = self.model.can_calibrate(now)
        elif cmd == 'A':
            allowed = self.model.calibration_active(now)
        elif cmd == 'z':
            allowed = self.model.can_recover(now)
        elif cmd.startswith(('x','w')):
            allowed = self.model.can_manual(now)
        elif cmd in ('p', 'P'):
            allowed = self.model.can_drive(now)
        elif cmd[:1] in ('V', 'W', '#'):
            allowed = self.model.can_spin_control(now)
        elif cmd.startswith(('vp ', 'vi ', 'vff ', 'vfr ', 'rpm ')):
            allowed = self.model.can_spin_control(now)
        elif cmd.startswith('tel ') or cmd in ('s','?','f','d','h','estop'):
            allowed = True
        elif (cmd in {f'm{i}' for i in range(5)} or cmd == 'cd' or
              word in haptic_params or word == 'rot'):
            allowed = self.model.can_haptic(now)
        elif cmd == 'g':
            allowed = True
        else:
            allowed = self.model.can_drive(now)
        if not allowed:
            self._log('设备未就绪，命令未发送：'+cmd)
            return False
        try:
            self.ser.write(command.encode('ascii'))
            flush = getattr(self.ser, 'flush', None)
            if flush:
                flush()
        except (serial.SerialException, OSError) as exc:
            self._log('串口写入失败：'+str(exc))
            self._disconnect()
            return False
        if cmd != '?':
            self._log('TX '+cmd)
        if cmd.startswith('tel '):
            self.tel_requested = True
        if (cmd in ('a','A','m','r','R','z','p','P','cd') or
                cmd in {f'm{i}' for i in range(5)} or
                cmd.startswith(('x','w','V','W','#','rot ','vp ','vi ','vff ','vfr ','rpm ')) or
                word in haptic_params):
            self.command_pending_until = now + 0.3
        return True

    def _emergency_stop(self):
        self.command_pending_until = 0.0
        self.spin_stop_at = 0.0
        self.spin_status.set('紧急停止：等待功率级释放确认')
        self._send('estop\n')

    def _toggle_manual(self):
        if self.model.can_manual(time.monotonic()):
            self._send('g')
        else:
            # The selected amplitude is sent together with neutral entry. No
            # optimistic phase state and no automatic keepalive from the UI.
            self._send('mw%d' % (self.pct.get()//5))
            self.command_pending_until = time.monotonic()+0.3

    def _toggle_phase(self, phase):
        status = self.model.status
        if status and self.model.can_manual(time.monotonic()):
            self._send('x%d' % (status['mask'] ^ (1<<phase)))

    def _send_pct(self):
        if self.model.can_manual(time.monotonic()):
            self._send('w%d' % (self.pct.get()//5))

    def _spin_speed_changed(self, event=None):
        rpm = max(3, min(60, int(round(float(self.spin_speed_rpm.get())))))
        self.spin_speed_text.set(f'{rpm} rpm')
        if not self.model.spin_active(time.monotonic()):
            self.spin_status.set(f'速度设定 {rpm} rpm ({rpm/60.0:.3f} 圈/秒)')

    def _set_spin_speed_preset(self, rpm):
        self.spin_speed_rpm.set(rpm)
        self._spin_speed_changed()
        self._apply_spin_speed()

    def _apply_spin_speed(self):
        rpm = max(3, min(60, int(round(float(self.spin_speed_rpm.get())))))
        self.spin_speed_rpm.set(rpm)
        self.spin_speed_text.set(f'{rpm} rpm')
        if self.model.spin_active(time.monotonic()):
            self._send(f'rpm {rpm}\n')

    def _apply_spin_velocity(self):
        for name, var in (('vp', self.spin_vp), ('vi', self.spin_vi),
                          ('vff', self.spin_vff), ('vfr', self.spin_vfr)):
            try:
                value = float(var.get())
            except (tk.TclError, ValueError):
                self._log(f'速度环参数 {name} 无效')
                return
            self._send(f'{name} {value:.6f}\n')
            time.sleep(0.02)
        self.spin_status.set('闭环速度环参数已发送')

    def _spin_mode_changed(self):
        is_open = self.spin_mode.get() == 'open'
        mode = '开环' if is_open else '闭环'
        self.spin_scale.configure(to=SPIN_OPENLOOP_POWER_MAX if is_open else 80)
        if is_open and self.spin_power.get() > SPIN_OPENLOOP_POWER_MAX:
            self.spin_power.set(SPIN_OPENLOOP_POWER_MAX)
        self.spin_status.set(f'{mode}模式待启动')

    def _apply_spin_power(self):
        cap = SPIN_OPENLOOP_POWER_MAX if self.spin_mode.get() == 'open' else 80
        pct = max(10, min(cap, int(round(self.spin_power.get() / 10.0)) * 10))
        self.spin_power.set(pct)
        if self.model.spin_active(time.monotonic()):
            self._send('W%d\n' % (pct // 10))

    def _toggle_spin(self):
        now = time.monotonic()
        if self.model.spin_active(now):
            self._send('s\n')
            self.spin_stop_at = now
            self.spin_status.set('减速停止中…')
            return
        if not self.model.can_drive(now):
            self._log('设备未就绪，未启动无限旋转')
            return
        rpm = max(3, min(60, int(round(float(self.spin_speed_rpm.get())))))
        rps = rpm / 60.0
        cap = SPIN_OPENLOOP_POWER_MAX if self.spin_mode.get() == 'open' else 80
        pct = max(10, min(cap, int(round(self.spin_power.get() / 10.0)) * 10))
        self.spin_power.set(pct)
        mode = 1 if self.spin_mode.get() == 'open' else 0
        self._send('#%d\n' % mode)
        time.sleep(0.02)
        self._send('rpm %d\n' % rpm)
        time.sleep(0.02)
        self._send('W%d\n' % (pct // 10))
        time.sleep(0.02)
        if mode == 0:
            self._apply_spin_velocity()
        self._send('p\n' if self.spin_dir.get() > 0 else 'P\n')
        self.spin_stop_at = 0
        self.spin_status.set(f"启动中：{'开环' if mode else '闭环'} {rpm} rpm，力度上限 {pct}%")

    def _enable_controls(self):
        now = time.monotonic()
        ready = self.ser is not None and self.model.can_drive(now)
        haptic = self.ser is not None and self.model.can_haptic(now)
        manual = self.ser is not None and self.model.can_manual(now)
        spin = self.ser is not None and self.model.spin_active(now)
        pending = now < self.command_pending_until
        for button in self.drive_buttons:
            button.configure(state='normal' if ready and not pending else 'disabled')
        self.btn_manual.configure(state='normal' if (ready or manual) and not pending else 'disabled',
                                  text='退出手动（释放）' if manual else '进入手动（中性）')
        for button in self.phase_buttons:
            button.configure(state='normal' if manual and not pending else 'disabled')
        for button in self.pct_buttons:
            button.configure(state='normal' if (ready or manual) and not pending else 'disabled')
        for button in self.spin_dir_buttons:
            button.configure(state='normal' if ready and not pending else 'disabled')
        for button in self.spin_mode_buttons:
            button.configure(state='normal' if ready and not spin and not pending else 'disabled')
        self.spin_speed_scale.configure(
            state='normal' if (ready or spin) and not pending else 'disabled')
        for button in self.spin_speed_preset_buttons:
            button.configure(
                state='normal' if (ready or spin) and not pending else 'disabled')
        self.spin_scale.configure(
            state='normal' if (ready or spin) and not pending else 'disabled')
        vel_state = ('normal' if (ready or spin) and
                     self.spin_mode.get() != 'open' and not pending else 'disabled')
        for box in self.spin_vel_controls:
            box.configure(state=vel_state)
        self.btn_spin_vel.configure(state=vel_state)
        if spin:
            self.btn_spin.configure(state='normal', text='停止无限旋转')
        elif ready and not pending:
            self.btn_spin.configure(state='normal', text='开始无限旋转')
        else:
            self.btn_spin.configure(state='disabled', text='开始无限旋转')
        self.btn_recover.configure(state='normal' if self.ser and self.model.can_recover(now) and not pending else 'disabled')
        calibration_active = self.ser is not None and self.model.calibration_active(now)
        calibration_allowed = self.ser is not None and self.model.can_calibrate(now)
        self.btn_cal.configure(
            state='normal' if (calibration_active or calibration_allowed) and not pending else 'disabled',
            text='取消校准' if calibration_active else '开始慢速校准',
            command=(lambda: self._send('A')) if calibration_active else (lambda: self._send('a')))
        for button in self.haptic_mode_buttons:
            button.configure(state='normal' if haptic and not pending else 'disabled')
        for sc, _val, _shown, _wire in self.haptic_scales.values():
            sc.configure(state='normal' if haptic and not pending else 'disabled')
        for button in self.read_buttons+[self.btn_stop]:
            button.configure(state='normal' if self.ser else 'disabled')

    def _clear_values(self):
        self.health_box.configure(text='健康状态与采样')
        self.angle_text.set('--.-°')
        self.encoder_text.set('等待有效采样')
        self.turns_text.set('相对累计  +0.000 圈')
        self.canvas.itemconfigure(self.needle, state='hidden')
        for var in self.current_vars.values():
            var.set('---')
        for var in self.health_vars.values():
            var.set('--')
        self.fault_text.set('故障原因：等待设备状态')
        self.control_text.set('设备未就绪')
        self.spin_status.set('待机')
        self.haptic_live.set('连接后等待 $T 遥测')
        for button in self.haptic_mode_buttons:
            button.state(['!pressed'])
        self.banner.configure(text='未连接',bg='#e8edf4',fg='#28374d')
        for i, button in enumerate(self.phase_buttons):
            button.configure(text=f"{'ABC'[i]} 关闭")

    def _show_currents(self, ia, ib, ic, valid):
        values = (ia, ib, ic) if valid else (None, None, None)
        for name, value in zip('ABC', values):
            self.current_vars[name].set('---' if value is None else f'{value:+d}')

    def _update(self, status):
        self.health_box.configure(text='健康状态与采样')
        now = time.monotonic()
        if self.model.accept(status,now):
            self._log('检测到设备重启，累计角度已重置')
        self.timeout_stopped = False
        v = status.values
        raw_display = (v['ang'] if ENCODER_DISPLAY_DIRECTION > 0
                       else (-v['ang']) & 0x3fff)
        deg = raw_display * 360.0/16384
        self.angle_text.set(f'{deg:.1f}°' if v['encok'] else '--.-°')
        self.encoder_text.set(f"raw {raw_display} / CRC失败 {v['crc']}" if v['encok'] else f"采样无效 / CRC失败 {v['crc']}")
        self.turns_text.set(f'相对累计  {self.model.turns:+.3f} 圈')
        self._show_currents(v['ia'], v['ib'], v['ic'], v['adcok'])
        a = math.radians(deg-90)
        self.canvas.coords(self.needle,110,110,110+76*math.cos(a),110+76*math.sin(a))
        self.canvas.itemconfigure(self.needle,state='normal' if v['encok'] else 'hidden')
        drv = '配置与状态通过' if v['drvok'] else '不可用 / 供电或 SPI 异常'
        self.health_vars['驱动'].set(f"{drv}   IC_STAT=0x{v['drv']:02X}   BRK={v['brk']}")
        fields = {0:'正常',1:'过强',2:'过弱',3:'异常'}
        self.health_vars['编码器'].set(f"{'CRC有效' if v['encok'] else '无效'}   磁场={fields[v['mg']&3] if v['encok'] else '--'}   按压={(v['mg']>>2)&1 if v['encok'] else '--'}")
        label = ('校零后 LSB' if v['drvok'] else '校零后 LSB / 驱动不可用') if v['cal'] else '原始 LSB / 未标定有效电流'
        values = f"{v['ia']} / {v['ib']} / {v['ic']}" if v['adcok'] else '-- / -- / --'
        self.health_vars['ADC'].set(f"{values}   {label}   超时={v['adce']}")
        cal_text = ('空闲' if v['calst'] == 0 else
                    '进行中' if 1 <= v['calst'] <= 6 else
                    '成功' if v['calst'] == 7 else
                    '已取消' if v['calst'] == 8 else '失败')
        self.health_vars['控制'].set(f"{STATE_NAMES[v['st']]}   对齐={v['aligned']}   PWM输出使能={v['out']}   校准={cal_text} 峰值={v['calpk']}LSB")
        self.health_vars['固件'].set(f"{v['fw']}   stage={v['stage']}   ISR={v['hz']} Hz   uptime={v['up']/1000:.1f}s")
        self.fault_text.set('故障原因：'+status.fault_text)
        self.control_text.set(f"调制 q={v['vq']} Q12   误差={v['err']} raw   速度={v['vel']} raw/s")
        for i, button in enumerate(self.phase_buttons):
            level = ('高' if v['mask']&(1<<i) else '低') if v['mode'] == 1 else '关闭'
            button.configure(text=f"{'ABC'[i]} {level}")
        if v['mode'] == 1 and v['pct'] in (5,10,15,20):
            self.pct.set(v['pct'])
        haptic_mode = v['hm'] if v['mode'] == 3 else None
        for i, button in enumerate(self.haptic_mode_buttons):
            button.state(['pressed'] if haptic_mode == i else ['!pressed'])
        if v['mode'] == 3:
            self.spin_status.set(f"力反馈 m{v['hm']} {status.haptic_name} 运行中 · 松开转动手感")
        elif v['mode'] == 2:
            is_open = bool(v.get('open'))
            rpm = v.get('vfb', v['vel']) * 60.0 / 16384.0
            target_rpm = v.get('vsp', v['vel']) * 60.0 / 16384.0
            self.spin_mode.set('open' if is_open else 'closed')
            self.spin_scale.configure(to=SPIN_OPENLOOP_POWER_MAX if is_open else 80)
            if is_open and self.spin_power.get() > SPIN_OPENLOOP_POWER_MAX:
                self.spin_power.set(SPIN_OPENLOOP_POWER_MAX)
            if not is_open and now >= self.command_pending_until:
                target_rpm_int = int(round(target_rpm))
                if 3 <= target_rpm_int <= 60:
                    self.spin_speed_rpm.set(target_rpm_int)
                    self.spin_speed_text.set(f'{target_rpm_int} rpm')
            if self.spin_stop_at and now - self.spin_stop_at < 2.5:
                self.spin_status.set(f'减速停止中：{rpm:+.1f} rpm')
            elif not is_open:
                self.spin_status.set(
                    f"闭环运行：目标 {target_rpm:+.1f} / 实测 {rpm:+.1f} rpm，"
                    f"误差 {v.get('verr', 0)} raw/s，vq={v['vq']}")
            else:
                self.spin_status.set(
                    f"开环运行：{rpm:+.1f} rpm，力度上限 {v['pct']}%，vq={v['vq']}")
        elif v['st'] == 1:
            self.spin_status.set('其他动作运行中')
        else:
            self.spin_status.set('待机')
            self.spin_stop_at = 0
        if v['st'] == 3:
            text, bg, fg = '故障锁存 · 功率输出已释放', '#fae4e6', '#972936'
            if not v['aligned']:
                text += ' · 排除故障后重新启动完成标定'
        elif v['st'] == 1:
            text, bg, fg = ('力反馈手感运行中 · ' + status.haptic_name if v['mode'] == 3 else
                            '无限旋转运行中' if v['mode'] == 2 else
                            '手动调试运行中' if v['mode'] == 1 else '动作执行中'), '#fff0cf', '#815000'
        elif status.drive_ready:
            text, bg, fg = '设备就绪 · 等待动作指令', '#dbf4e9', '#176249'
        else:
            text, bg, fg = '诊断可用 · 运动条件未满足', '#e8edf4', '#28374d'
        if v['out'] and v['st'] == 3:
            text = '故障状态仍有 PWM 使能，请立即检查硬件'
        self.banner.configure(text=text,bg=bg,fg=fg)
        self.lbl_conn.configure(text=f'{self.ser.port} 通信正常')
        summary = (v['st'],v['mode'],v['hm'],v['fault'],v['drvok'],v['encok'],v['cal'])
        if summary != self.last_summary:
            self._log(f"状态：{STATE_NAMES[v['st']]}；{status.fault_text}")
            self.last_summary = summary
        row = {'host_time':datetime.now().isoformat(timespec='milliseconds'), 'port':self.ser.port, **v}
        self.history.append(row)
        if self.record_file:
            try:
                if self.record_writer is None:
                    self.record_writer = csv.DictWriter(self.record_file,fieldnames=list(row))
                    self.record_writer.writeheader()
                self.record_writer.writerow(row)
            except (OSError,ValueError) as exc:
                self._log('采样记录停止：'+str(exc))
                self.record_file.close()
                self.record_file = self.record_writer = None
        if not self.tel_requested:
            text = self.tel_rate.get()
            hz = 0 if text == '关闭' else int(text.split()[0])
            self._send(f'tel {hz}\n')

    def _accept_telemetry(self, telemetry):
        now = time.monotonic()
        row = {
            'host_time': datetime.now().isoformat(timespec='milliseconds'),
            'port': self.ser.port if self.ser else '',
            **telemetry.values,
        }
        self.haptic_history.append((now, telemetry))
        self.haptic_latest = telemetry
        v = telemetry.values
        if all(key in v for key in ('ia', 'ib', 'ic', 'adcok')):
            self._show_currents(v['ia'], v['ib'], v['ic'], v['adcok'])
        if 'raw' in v and (self.model.status is None or self.model.status['encok']):
            raw = (v['raw'] if ENCODER_DISPLAY_DIRECTION > 0
                   else (-v['raw']) & 0x3fff)
            deg = raw * 360.0 / 16384.0
            self.angle_text.set(f'{deg:.1f}°')
            self.encoder_text.set(f'raw {raw} / ISR {v["hz"]} Hz')
            a = math.radians(deg - 90)
            self.canvas.coords(self.needle, 110, 110,
                               110 + 76 * math.cos(a), 110 + 76 * math.sin(a))
            self.canvas.itemconfigure(self.needle, state='normal')
        self.haptic_live.set(
            f"m{v['hm']} {HAPTIC_MODE_NAMES[v['hm']]} | "
            f"ang {v['ang']:+8.2f}°  tgt {v['tgt']:+8.2f}°\n"
            f"vel {v['vel']:+7.2f} rad/s | tq {v['tq']:+6d} Q12\n"
            f"pos {v['pos']:+d} | sub {v['sub']:+.2f} | {v['hz']} Hz")
        if self.trace_file:
            try:
                if self.trace_writer is None:
                    self.trace_writer = csv.DictWriter(self.trace_file, fieldnames=list(row))
                    self.trace_writer.writeheader()
                self.trace_writer.writerow(row)
            except (OSError, ValueError) as exc:
                self._log('手感遥测记录停止：'+str(exc))
                self.trace_file.close()
                self.trace_file = self.trace_writer = None

    def _draw_haptic_curves(self):
        now = time.monotonic()
        if now - self.haptic_last_draw < 0.1 or not self.haptic_history:
            return
        self.haptic_last_draw = now
        cutoff = now - 10.0
        rows = [t.values for ts, t in self.haptic_history if ts >= cutoff]
        if len(rows) < 2:
            return
        c = self.haptic_canvas
        w = max(320, c.winfo_width())
        h = max(260, c.winfo_height())
        pad = 34
        band = (h - 2 * pad) / 3.0
        c.delete('trace')
        for i, label in enumerate(('ANGLE deg', 'VEL rad/s', 'TQ Q12')):
            y0 = pad + i * band
            c.create_line(28, y0, w - 8, y0, fill='#33415a', tags='trace')
            c.create_line(28, y0 + band - 4, w - 8, y0 + band - 4,
                          fill='#202d44', tags='trace')
            c.create_text(4, y0 + 3, text=label, anchor='nw', fill='#8fa3c4',
                          font=('Consolas', 8), tags='trace')

        def line(vals, idx, color):
            lo = min(vals)
            hi = max(vals)
            if hi - lo < 1e-9:
                lo -= 1.0
                hi += 1.0
            y0 = pad + idx * band
            pts = []
            for j, val in enumerate(vals):
                x = 30 + (w - 40) * j / max(1, len(vals) - 1)
                y = y0 + band - 8 - (band - 16) * (val - lo) / (hi - lo)
                pts.extend((x, y))
            if len(pts) >= 4:
                c.create_line(*pts, fill=color, width=1.5, tags='trace')
            c.create_text(w - 8, y0 + 2, text=f'max {hi:.2f} min {lo:.2f}',
                          anchor='ne', fill='#7186a8', font=('Consolas', 8), tags='trace')

        line([r['ang'] for r in rows], 0, '#4fd1c5')
        line([r['tgt'] for r in rows], 0, '#f6ad55')
        line([r['vel'] for r in rows], 1, '#63b3ed')
        line([r['tq'] for r in rows], 2, '#f687b3')

    def _tick(self):
        now = time.monotonic()
        for _ in range(200):
            try:
                kind,line = self.rxq.get_nowait()
            except queue.Empty:
                break
            if kind == 'error':
                self._log('串口读取失败：'+line)
                self._disconnect()
                break
            if line.startswith('$T,'):
                telemetry = Telemetry.parse(line)
                if telemetry and self.ser:
                    self._accept_telemetry(telemetry)
                continue
            if line.startswith('#FOC,'):
                status = Status.parse(line)
                if status and self.ser:
                    self._update(status)
                elif self.last_summary != 'invalid':
                    self._send('s')
                    self.model = PanelState()
                    self.model.encoder_direction = ENCODER_DISPLAY_DIRECTION
                    self._clear_values()
                    self._log('状态帧缺失或协议不兼容，要求 proto=3 / diag=1；控制已禁用')
                    self.last_summary = 'invalid'
            elif line and not line.startswith('isr='):
                self._log(line)
        self._draw_haptic_curves()
        if self.record_file and now - self.last_record_flush >= 0.5:
            try:
                self.record_file.flush()
                if self.trace_file:
                    self.trace_file.flush()
                self.last_record_flush = now
            except OSError as exc:
                self._log('采样刷新失败：'+str(exc))
        if self.ser:
            if not self.model.fresh(now):
                self.health_box.configure(text='健康状态与采样（等待更新 / 上次状态）')
                self.lbl_conn.configure(text=f'{self.ser.port} 等待状态 / 超时')
                self.banner.configure(text='等待有效诊断帧 / 通信超时 · 动作控制已禁用',bg='#fff0cf',fg='#815000')
                self.angle_text.set('--.-°')
                self.canvas.itemconfigure(self.needle,state='hidden')
                if self.model.status and not self.timeout_stopped:
                    self._send('s')
                    self.timeout_stopped = True
                    self._log('状态超过 2 秒未更新，已尝试释放输出')
            if now >= self.next_status_poll:
                self._send('?\n')
                interval = 0.5 if self.tel_rate.get() != '关闭' else POLL_MS / 1000.0
                self.next_status_poll = now + interval
        self._enable_controls()
        self.timer = self.root.after(POLL_MS,self._tick)

    def _log(self, text):
        line = datetime.now().strftime('%H:%M:%S ')+text
        self.log_lines.append(line)
        self.txt.configure(state='normal')
        self.txt.insert('end',line+'\n')
        count = int(self.txt.index('end-1c').split('.')[0])
        if count > 800:
            self.txt.delete('1.0',f'{count-800}.0')
        self.txt.see('end')
        self.txt.configure(state='disabled')

    def _export_csv(self):
        if not self.history:
            self._log('暂无采样可导出')
            return
        path = filedialog.asksaveasfilename(title='导出最近 5000 帧',defaultextension='.csv',filetypes=[('CSV','*.csv')])
        if path:
            try:
                rows = list(self.history)
                keys = list(dict.fromkeys(key for row in rows for key in row))
                with open(path,'w',encoding='utf-8-sig',newline='') as stream:
                    writer = csv.DictWriter(stream,fieldnames=keys)
                    writer.writeheader()
                    writer.writerows(rows)
                self._log('已导出：'+path)
            except OSError as exc:
                messagebox.showerror('导出失败',str(exc))

    def _export_log(self):
        path = filedialog.asksaveasfilename(title='保存设备日志',defaultextension='.txt',filetypes=[('文本','*.txt')])
        if path:
            try:
                Path(path).write_text('\n'.join(self.log_lines)+'\n',encoding='utf-8-sig')
                self._log('日志已保存：'+path)
            except OSError as exc:
                messagebox.showerror('保存失败',str(exc))

    def _close(self):
        self.root.after_cancel(self.timer)
        self._disconnect()
        self.root.destroy()


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == '__main__':
    main()
