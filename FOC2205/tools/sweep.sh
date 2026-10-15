#!/bin/bash
OC="C://Users//Administrator//.platformio//packages//tool-agrv_openocd//bin//openocd_cmd.bat"
ETC="C://Users//Administrator//.platformio//platforms//AgRV//etc"
run() {
  local name="$1"; shift
  out=$(cmd //c "$@" 2>&1)
  if echo "$out" | grep -qiE "cannot read IDR|JUNK"; then
    echo "[$name] FAIL (no IDR)"
  elif echo "$out" | grep -qiE "halted|target state|Info : .*Tap|IDCODE"; then
    echo "[$name] *** OK ***"
    echo "$out" | grep -iE "halted|IDCODE|target state|Tap" | head -5
  else
    echo "[$name] ???"
    echo "$out" | tail -4
  fi
}
mk() {
  cat > /tmp/sw_$1.bat << EOB
@echo off
"$OC" -s "$ETC" $2 -f agrv2k.cfg $3 -c "shutdown"
EOB
  cp /tmp/sw_$1.bat ./sw_$1.bat
}
mk a "-c \"variable ADAPTER_SPEED 100\" -c \"variable ADAPTER cmsis-dap\"" "-c \"init\""
mk b "-c \"variable ADAPTER_SPEED 100\" -c \"variable ADAPTER cmsis-dap\"" "-c \"reset_config trst_only\" -c \"adapter deassert trst\" -c \"init\""
mk c "-c \"variable ADAPTER_SPEED 1000\" -c \"variable ADAPTER cmsis-dap\"" "-c \"transport select jtag\" -c \"init\""
mk d "-c \"variable ADAPTER_SPEED 1000\" -c \"variable ADAPTER cmsis-dap\"" "-c \"swj_pins trst 1\" -c \"init\""
for n in a b c d; do run "$n" sw_$n.bat; done
