"""Hidden-Tk end-to-end check for the panel's +/- one-turn position buttons."""
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


def run_move(root, app, degrees):
    mark = len(app.log_lines)
    app._send('rot %d\n' % degrees)
    done = wait_for(
        root,
        lambda: any('MOVE DONE' in line for line in list(app.log_lines)[mark:]) and
        app.model.status is not None and app.model.status['st'] in (0, 4) and
        app.model.status['out'] == 0,
        30.0)
    if not done:
        raise RuntimeError('rot %+d did not complete cleanly' % degrees)
    if app.model.status['fault']:
        raise RuntimeError('rot %+d faulted: %s' %
                           (degrees, app.model.status['fault']))


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
        run_move(root, app, 360)
        run_move(root, app, -360)
        print('GUI_POSITION_SMOKE_OK rot=+360,-360 fw=%s' %
              app.model.status['fw'])
    finally:
        app._disconnect()
        root.destroy()


if __name__ == '__main__':
    main()
