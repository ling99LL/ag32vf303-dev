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
        if (app.spin_speed_scale.cget('from') != 3 or
                app.spin_speed_scale.cget('to') != 60):
            raise RuntimeError('speed slider range is not 3-60 rpm')
        if not app.btn_stop.cget('text').startswith('紧急停止'):
            raise RuntimeError('emergency-stop button is not wired')
        if any(name not in app.current_vars for name in 'ABC'):
            raise RuntimeError('phase-current labels are missing')

        app.spin_mode.set('closed')
        app.spin_speed_rpm.set(6)
        app._spin_speed_changed()
        app.spin_power.set(20)
        app.spin_dir.set(1)
        app.btn_spin.invoke()

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
        app.spin_speed_scale.set(12)
        app._spin_speed_changed()
        app._apply_spin_speed()
        if not wait_for(root, lambda: app.model.status is not None and
                        'vsp' in app.model.status.values and
                        abs(app.model.status['vsp'] * 60.0 / 16384.0 - 12.0) < 0.8, 2.0):
            raise RuntimeError('speed slider did not retarget the running SPIN')
        pump(root, 2.5)
        measured_high = []
        end = time.monotonic() + 2.5
        while time.monotonic() < end:
            root.update()
            if app.model.status is not None and 'vfb' in app.model.status.values:
                measured_high.append(app.model.status['vfb'] * 60.0 / 16384.0)
            time.sleep(0.1)
        measured_high_rpm = (sum(measured_high) / len(measured_high)
                             if measured_high else float('nan'))
        if abs(measured_high_rpm - 12.0) > 1.3:
            raise RuntimeError(
                f'speed slider tracking failed: measured_mean={measured_high_rpm:.2f} rpm '
                f'samples={measured_high[-8:]}')
        if not wait_for(root, lambda: app.haptic_latest is not None and
                        'ia' in app.haptic_latest.values, 2.0):
            raise RuntimeError('high-rate telemetry did not include phase currents')
        if any(app.current_vars[name].get() == '---' for name in 'ABC'):
            raise RuntimeError('phase-current display did not update')

        estop_sent = time.monotonic()
        app.btn_stop.invoke()
        if not wait_for(root, lambda: app.model.status is not None and
                        app.model.status['st'] in (0, 4) and
                        app.model.status['out'] == 0, 2.5):
            raise RuntimeError('GUI emergency stop did not release the power stage')
        estop_seconds = time.monotonic() - estop_sent
        print('GUI_SPIN_SMOKE_OK targets=%.2f/12.00 measured=%.2f/%.2f rpm hz=%s '
              'currents=%s/%s/%s estop_release=%.2fs' %
              (target_rpm, measured_rpm, measured_high_rpm, status['hz'],
               app.current_vars['A'].get(), app.current_vars['B'].get(),
               app.current_vars['C'].get(), estop_seconds))
    finally:
        app._disconnect()
        root.destroy()


if __name__ == '__main__':
    main()
