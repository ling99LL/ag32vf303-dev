#!/bin/bash
# 无限循环等待板子上电窗口（配合 flash_grab.bat 使用）
cd "$(dirname "$0")"
n=0
while true; do
  n=$((n+1))
  out=$(cmd //c flash_grab.bat 2>&1)
  echo "$out" >> /tmp/grab_full.log
  if echo "$out" | grep -qiE "Verified OK|verified.*ok|\*\* Verified"; then
    echo "SUCCESS on try $n"
    echo "$out" | tail -14
    exit 0
  fi
  if [ $((n % 100)) -eq 0 ]; then echo "... $n tries, still waiting for power-up"; fi
done
