# nFAULT / hardware-break verification (FOC2205)

Verifies that a **real** DRV8316C nFAULT assertion is caught by the GPTIMER0
break input, that the hardware drops MOE and latches `SR.BIF`, and that the
firmware then latches `MOTION_FAULT("driver break")` and can recover.

Everything is driven from the debug probe plus the console UART: **no firmware
change and no reflash**. `PIN_22` is not broken out on this board, so the fault
is produced by the DRV itself instead of by shorting the pin.

## How the fault is produced

`CTRL3 = 0x44` clears `SPI_FLT_REP`, which enables nFAULT reporting for SPI
faults (reset default is 0x46 = reporting disabled). One SPI frame with only 8
SCLK cycles then violates "a full 16 SCLK cycles must occur for transaction to
be valid" -> `STAT2.SPI_SCLK_FLT` + `IC_STAT.SPI_FLT/FAULT` -> the DRV pulls
nFAULT low. It is a real fault response of the driver, not an injected pin
level. `CTRL2.CLR_FLT` clears it again.

Note: an out-of-range register address (read or write of 0x3F) is **not**
flagged by this DRV8316C sample (`nfault_probe.tcl`), only the frame-length
error is.

## Scripts

| Script | Purpose |
|---|---|
| `nfault_sanity.bat` | Prove the debugger-side SPI0 frames match the firmware's reads (IC_STAT=0x08, CTRL2=0x7C, CTRL3=0x46). Run this first after any change. |
| `halt_check.bat` | Prove `halt` really freezes the core (PC frozen while GPTIMER0 CNT keeps counting). |
| `nfault_inject.bat` | Halt, arm MOE with INL low (no torque), switch on SPI-fault reporting, inject the 8-clock frame, and leave the target **halted** with the fault latched. |
| `nfault_resume.bat` | Resume the halted target. |
| `nfault_restore.bat` | Put CTRL3 back to 0x46 and clear the DRV fault. |
| `nfault_probe.bat` | Compare the candidate SPI fault conditions. |
| `nfault_cycle.py` | Full cycle: inject -> resume (listen on UART) -> `?` -> `f` -> `z` -> `?` -> restore. |

Run the `.bat` files from the FOC2205 project root (`experiments/tests/nfault/*.bat`
paths are relative to it).

## Reading the result

With the core halted, the injection must show

```
INJECTED GPIO4=0x1C nFAULT_pin=0 MOE=0 BIF=1 IC_STAT=0x29 STAT2=0x82
```

`GPIO4` bit1 = PIN_22 (1 -> 0 = the DRV really pulls the pin low), `MOE` 1 -> 0
and `BIF` 0 -> 1 are pure hardware, and a MOE retry while nFAULT is low reads
back `MOE=0`. After the resume the firmware prints
`MOVE ABORT: driver break` and reports `st=3 ... brk=1 drv=0x29 fault=driver break`.
`z` then reports `recovered: idle, outputs off` and the frame returns to
`st=0 out=0 brk=0 drv=0x08`.

Verified end-to-end run (2026-10-16, `fw=20261016.6`):
`experiments/logs/powered-20261016/225820-nfault-cycle.txt`.
