"""Hidden-Tk end-to-end check for the FOC2205 closed-loop SPIN panel."""
from pathlib import Path
import sys
import time
import tkinter as tk

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))

from foc_panel import App


def pump(root, seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        root.update()
        time.sleep(0.02)


def wait_for(root, predicate, timeout):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        root.update()
        if predicate():
            return True
        time.sleep(0.02)
    return False


def main():
    root = tk.Tk()
    root.withdraw()
    app = App(root)
    app.port.set('COM26')
    app._connect()
    try:
        if not wait_for(root, lambda: app.model.fresh(time.monotonic()) and
                        app.model.can_drive(time.monotonic()), 6.0):
            raise RuntimeError('panel did not receive a ready status')

        app.spin_mode.set('closed')
        app.spin_speed.set('0.10 圈/秒 (6 rpm)')
        app.spin_power.set(20)
        app.spin_dir.set(1)
        app._toggle_spin()

        if not wait_for(root, lambda: app.model.spin_active(time.monotonic()), 3.0):
            status = app.model.status.values if app.model.status else None
            raise RuntimeError(
                'GUI did not enter closed-loop SPIN; status=%s log=%s' %
                (status, list(app.log_lines)[-12:]))
        pump(root, 4.0)
        status = app.model.status
        if status is None or status['mode'] != 2 or status['open'] != 0:
            raise RuntimeError('GUI/status did not report closed SPIN')
        if status['st'] != 1 or status['out'] != 1 or status['fault']:
            raise RuntimeError('closed SPIN left the healthy running state')
        if not 19_000 <= status['hz'] <= 21_000:
            raise RuntimeError('ISR rate outside 19-21 kHz')
        vsp = status.values.get('vsp')
        vfb = status.values.get('vfb')
        if vsp is None or vfb is None:
            raise RuntimeError('velocity-loop status fields missing')
        target_rpm = vsp * 60.0 / 16384.0
        measured = []
        end = time.monotonic() + 3.0
        while time.monotonic() < end:
            root.update()
            if app.model.status is not None and 'vfb' in app.model.status.values:
                measured.append(app.model.status['vfb'] * 60.0 / 16384.0)
            time.sleep(0.1)
        measured_rpm = sum(measured) / len(measured) if measured else float('nan')
        if abs(target_rpm - 6.0) > 1.0 or abs(measured_rpm - target_rpm) > 1.0:
            raise RuntimeError(
                f'velocity tracking failed: target={target_rpm:.2f} '
                f'measured_mean={measured_rpm:.2f} rpm samples={measured[-8:]}')

        app._toggle_spin()
        if not wait_for(root, lambda: app.model.status is not None and
                        app.model.status['st'] in (0, 4) and
                        app.model.status['out'] == 0, 5.0):
            raise RuntimeError('GUI stop did not release the power stage')
        print('GUI_SPIN_SMOKE_OK target=%.2f measured=%.2f rpm hz=%s' %
              (target_rpm, measured_rpm, status['hz']))
    finally:
        app._disconnect()
        root.destroy()


if __name__ == '__main__':
    main()
