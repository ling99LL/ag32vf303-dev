"""Hidden-Tk end-to-end check for the FOC2205 haptic panel."""
from pathlib import Path
import sys
import time
import tkinter as tk

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))

from foc_panel import App


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
        if len(app.haptic_mode_buttons) != 5:
            raise RuntimeError('m0-m4 buttons missing')
        if len(app.haptic_scales) != 14:
            raise RuntimeError('haptic parameter sliders missing')
        if abs(app.haptic_scales['kd'][0].get() - 0.45) > 1e-6:
            raise RuntimeError('m4 damping default is not 0.45')

        for mode in (0, 1, 2):
            app.haptic_mode_buttons[mode].invoke()
            if not wait_for(
                root,
                lambda mode=mode: app.model.haptic_active(time.monotonic()) and
                app.model.status is not None and
                app.model.status.values.get('hm') == mode,
                2.5,
            ):
                raise RuntimeError(f'm{mode} did not become active in GUI')
        print('GUI_HAPTIC_SMOKE_OK modes=0/1/2 params=14 kd=0.45 fw=%s' %
              app.model.status['fw'])
    finally:
        app._disconnect()
        root.destroy()


if __name__ == '__main__':
    main()
