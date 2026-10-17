"""FOC2205 additive protocol-v2 diagnostics and panel state (no Tk/serial I/O)."""
from dataclasses import dataclass

STALE_SECONDS = 2.0
STATE_NAMES = {0: '空闲', 1: '运行', 2: '保留', 3: '故障锁存', 4: '动作完成'}
FAULT_NAMES = {
    'driver unavailable/config': '驱动无响应或配置不符，请检查 VM 供电与 SPI',
    'driver status': '驱动状态异常，请检查供电与故障寄存器',
    'driver config': '驱动配置读回不符',
    'driver break': 'nFAULT 硬件刹车已锁存',
    'encoder CRC': '编码器 CRC 连续失败',
    'ADC timeout': 'ADC 采样超时',
    'startup encoder CRC': '启动编码器自检失败',
    'startup ADC calibration': '电流零点标定失败',
    'startup alignment': '转子对齐失败',
}


@dataclass(frozen=True)
class Status:
    values: dict

    @classmethod
    def parse(cls, line):
        if not line.startswith('#FOC,'):
            return None
        values = dict(part.split('=', 1) for part in line[5:].split(',') if '=' in part)
        # A truncated line must never manufacture valid zero-valued measurements.
        fields = ('proto diag up hz stage calst calpk calok ready aligned drvok encok mg adcok cal '
                  'adce brk out ang crc ia ib ic mode mask pct drv vq iacc err vel st').split()
        try:
            for key in fields:
                values[key] = int(values[key], 16 if key == 'drv' else 10)
            if values['proto'] != 2 or values['diag'] != 1:
                return None
            if (not 0 <= values['ang'] < 16384 or values['st'] not in STATE_NAMES or
                    not 0 <= values['calst'] <= 9 or values['calpk'] < 0 or
                    values['calok'] not in (0, 1)):
                return None
            for key in 'ready aligned drvok encok adcok cal brk out'.split():
                if values[key] not in (0, 1):
                    return None
            if values['mode'] not in (0, 1, 2):
                return None
            pct_max = 80 if values['mode'] == 2 else 20
            if not 0 <= values['mask'] <= 7 or not 0 <= values['pct'] <= pct_max:
                return None
            if not values.get('fw') or 'fault' not in values:
                return None
        except (ValueError, KeyError):
            return None
        return cls(values)

    def __getitem__(self, key):
        return self.values[key]

    @property
    def fault_text(self):
        reason = self.values['fault']
        return FAULT_NAMES.get(reason, reason or '无')

    @property
    def drive_ready(self):
        v = self.values
        return (all(v[k] for k in ('ready', 'aligned', 'drvok', 'encok', 'adcok', 'cal'))
                and not v['brk'] and v['st'] in (0, 4))


class PanelState:
    def __init__(self):
        self.status = None
        self.received_at = None
        self.last_angle = None
        self.turns = 0.0
        self.reboots = 0

    def fresh(self, now):
        return self.received_at is not None and now - self.received_at <= STALE_SECONDS

    def accept(self, status, now):
        reboot = (self.status is not None and
                  status['up'] < self.status['up'] and
                  self.status['up'] - status['up'] < 0x80000000)
        if reboot:
            self.reboots += 1
            self.turns = 0.0
        if reboot or not self.fresh(now) or not status['encok']:
            self.last_angle = None
        if status['encok']:
            if self.last_angle is not None:
                delta = (status['ang'] - self.last_angle + 8192) % 16384 - 8192
                self.turns += delta / 16384.0
            self.last_angle = status['ang']
        self.status = status
        self.received_at = now
        return reboot

    def can_drive(self, now):
        return self.fresh(now) and self.status.drive_ready

    def can_calibrate(self, now):
        v = self.status
        return (self.fresh(now) and v is not None and v['calok'] == 1 and
                all(v[k] for k in ('drvok', 'encok', 'adcok', 'cal')) and
                not v['brk'] and
                v['calst'] not in (1, 2, 3, 4, 5, 6) and
                v['st'] == 0 and not v['out'])

    def calibration_active(self, now):
        return (self.fresh(now) and self.status is not None and
                1 <= self.status['calst'] <= 6)

    def can_manual(self, now):
        return (self.fresh(now) and self.status['mode'] == 1 and
                self.status['st'] == 1 and self.status['ready'] == 1)

    def spin_active(self, now):
        return (self.fresh(now) and self.status is not None and
                self.status['mode'] == 2 and self.status['st'] == 1 and
                self.status['ready'] == 1)

    def can_spin_control(self, now):
        return self.spin_active(now) or self.can_drive(now)

    def can_recover(self, now):
        return (self.fresh(now) and self.status['st'] == 3 and
                all(self.status[k] for k in ('aligned', 'drvok', 'encok', 'adcok', 'cal')))
