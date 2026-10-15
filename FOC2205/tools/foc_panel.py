"""FOC2205 上位机 —— 角度显示 + 三相手动强制（硬件调试用）。

功能
  1. 实时显示 MT6701 角度（表盘指针 + 度数 + raw + 累积圈数）
  2. 手动把 A/B/C 三相各自强制成"高(VM)"或"低(GND)"，用于排查哪相通、
     相电流有没有、转子会不会被吸住
  3. 顺带显示三相电流 LSB、CRC 误码、DRV8316 故障字节、力矩指令

协议（固件侧 main.c 实现，115200 8N1）
  '?'    -> 一行 "#FOC,ang=...,deg=...,crc=...,ia=...,mode=...,mask=...,..."
  'm'        进入手动强制模式
  'xN'       N=0..7，bit0=A bit1=B bit2=C，1=高
  'wN'       N=1..4 -> 驱动强度 25/50/75/100 pct（压差 = VM * pct/100）
  'g'        退出手动，输出交还 FOC
  'r'/'R'    位置伺服 ±1 圈    's' 释放    'f' 读故障

安全
  * 手动模式 = 直流通电，电流可能很大（仅受电机电阻限制）。
    先用低强度（25/50），不要长时间挂着。
  * 固件侧 30 秒无操作会自动释放；本界面每 5 秒自动重发一次 mask 保活。

运行：python tools/foc_panel.py        （需要 pyserial + tkinter）
"""
import sys, time, threading, queue
import tkinter as tk
from tkinter import ttk, messagebox
import serial, serial.tools.list_ports

RAW_PER_TURN = 16384.0
POLL_MS = 100          # 状态帧轮询间隔
KEEPALIVE_MS = 5000    # 手动模式保活


def list_ports():
    try:
        return [p.device for p in serial.tools.list_ports.comports()]
    except Exception:
        return []


