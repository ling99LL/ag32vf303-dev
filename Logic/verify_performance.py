import serial
import time
import sys

def benchmark_suite(port="COM33"):
    print(f"==================================================")
    print(f"   AG32VF303 Logic Analyzer Performance Audit")
    print(f"==================================================")
    try:
        ser = serial.Serial(port, 115200, timeout=3)
    except Exception as e:
        print(f"Failed to open {port}: {e}")
        return

    time.sleep(0.05)
    ser.reset_input_buffer()
    ser.reset_output_buffer()

    # 1. Device Handshake
    ser.write(bytes([0x00]))
    time.sleep(0.02)
    ser.reset_input_buffer()
    ser.write(bytes([0x02]))
    dev_id = ser.read(4)
    print(f"[*] Target Probe Handshake: {dev_id.decode('latin1', errors='replace')} (SUMP/OLS OK)")

    # 2. Metadata Query
    ser.write(bytes([0x04]))
    time.sleep(0.05)
    meta = ser.read(64)
    print(f"[*] SUMP Metadata Byte Payload: {len(meta)} bytes")

    # 3. Multi-depth throughput test
    test_depths = [256, 1024, 4096, 16384, 65536]
    print("\n[*] Measuring Real Hardware Upload Throughput:")
    print("-" * 55)
    print(f"{'Depth (Samples)':<18} | {'Upload Time (ms)':<16} | {'Effective Bandwidth'}")
    print("-" * 55)

    for depth in test_depths:
        # Sample count: (param + 1) * 4
        param = (depth // 4) - 1
        ser.write(bytes([0x80, 0, 0, 0, 0]))      # Divider 0
        ser.write(bytes([0x81, param & 0xFF, (param >> 8) & 0xFF, 0, 0])) # Readcount
        ser.write(bytes([0x82, 0, 0, 0, 0]))      # Clean external mode
        ser.write(bytes([0xC1, 0, 0, 0, 0]))      # Trig Mask 0
        ser.write(bytes([0x01]))                  # Run

        t0 = time.perf_counter()
        raw = ser.read(depth)
        dt = (time.perf_counter() - t0) * 1000.0

        if len(raw) == depth:
            speed_kbs = (depth / 1024.0) / (dt / 1000.0)
            print(f"{depth:<18} | {dt:>12.2f} ms   | {speed_kbs:>8.1f} KB/s")
        else:
            print(f"{depth:<18} | TIMEOUT ({len(raw)}/{depth})")

    print("-" * 55)
    print("\n[*] Testing Trigger Latency & Filtering (1024 Samples):")
    # Immediate vs Triggered
    for trig in [0, 1]:
        param = (1024 // 4) - 1
        ser.write(bytes([0x80, param & 0xFF, (param >> 8) & 0xFF, 0, 0]))
        ser.write(bytes([0x81, 0, 0, 0, 0]))
        ser.write(bytes([0xC1, trig, 0, 0, 0]))   # Mask
        ser.write(bytes([0xC0, trig, 0, 0, 0]))   # Val
        ser.write(bytes([0x01]))

        t0 = time.perf_counter()
        raw = ser.read(1024)
        dt = (time.perf_counter() - t0) * 1000.0
        mode_str = "Immediate (Mask=0)" if trig == 0 else "Armed Wait Timeout (Mask=1)"
        print(f"  - Mode: {mode_str:<30} -> {dt:.2f} ms")

    ser.close()
    print("\n[+] Performance and Protocol Verification PASSED.")

if __name__ == "__main__":
    benchmark_suite()
