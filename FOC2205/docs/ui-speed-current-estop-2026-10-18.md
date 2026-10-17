# FOC2205 `.25` UI / speed / current / emergency-stop acceptance

Date: 2026-10-18

## Scope

This record covers the GUI and host-facing changes after `fw=20261017.24`.
The motor-control algorithm stayed on the validated velocity-PI plus
synchronous feed-forward path.

## Implemented

- SPIN speed slider: 3–60 rpm, 1 rpm steps, with 3/6/15/60 rpm shortcuts.
- Firmware command: `rpm <3-60>`; legacy `V1..V4` still accepted.
- Compact telemetry `$T` 17-field form:
  `...,raw,ia,ib,ic,adcok`.
- Encoder-card A/B/C current display, gated by `adcok`.
- Full-width emergency-stop button and `Esc` -> `estop`.
- Status tab wrapped in a scrollable canvas to prevent clipped controls.
- `estop` is immediate; `s` remains the bounded SPIN stop.

## Automated results

```text
ALL CONTROL REGRESSIONS PASSED
Ran 9 tests in 0.001s
GUI_SPIN_SMOKE_OK targets=6.00/12.00 measured=6.57/11.37 rpm hz=20005
currents=+0/+5/+1 estop_release=0.80s
```

Additional checks:

- `foc2205` build: SUCCESS.
- `foc2205_bringup` build: SUCCESS.
- MCU upload: write and verify SUCCESS.
- Final COM26 status: `ready=1`, `st=0`, `out=0`, `crc=0`,
  `adcok=1`, `fault=''`.

One earlier repeat collected the 12 rpm window before the velocity step had
settled and measured a 13.32 rpm mean. The final smoke test waits 2.5 s after
the slider change, then measures a 2.5 s steady-state window; the 1.3 rpm
tolerance was not relaxed.

## Widget-level follow-up

The smoke test now exercises the actual Tk widgets rather than calling private
control methods directly:

- `btn_spin.invoke()` starts closed-loop SPIN;
- the 3-60 rpm slider is moved to 12 rpm and its release path is applied;
- `btn_stop.invoke()` sends the emergency-stop command.

Repeated COM26 runs on 2026-10-18 passed. The steady 6/12 rpm means were
5.73/11.80 rpm in the hidden-window run; visible-window feedback was
11.30-12.35 rpm at a 12.00 rpm target. A/B/C current labels showed live ADC
values while running, ISR stayed at 20,005 Hz, and emergency-stop release took
0.56-0.67 s in the visible runs (`0.70 s` in the hidden run). Final status was
`st=0, out=0, fault=''`.

Additional evidence:

- `experiments/logs/powered-20261018/gui-widget-controls-smoke.txt`
- `experiments/logs/powered-20261018/ui-test-running-12rpm-full.png`
- `experiments/logs/powered-20261018/ui-test-estop-confirmed-full.png`
- `experiments/logs/powered-20261018/ui-test-running-currents-full.png`

## Logs

- `experiments/logs/powered-20261018/run_tests.txt`
- `experiments/logs/powered-20261018/gui-spin-estop-currents.txt`
- `experiments/logs/powered-20261017/ui-speed-current-estop.png`
- `experiments/logs/powered-20261017/ui-spin-speed-controls.png`

## Not claimed

- Manual subjective feel of m1 damping, m2 inertia, m3 detents, or m4
  boundary resistance is not part of this automated run.
- Physical phase-current calibration, bus-voltage measurement, and
  oscilloscope waveform acceptance remain separate measurements.
