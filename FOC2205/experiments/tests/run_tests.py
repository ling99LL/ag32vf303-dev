"""Compile production control sources against deterministic hardware stubs."""
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
GCC = shutil.which('gcc') or r'C:\MinGW\bin\gcc.exe'
BUILD = HERE / 'build'
BUILD.mkdir(exist_ok=True)
sources = ['motion.c', 'foc.c', 'mt6701.c', 'console.c', 'control.c', 'calibration.c']
subprocess.run([GCC, '-std=c99', '-O2', '-Wall', '-Wextra', '-Werror',
                '-DFOC_HOST_TEST', '-DFOC_CPLD_BRINGUP=1',
                '-include', str(HERE/'stubs/test_platform.h'),
                '-I'+str(HERE/'stubs'), '-I'+str(ROOT/'src'),
                *[str(ROOT/'src'/s) for s in sources],
                str(HERE/'control_regression.c'), '-lm', '-o', str(BUILD/'control.exe')], check=True)
subprocess.run([str(BUILD/'control.exe')], check=True)
subprocess.run([sys.executable, str(HERE/'test_panel_protocol.py')], check=True)
for p in (ROOT/'tools').glob('*.py'):
    compile(p.read_text(encoding='utf-8-sig'), str(p), 'exec')
print('PASS active Python tools syntax')
