#!/bin/bash
# 只重试烧录，不再动 pnputil（避免把 DAP 弄成 Disabled）
cd "$(dirname "$0")"
n=0
while [ $n -lt 1500 ]; do
  n=$((n+1))
  out=$(cmd //c flash_grab.bat 2>&1)
  echo "$out" >> /tmp/watch2.log
  if echo "$out" | grep -qiE "Verified OK|verified.*ok|\*\* Verified"; then
    echo "SUCCESS on try $n"
    echo "$out" | tail -14
    exit 0
  fi
  if [ $((n % 50)) -eq 0 ]; then echo "... $n tries"; fi
done
echo "FAILED after $n tries"
