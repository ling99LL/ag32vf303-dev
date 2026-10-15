#!/bin/bash
# 一键：烧录 20% 版固件 -> 复位运行 -> 自动跑一次闭环转圈 -> 打印平顺度指标
#
# 用法（DAPLink 已插好、板子已上电后）：
#   bash tools/go20.sh [圈速度档位]
#
# 判定标准：jitter 行里的 |vm| mean 应该接近 rev_per_s * 16384
#   （0.05 rev/s -> 理想 819；10% 出力时实测基线 852）
set -u
cd "$(dirname "$0")/.."

ELF_WIN='C:\Users\Administrator\Documents\AG32\FOC2205\.pio\build\foc2205\foc2205.elf'
PY="C:/Users/Administrator/AppData/Local/Programs/Python/Python311/python.exe"
PORT="${2:-COM26}"

echo "=== [1/3] 烧录 ==="
"C:/Users/Administrator/.platformio/penv/Scripts/pio.exe" run -e foc2205 -t upload 2>&1 \
  | grep -iE "SUCCESS|error|verified|IDR|Wrote" | head -6

echo "=== [2/3] 复位运行 ==="
(cd tools && cmd //c reset_run.bat > /dev/null 2>&1)
sleep 3

echo "=== [3/3] 闭环转一圈 ==="
"$PY" tools/uart_console.py r "${1:-45}" "$PORT" > log_go20.txt 2>&1
grep -E "MOVE DONE|jitter|move start|fault|stall" log_go20.txt
echo "--- 末 6 行 ---"
tail -6 log_go20.txt
