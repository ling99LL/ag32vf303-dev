#!/usr/bin/env python
"""
绕过 openocd，直接对 CMSIS-DAP 发原始命令做底层诊断。

用途：区分"调试器坏了 / 线没接 / 目标不响应"这三种情况。

  python tools/dap_raw_probe.py

依次做四件事：
  1. DAP_Info        —— 调试器自身是否正常
  2. DAP_SWJ_Pins    —— 驱动 SWCLK/SWDIO 为 1 和 0 并读回，看输出级与连线
  3. JTAG->SWD 切换 + DAP_Transfer 读 DP IDR
  4. 打印 ACK 与 IDR 原始值，给出结论

依赖：pyusb + libusb-package（装在 .workbuddy 的隔离 venv 里）
"""
import os
import sys
import struct

import libusb_package
import usb.core
import usb.util
from usb.backend import libusb1

VID, PID = 0x0CAFE, 0x1001

# --- CMSIS-DAP 命令号 ---
DAP_INFO        = 0x00
DAP_CONNECT     = 0x02
DAP_SWJ_PINS    = 0x10
DAP_SWJ_CLOCK   = 0x11
DAP_SWD_CFG     = 0x13
DAP_TRANSFER    = 0x05
DAP_SWJ_SEQ     = 0x1D

# DAP_SWJ_Pins 位定义
PIN_SWCLK, PIN_SWDIO, PIN_TDI, PIN_TDO = 0x01, 0x02, 0x04, 0x08
PIN_nTRST, PIN_nRESET = 0x20, 0x80


def open_dap():
    dll = os.path.join(os.path.dirname(libusb_package.__file__), "libusb-1.0.dll")
    backend = libusb1.get_backend(find_library=lambda _: dll)
    dev = usb.core.find(idVendor=VID, idProduct=PID, backend=backend)
    if dev is None:
        raise SystemExit("找不到 CMSIS-DAP 设备 (0x%04x:0x%04x)" % (VID, PID))
    dev.set_configuration()
    cfg = dev.get_active_configuration()
    intf = cfg[(0, 0)]
    ep_out = usb.util.find_descriptor(
        intf, custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress)
        == usb.util.ENDPOINT_OUT)
    ep_in = usb.util.find_descriptor(
        intf, custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress)
        == usb.util.ENDPOINT_IN)
    return dev, intf, ep_out, ep_in


class Dap:
    def __init__(self):
        self.dev, self.intf, self.ep_out, self.ep_in = open_dap()
        self.pad = 64

    def cmd(self, payload, expect=None, timeout=2000):
        buf = bytearray([payload[0]]) + bytearray(payload[1:])
        buf += b"\x00" * (self.pad - len(buf))
        self.ep_out.write(bytes(buf), timeout)
        r = bytes(self.ep_in.read(self.pad, timeout))
        if expect is not None and r[0] != expect:
            raise RuntimeError("命令 0x%02X 应答异常: %s" % (payload[0], r[:8].hex()))
        return r

    def info(self, sub):
        r = self.cmd([DAP_INFO, sub])
        n = r[1]
        return r[2:2 + n].decode("ascii", "replace") if n else ""

    def connect_swd(self):
        r = self.cmd([DAP_CONNECT, 0x01])
        return r[1]

    def swj_clock(self, hz):
        self.cmd([DAP_SWJ_CLOCK] + list(struct.pack("<I", hz)))

    def swd_config(self):
        self.cmd([DAP_SWD_CFG, 0x00])

    def swj_seq(self, bits, data):
        assert len(data) == (bits + 7) // 8
        self.cmd([DAP_SWJ_SEQ, bits] + list(data))

    def pins(self, out, sel, wait_us=10):
        r = self.cmd([DAP_SWJ_PINS, out, sel] + list(struct.pack("<I", wait_us)))
        return r[1]

    def read_dp(self, reg):
        """reg: 0=IDR(IDCODE) 4=CTRL/STAT。返回 (ack, value)"""
        req = 0x02 | ((reg & 0x0C) << 1)   # APnDP=0, RnW=1, A3A2
        r = self.cmd([DAP_TRANSFER, 0x00, 0x01, req])
        ack = r[2] & 0x07
        val = struct.unpack("<I", r[3:7])[0] if len(r) >= 7 else None
        return ack, val


ACK_TXT = {1: "OK", 2: "WAIT", 4: "FAULT"}


def main():
    d = Dap()
    print("=== [1] 调试器自身 ===")
    try:
        print("  Vendor :", d.info(0x01))
        print("  FW ver :", d.info(0x04))
        print("  Serial :", d.info(0x06))
        caps = d.cmd([DAP_INFO, 0xF0])[2]
        print("  Caps   : 0x%02X (bit0=SWD bit1=JTAG)" % caps)
    except Exception as e:
        print("  读取失败:", e)
    print("  connect port:", d.connect_swd())

    print("\n=== [2] 驱动 SWCLK/SWDIO 并读回（判断输出级 + 连线）===")
    for name, pin in (("SWCLK", PIN_SWCLK), ("SWDIO", PIN_SWDIO)):
        hi = d.pins(pin, pin)
        lo = d.pins(0x00, pin)
        rel = d.pins(0x00, 0x00)          # 全部释放（输入），看外部电平
        print("  %s: 驱1读回=%d  驱0读回=%d  释放后=%d   -> %s"
              % (name, (hi >> {"SWCLK": 0, "SWDIO": 1}[name]) & 1,
                 (lo >> {"SWCLK": 0, "SWDIO": 1}[name]) & 1,
                 (rel >> {"SWCLK": 0, "SWDIO": 1}[name]) & 1,
                 "跟随(线正常)" if ((hi >> {"SWCLK": 0, "SWDIO": 1}[name]) & 1)
                 != ((lo >> {"SWCLK": 0, "SWDIO": 1}[name]) & 1) else "不跟随(!!)"))

    print("\n=== [3] JTAG->SWD 切换 + 读 DP IDR ===")
    d.swj_clock(100000)
    d.swd_config()
    # >=50 TCK/TMS=1，然后 16 位 0xE79E（LSB first -> 9E E7），再 >=50 TCK/TMS=1，再 8 位 0
    d.swj_seq(64, b"\xff" * 8)
    d.swj_seq(16, b"\x9e\xe7")
    d.swj_seq(64, b"\xff" * 8)
    d.swj_seq(8, b"\x00")
    for hz in (100000, 10000, 1000):
        d.swj_clock(hz)
        for attempt in range(3):
            try:
                ack, val = d.read_dp(0x00)
            except Exception as e:
                print("  %7d Hz  传输异常: %s" % (hz, e))
                break
            print("  %7d Hz  ACK=%d(%s)  IDR=0x%08X"
                  % (hz, ack, ACK_TXT.get(ack, "JUNK/无响应"),
                     val if val is not None else 0))
            if ack == 1:
                break

    print("\n=== 结论提示 ===")
    print("  ACK=1 且 IDR=0x?BC11477 之类 -> 目标正常，问题在 openocd 配置")
    print("  ACK 非 1、IDR=0xFFFFFFFF/0x00000000 -> 目标没回应：SWDIO/SWCLK 未接或目标 TAP 失能")


if __name__ == "__main__":
    main()
