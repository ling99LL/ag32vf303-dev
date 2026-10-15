#!/bin/bash
# 守护：等 DAPLink 回来 + 等板子上电窗口，两者都满足就自动烧录。
#   - 每轮先 pnputil enable DAPLink（Windows 会残留 Disabled 状态）
#   - 再跑 flash_grab.bat（openocd: init -> halt -> program -> reset halt）
#   - 成功即退出
ID='USB\VID_CAFE&PID_1001\3135504115343838517B93107883024C'
cd "$(dirname "$0")"
n=0
while true; do
  n=$((n+1))
  MSYS_NO_PATHCONV=1 pnputil /enable-device "$ID" > /dev/null 2>&1
  out=$(cmd //c flash_grab.bat 2>&1)
  echo "$out" >> /tmp/watch.log
  if echo "$out" | grep -qiE "Verified OK|verified.*ok|\*\* Verified"; then
    echo "SUCCESS on try $n"
    echo "$out" | tail -14
    exit 0
  fi
  if [ $((n % 60)) -eq 0 ]; then echo "... $n tries elapsed"; fi
done
