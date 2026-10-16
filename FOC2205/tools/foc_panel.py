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
from foc_protocol import PanelState, Status, STATE_NAMES

POLL_MS = 100
LOG_DIR = Path(__file__).resolve().parents[1] / 'experiments' / 'logs'


def list_ports():
    return sorted(p.device for p in serial.tools.list_ports.comports())


class App:
    def __init__(self, root):
        self.root = root
        root.title('FOC2205 调试台 — 设备诊断 / 角度 / 控制')
        root.geometry('1080x800')
        root.minsize(1020, 760)
        self.ser = None
        self.reader_thread = None
        self.stop_evt = threading.Event()
        self.rxq = queue.Queue()
        self.model = PanelState()
        self.history = deque(maxlen=5000)
        self.log_lines = deque(maxlen=2000)
        self.last_summary = None
        self.timeout_stopped = False
        self.command_pending_until = 0.0
        self.record_file = None
        self.record_writer = None
        self._build_ui()
        self._clear_values()
        self._enable_controls()
        root.protocol('WM_DELETE_WINDOW', self._close)
        root.bind('<Escape>', lambda event: self._send('s'))
        self.timer = root.after(POLL_MS, self._tick)

    def _build_ui(self):
        style = ttk.Style(self.root)
        style.theme_use('clam')
        style.configure('TLabel', font=('Microsoft YaHei UI', 10))
        style.configure('TLabelframe.Label', font=('Microsoft YaHei UI', 10, 'bold'))
        top = ttk.Frame(self.root, padding=10)
        top.pack(fill='x')
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
        self.btn_stop = tk.Button(top, text='释放输出  [Esc]', font=('Microsoft YaHei UI', 11, 'bold'),
                                  bg='#ba2836', fg='white', command=lambda: self._send('s'))
        self.btn_stop.pack(side='right')
        self.banner = tk.Label(self.root, text='连接设备后读取健康状态', anchor='w',
                               bg='#e8edf4', fg='#28374d', padx=14, pady=10,
                               font=('Microsoft YaHei UI', 12, 'bold'))
        self.banner.pack(fill='x', padx=10)
        body = ttk.Frame(self.root, padding=10)
        body.pack(fill='x')
        left = ttk.LabelFrame(body, text='MT6701 编码器', padding=10)
        left.pack(side='left', fill='y', padx=(0, 10))
        self.canvas = tk.Canvas(left, width=240, height=240, bg='#172337', highlightthickness=0)
        self.canvas.pack()
        cx = cy = 120
        for i in range(12):
            a = math.radians(i * 30 - 90)
            self.canvas.create_line(cx+93*math.cos(a), cy+93*math.sin(a),
                                    cx+106*math.cos(a), cy+106*math.sin(a), fill='#8092ac', width=2)
        for deg, x, y in [(0,120,33), (90,207,120), (180,120,207), (270,33,120)]:
            self.canvas.create_text(x, y, text=str(deg), fill='#c4d0e0')
        self.needle = self.canvas.create_line(120,120,120,38,fill='#44d7b6',width=4, state='hidden')
        self.angle_text = tk.StringVar(value='--.-°')
        ttk.Label(left, textvariable=self.angle_text, font=('Consolas', 28, 'bold')).pack(pady=6)
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
        for label, command in [('位置 +1 圈', 'r'), ('位置 -1 圈', 'R')]:
            btn = ttk.Button(row, text=label, command=lambda c=command: self._send(c))
            btn.pack(side='left', padx=(0,6))
            self.drive_buttons.append(btn)
        self.btn_recover = ttk.Button(row, text='检查并恢复', command=lambda: self._send('z'))
        self.btn_recover.pack(side='left')
        self.btn_cal = ttk.Button(row, text='开始慢速校准', command=lambda: self._send('a'))
        self.btn_cal.pack(side='left', padx=(8, 0))
        self.control_text = tk.StringVar(value='设备未就绪')
        ttk.Label(control, textvariable=self.control_text).pack(anchor='w', pady=(6,0))
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
        log = ttk.LabelFrame(self.root, text='设备日志', padding=8)
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
        self.last_summary = None
        self.timeout_stopped = False
        self.command_pending_until = 0
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
            self.record_path = LOG_DIR / f'panel-{datetime.now():%Y%m%d-%H%M%S-%f}.csv'
            self.record_file = self.record_path.open('w',encoding='utf-8-sig',newline='')
            self.record_writer = None
            self._log(f'采样自动记录：{self.record_path.name}')
        except OSError as exc:
            self._log(f'记录文件不可用：{exc}')
        self._send('s')
        self._send('?')
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
            port.write(b's')
            port.close()
        except (serial.SerialException, OSError):
            port.close()
        if self.reader_thread:
            self.reader_thread.join(timeout=0.4)
        if self.record_file:
            self.record_file.close()
            self.record_file = self.record_writer = None
        self.model = PanelState()
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
        if command == 'a':
            allowed = self.model.can_calibrate(now)
        elif command == 'A':
            allowed = self.model.calibration_active(now)
        elif command == 'z':
            allowed = self.model.can_recover(now)
        elif command.startswith(('x','w')):
            allowed = self.model.can_manual(now)
        elif command == 'g' or command in ('s','?','f','d','h'):
            allowed = True
        else:
            allowed = self.model.can_drive(now)
        if not allowed:
            self._log('设备未就绪，命令未发送：'+command)
            return False
        try:
            self.ser.write(command.encode('ascii'))
        except (serial.SerialException, OSError) as exc:
            self._log('串口写入失败：'+str(exc))
            self._disconnect()
            return False
        if command != '?':
            self._log('TX '+command)
        if command in ('a','A','m','r','R','z') or command.startswith(('x','w')):
            self.command_pending_until = now + 0.3
        return True

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

    def _enable_controls(self):
        now = time.monotonic()
        ready = self.ser is not None and self.model.can_drive(now)
        manual = self.ser is not None and self.model.can_manual(now)
        pending = now < self.command_pending_until
        for button in self.drive_buttons:
            button.configure(state='normal' if ready and not pending else 'disabled')
        self.btn_manual.configure(state='normal' if (ready or manual) and not pending else 'disabled',
                                  text='退出手动（释放）' if manual else '进入手动（中性）')
        for button in self.phase_buttons:
            button.configure(state='normal' if manual and not pending else 'disabled')
        for button in self.pct_buttons:
            button.configure(state='normal' if (ready or manual) and not pending else 'disabled')
        self.btn_recover.configure(state='normal' if self.ser and self.model.can_recover(now) and not pending else 'disabled')
        calibration_active = self.ser is not None and self.model.calibration_active(now)
        calibration_allowed = self.ser is not None and self.model.can_calibrate(now)
        self.btn_cal.configure(
            state='normal' if (calibration_active or calibration_allowed) and not pending else 'disabled',
            text='取消校准' if calibration_active else '开始慢速校准',
            command=(lambda: self._send('A')) if calibration_active else (lambda: self._send('a')))
        for button in self.read_buttons+[self.btn_stop]:
            button.configure(state='normal' if self.ser else 'disabled')

    def _clear_values(self):
        self.health_box.configure(text='健康状态与采样')
        self.angle_text.set('--.-°')
        self.encoder_text.set('等待有效采样')
        self.turns_text.set('相对累计  +0.000 圈')
        self.canvas.itemconfigure(self.needle, state='hidden')
        for var in self.health_vars.values():
            var.set('--')
        self.fault_text.set('故障原因：等待设备状态')
        self.control_text.set('设备未就绪')
        self.banner.configure(text='未连接',bg='#e8edf4',fg='#28374d')
        for i, button in enumerate(self.phase_buttons):
            button.configure(text=f"{'ABC'[i]} 关闭")

    def _update(self, status):
        self.health_box.configure(text='健康状态与采样')
        now = time.monotonic()
        if self.model.accept(status,now):
            self._log('检测到设备重启，累计角度已重置')
        self.timeout_stopped = False
        v = status.values
        deg = v['ang'] * 360.0/16384
        self.angle_text.set(f'{deg:.1f}°' if v['encok'] else '--.-°')
        self.encoder_text.set(f"raw {v['ang']} / CRC失败 {v['crc']}" if v['encok'] else f"采样无效 / CRC失败 {v['crc']}")
        self.turns_text.set(f'相对累计  {self.model.turns:+.3f} 圈')
        a = math.radians(deg-90)
        self.canvas.coords(self.needle,120,120,120+82*math.cos(a),120+82*math.sin(a))
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
            level = ('高' if v['mask']&(1<<i) else '低') if v['mode'] else '关闭'
            button.configure(text=f"{'ABC'[i]} {level}")
        if v['mode'] and v['pct'] in (5,10,15,20):
            self.pct.set(v['pct'])
        if v['st'] == 3:
            text, bg, fg = '故障锁存 · 功率输出已释放', '#fae4e6', '#972936'
            if not v['aligned']:
                text += ' · 排除故障后重新启动完成标定'
        elif v['st'] == 1:
            text, bg, fg = '手动调试运行中' if v['mode'] else '动作执行中', '#fff0cf', '#815000'
        elif status.drive_ready:
            text, bg, fg = '设备就绪 · 等待动作指令', '#dbf4e9', '#176249'
        else:
            text, bg, fg = '诊断可用 · 运动条件未满足', '#e8edf4', '#28374d'
        if v['out'] and v['st'] == 3:
            text = '故障状态仍有 PWM 使能，请立即检查硬件'
        self.banner.configure(text=text,bg=bg,fg=fg)
        self.lbl_conn.configure(text=f'{self.ser.port} 通信正常')
        summary = (v['st'],v['fault'],v['drvok'],v['encok'],v['cal'])
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
                self.record_file.flush()
            except (OSError,ValueError) as exc:
                self._log('采样记录停止：'+str(exc))
                self.record_file.close()
                self.record_file = self.record_writer = None

    def _tick(self):
        for _ in range(200):
            try:
                kind,line = self.rxq.get_nowait()
            except queue.Empty:
                break
            if kind == 'error':
                self._log('串口读取失败：'+line)
                self._disconnect()
                break
            if line.startswith('#FOC,'):
                status = Status.parse(line)
                if status and self.ser:
                    self._update(status)
                elif self.last_summary != 'invalid':
                    self._send('s')
                    self.model = PanelState()
                    self._clear_values()
                    self._log('状态帧缺失或协议不兼容，要求 proto=2 / diag=1；控制已禁用')
                    self.last_summary = 'invalid'
            elif line and not line.startswith('isr='):
                self._log(line)
        if self.ser:
            if not self.model.fresh(time.monotonic()):
                self.health_box.configure(text='健康状态与采样（等待更新 / 上次状态）')
                self.lbl_conn.configure(text=f'{self.ser.port} 等待状态 / 超时')
                self.banner.configure(text='等待有效诊断帧 / 通信超时 · 动作控制已禁用',bg='#fff0cf',fg='#815000')
                self.angle_text.set('--.-°')
                self.canvas.itemconfigure(self.needle,state='hidden')
                if self.model.status and not self.timeout_stopped:
                    self._send('s')
                    self.timeout_stopped = True
                    self._log('状态超过 2 秒未更新，已尝试释放输出')
            self._send('?')
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
