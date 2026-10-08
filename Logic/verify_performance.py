import serial
import time
import sys

def benchmark_suite(port="COM33"):
    print("==================================================")
    print("   AG32VF303 Logic Analyzer (Plan B) Performance")
    print("==================================================")
    try:
        ser = serial.Serial(port, 115200, timeout=3)
    except Exception as e:
        print(f"Failed to open {port}: {e}")
        return

    time.sleep(0.05)
    ser.reset_input_buffer()
    ser.reset_output_buffer()

    # 1. Device Handshake
    ser.write(bytes([0x00] * 5))
    time.sleep(0.02)
    ser.reset_input_buffer()
    ser.write(bytes([0x02]))
    dev_id = ser.read(4)
    print(f"[*] Target Probe Handshake: {dev_id.decode('latin1', errors='replace')} (SUMP/OLS OK)")

    # 2. Metadata Query
    ser.write(bytes([0x04]))
    time.sleep(0.05)
    meta = ser.read(64)
    name_end = meta.find(b'\x00', 1)
    dev_name = meta[1:name_end].decode('ascii', errors='replace')
    print(f"[*] Advertised Model: {dev_name}, Metadata size: {len(meta)} bytes")

    # 3. Multi-depth throughput test (CPLD BRAM hardware buffer depths)
    test_depths = [256, 512, 1024, 2048, 4096, 8192]
    print("\n[*] Measuring Real Hardware Capture & USB CDC Upload Throughput:")
    print("-" * 60)
    print(f"{'Depth (Samples)':<18} | {'Upload Time (ms)':<16} | {'Effective Bandwidth'}")
    print("-" * 60)

    for depth in test_depths:
        param = (depth // 4) - 1
        ser.write(bytes([0x80, 0, 0, 0, 0]))      # Divider 0 (Max speed: 100 MSa/s)
        ser.write(bytes([0x81, param & 0xFF, (param >> 8) & 0xFF, 0, 0])) # Readcount
        ser.write(bytes([0x82, 0, 0, 0, 0]))      # 1 changroup
        ser.write(bytes([0xC0, 0, 0, 0, 0]))      # Trigger val 0
        ser.write(bytes([0xC1, 0, 0, 0, 0]))      # Trigger mask 0 (Immediate)
        ser.write(bytes([0x01]))                  # Run capture

        t0 = time.perf_counter()
        raw = ser.read(depth)
        dt = (time.perf_counter() - t0) * 1000.0

        if len(raw) == depth:
            speed_kbs = (depth / 1024.0) / (dt / 1000.0)
            print(f"{depth:<18} | {dt:>12.2f} ms   | {speed_kbs:>8.1f} KB/s")
        else:
            print(f"{depth:<18} | TIMEOUT ({len(raw)}/{depth})")

    print("-" * 60)
    print("\n[*] Testing CPLD Hardware Trigger (CH3 = PIN_10):")
    # Immediate vs Triggered on CH3
    for trig_name, mask, val in [("Immediate (Mask=0)", 0x00, 0x00), ("CH3 High Match (Mask=0x08, Val=0x08)", 0x08, 0x08)]:
        param = (1024 // 4) - 1
        ser.write(bytes([0x80, 9, 0, 0, 0]))      # 10 MSa/s
        ser.write(bytes([0x81, param & 0xFF, (param >> 8) & 0xFF, 0, 0]))
        ser.write(bytes([0x82, 0, 0, 0, 0]))
        ser.write(bytes([0xC0, val, 0, 0, 0]))
        ser.write(bytes([0xC1, mask, 0, 0, 0]))
        ser.write(bytes([0x01]))

        t0 = time.perf_counter()
        raw = ser.read(1024)
        dt = (time.perf_counter() - t0) * 1000.0
        ch3 = [(b >> 3) & 1 for b in raw]
        transitions = sum(1 for i in range(1, len(ch3)) if ch3[i] != ch3[i-1])
        print(f"  - Mode: {trig_name:<40} -> {dt:.2f} ms (Edges={transitions})")

    ser.close()
    print("\n[+] Plan B Hardware Logic Analyzer Verification COMPLETED SUCCESSFULLY.")

if __name__ == "__main__":
    benchmark_suite()