class App:
    def __init__(self, root):
        self.root = root
        root.title('FOC2205 上位机 — 角度 / 三相手动强制')
        root.geometry('900x640')

        self.ser = None
        self.rxq = queue.Queue()
        self.stop_evt = threading.Event()
        self.mask = [0, 0, 0]          # A B C，1=高
        self.pct = 50
        self.manual = False
        self.last_ang = None
        self.turns = 0                 # 累积圈数（上位机侧估算）
        self.last_keepalive = 0.0

        self._build_ui()
        self.root.after(POLL_MS, self._tick)

    # ---------------- UI ----------------
    def _build_ui(self):
        top = ttk.Frame(self.root, padding=6)
        top.pack(fill='x')

        ttk.Label(top, text='串口').pack(side='left')
        self.port = ttk.Combobox(top, width=12, values=list_ports())
        self.port.pack(side='left', padx=3)
        if list_ports():
            self.port.set(list_ports()[0])
        else:
            self.port.set('COM26')
        ttk.Button(top, text='刷新', command=self._refresh_ports).pack(side='left')
        ttk.Label(top, text='波特率').pack(side='left', padx=(8, 0))
        self.baud = ttk.Combobox(top, width=8, values=['115200', '9600', '230400'])
        self.baud.set('115200')
        self.baud.pack(side='left', padx=3)
        self.btn_conn = ttk.Button(top, text='连接', command=self._toggle_conn)
        self.btn_conn.pack(side='left', padx=6)
        self.lbl_conn = ttk.Label(top, text='未连接', foreground='#a33')
        self.lbl_conn.pack(side='left')

        body = ttk.Frame(self.root, padding=6)
        body.pack(fill='both', expand=True)

        # --- 左：角度 ---
        left = ttk.LabelFrame(body, text='角度（MT6701）', padding=8)
        left.pack(side='left', fill='y', padx=(0, 8))
        self.canvas = tk.Canvas(left, width=260, height=260, bg='#111318',
                                highlightthickness=0)
        self.canvas.pack()
        self._draw_dial_base()
        self.needle = self.canvas.create_line(0, 0, 0, 0, fill='#e5484d', width=3)
        self.var_deg = tk.StringVar(value='--.-  deg')
        ttk.Label(left, textvariable=self.var_deg,
                  font=('Consolas', 26, 'bold')).pack(pady=(6, 0))
        self.var_raw = tk.StringVar(value='raw: ----')
        ttk.Label(left, textvariable=self.var_raw, font=('Consolas', 11)).pack()
        self.var_turns = tk.StringVar(value='累积: 0.00 圈')
        ttk.Label(left, textvariable=self.var_turns, font=('Consolas', 11)).pack()

        # --- 右：三相控制 + 状态 ---
        right = ttk.Frame(body)
        right.pack(side='left', fill='both', expand=True)

        ph = ttk.LabelFrame(right, text='三相手动强制（调试）', padding=8)
        ph.pack(fill='x')
        warn = ('手动强制 = 直流通电，电流仅受电机电阻限制。\n'
                '请先用低强度短时测试；固件 30 秒无操作自动释放。')
        ttk.Label(ph, text=warn, foreground='#c2410c',
                  font=('Microsoft YaHei', 9)).pack(anchor='w', pady=(0, 6))

        row = ttk.Frame(ph)
        row.pack()
        self.phase_btns = []
        for i, name in enumerate(('A 相', 'B 相', 'C 相')):
            b = tk.Button(row, text=name + '\n低', width=8, height=2,
                          bg='#3b4252', fg='white', font=('Microsoft YaHei', 11),
                          command=lambda i=i: self._toggle_phase(i))
            b.pack(side='left', padx=6)
            self.phase_btns.append(b)

        ctl = ttk.Frame(ph)
        ctl.pack(fill='x', pady=(8, 0))
        ttk.Label(ctl, text='驱动强度').pack(side='left')
        self.var_pct = tk.IntVar(value=50)
        for v in (25, 50, 75, 100):
            ttk.Radiobutton(ctl, text=f'{v}%', value=v, variable=self.var_pct,
                            command=self._send_pct).pack(side='left', padx=4)
        self.btn_manual = tk.Button(ctl, text='进入手动强制', bg='#1f6feb',
                                    fg='white', command=self._toggle_manual)
        self.btn_manual.pack(side='left', padx=12)

        st = ttk.LabelFrame(right, text='状态', padding=8)
        st.pack(fill='x', pady=(8, 0))
        self.var_stat = tk.StringVar(value='ia=-- ib=-- ic=--')
        ttk.Label(st, textvariable=self.var_stat,
                  font=('Consolas', 12)).pack(anchor='w')
        self.var_drv = tk.StringVar(value='IC_STAT=--  CRC=--  mode=--')
        ttk.Label(st, textvariable=self.var_drv,
                  font=('Consolas', 11)).pack(anchor='w')
        self.var_ctl = tk.StringVar(value='vq=--  i=--  err=--')
        ttk.Label(st, textvariable=self.var_ctl,
                  font=('Consolas', 11)).pack(anchor='w')

        act = ttk.Frame(right)
        act.pack(fill='x', pady=(8, 0))
        ttk.Button(act, text='转 +1 圈 (r)', command=lambda: self._send('r')).pack(side='left')
        ttk.Button(act, text='转 -1 圈 (R)', command=lambda: self._send('R')).pack(side='left', padx=4)
        ttk.Button(act, text='释放 (s)', command=lambda: self._send('s')).pack(side='left')
        ttk.Button(act, text='读故障 (f)', command=lambda: self._send('f')).pack(side='left', padx=4)

        log = ttk.LabelFrame(self.root, text='日志', padding=6)
        log.pack(fill='both', expand=True, padx=6, pady=(0, 6))
        self.txt = tk.Text(log, height=10, font=('Consolas', 9))
        self.txt.pack(fill='both', expand=True)

    def _draw_dial_base(self):
        c = self.canvas
        cx = cy = 130
        r = 112
        c.create_oval(cx - r, cy - r, cx + r, cy + r, outline='#3b4252', width=2)
        for i in range(12):
            import math
            a = math.radians(i * 30 - 90)
            x1, y1 = cx + (r - 12) * math.cos(a), cy + (r - 12) * math.sin(a)
            x2, y2 = cx + r * math.cos(a), cy + r * math.sin(a)
            c.create_line(x1, y1, x2, y2, fill='#5b6478', width=2)
        c.create_text(cx, cy - r + 16, text='0', fill='#8b93a7', font=('Consolas', 9))
        c.create_text(cx + r - 16, cy, text='90', fill='#8b93a7', font=('Consolas', 9))
        c.create_text(cx, cy + r - 16, text='180', fill='#8b93a7', font=('Consolas', 9))
        c.create_text(cx - r + 18, cy, text='270', fill='#8b93a7', font=('Consolas', 9))
        self.cx, self.cy, self.cr = cx, cy, r

    # ---------------- 串口 ----------------
    def _refresh_ports(self):
        self.port['values'] = list_ports()

    def _toggle_conn(self):
        if self.ser:
            self._disconnect()
        else:
            self._connect()

    def _connect(self):
        try:
            self.ser = serial.Serial(self.port.get(), int(self.baud.get()), timeout=0.2)
        except Exception as e:
            messagebox.showerror('串口', f'打开失败：{e}')
            self.ser = None
            return
        self.stop_evt.clear()
        threading.Thread(target=self._reader, daemon=True).start()
        self.btn_conn.config(text='断开')
        self.lbl_conn.config(text='已连接 ' + self.port.get(), foreground='#2a7')
        self._log('connected: ' + self.port.get())

    def _disconnect(self):
        self.stop_evt.set()
        try:
            if self.manual:
                self._send('g')          # 断开前务必释放输出
        except Exception:
            pass
        time.sleep(0.1)
        try:
            self.ser.close()
        except Exception:
            pass
        self.ser = None
        self.btn_conn.config(text='连接')
        self.lbl_conn.config(text='未连接', foreground='#a33')
        self.manual = False
        self.btn_manual.config(text='进入手动强制', bg='#1f6feb')

    def _reader(self):
        buf = b''
        while not self.stop_evt.is_set():
            try:
                d = self.ser.read(512)
            except Exception:
                break
            if not d:
                continue
            buf += d
            while b'\n' in buf:
                line, buf = buf.split(b'\n', 1)
                self.rxq.put(line.decode('utf-8', 'replace').strip())

    def _send(self, s):
        if not self.ser:
            self._log('未连接，无法发送 ' + s)
            return
        try:
            self.ser.write(s.encode())
        except Exception as e:
            self._log('send error: %s' % e)

    def _log(self, s):
        self.txt.insert('end', time.strftime('%H:%M:%S ') + s + '\n')
        self.txt.see('end')

    # ---------------- 交互 ----------------
    def _toggle_manual(self):
        if not self.ser:
            self._log('请先连接串口')
            return
        if self.manual:
            self._send('g')
            self.manual = False
            self.btn_manual.config(text='进入手动强制', bg='#1f6feb')
            self._log('manual OFF')
        else:
            self._send('m')
            self.manual = True
            self.btn_manual.config(text='退出手动（交还 FOC）', bg='#c2410c')
            self._send_mask()
            self._log('manual ON — 注意：直流通电，电流可能很大')

    def _toggle_phase(self, i):
        self.mask[i] = 1 - self.mask[i]
        self.phase_btns[i].config(
            text=('A 相' if i == 0 else 'B 相' if i == 1 else 'C 相') +
                 ('\n高' if self.mask[i] else '\n低'),
            bg='#e5484d' if self.mask[i] else '#3b4252')
        if self.manual:
            self._send_mask()
        else:
            self._log('提示：需要先点“进入手动强制”才会生效')

    def _mask_value(self):
        return self.mask[0] | (self.mask[1] << 1) | (self.mask[2] << 2)

    def _send_mask(self):
        self._send('x%d' % self._mask_value())
        self.last_keepalive = time.time()

    def _send_pct(self):
        self.pct = self.var_pct.get()
        if self.manual:
            self._send('w%d' % (self.pct // 25))
            self.last_keepalive = time.time()

    # ---------------- 周期任务 ----------------
    def _tick(self):
        # 收日志
        while True:
            try:
                line = self.rxq.get_nowait()
            except queue.Empty:
                break
            if line.startswith('#FOC,'):
                self._update(line)
            elif line:
                self._log(line)

        if self.ser:
            self._send('?')
            if self.manual and (time.time() - self.last_keepalive) * 1000 > KEEPALIVE_MS:
                self._send_mask()          # 保活，避免固件 30 秒超时释放

        self.root.after(POLL_MS, self._tick)

    def _update(self, line):
        kv = {}
        for part in line[len('#FOC,'):].split(','):
            if '=' in part:
                k, v = part.split('=', 1)
                kv[k] = v
        try:
            ang = int(kv.get('ang', '0'))
            deg = float(kv.get('deg', '0'))
            ia = int(kv.get('ia', '0'))
            ib = int(kv.get('ib', '0'))
            ic = int(kv.get('ic', '0'))
            mode = int(kv.get('mode', '0'))
            crc = kv.get('crc', '--')
            drv = kv.get('drv', '--')
            vq = kv.get('vq', '--')
            iacc = kv.get('iacc', '--')
            err = kv.get('err', '--')
            mask = int(kv.get('mask', '0'))
            pct = kv.get('pct', '--')
        except ValueError:
            return

        # 累积圈数（跨圈估算）
        if self.last_ang is not None:
            d = ang - self.last_ang
            if d > 8192:
                d -= 16384
            elif d < -8192:
                d += 16384
            self.turns += d / RAW_PER_TURN
        self.last_ang = ang

        self.var_deg.set('%.1f  deg' % deg)
        self.var_raw.set('raw: %d' % ang)
        self.var_turns.set('累积: %+.2f 圈' % self.turns)

        # 指针
        import math
        a = math.radians(deg - 90)
        r = self.cr - 20
        self.canvas.coords(self.needle, self.cx, self.cy,
                           self.cx + r * math.cos(a), self.cy + r * math.sin(a))

        self.var_stat.set('ia=%4d  ib=%4d  ic=%4d   (ADC LSB, 零点≈2064)' % (ia, ib, ic))
        mtxt = '手动强制' if mode else 'FOC'
        if mode:
            mtxt += ' mask=%d(A%d B%d C%d) 强度=%s%%' % (
                mask, mask & 1, (mask >> 1) & 1, (mask >> 2) & 1, pct)
        self.var_drv.set('IC_STAT=%s  CRC=%s  模式=%s' % (drv, crc, mtxt))
        self.var_ctl.set('力矩 vq=%s  积分 i=%s  位置误差 err=%s raw' % (vq, iacc, err))

        # 固件侧自动释放了手动模式时，同步按钮状态
        if self.manual and not mode:
            self.manual = False
            self.btn_manual.config(text='进入手动强制', bg='#1f6feb')
            self._log('manual auto-released by firmware')


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == '__main__':
    main()
