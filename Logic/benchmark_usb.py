import serial
import time

def run_test():
    ser = serial.Serial('COM33', 115200, timeout=3)
    ser.write(b'\x00\x00\x00\x00\x00')
    time.sleep(0.05)
    ser.reset_input_buffer()

    test_sizes = [16384, 32768, 65536, 131072, 262144]
    print("=== AG32 USB 2.0 Full-Speed 真实物理极限实测 (COM33) ===")
    print(f"{'测试包大小':<16} | {'实收字节数':<12} | {'传输总耗时 (ms)':<16} | {'实测有效吞吐 (KB/s)':<20} | {'实测线速率 (Mbps)':<18}")
    print("-" * 92)

    for size in test_sizes:
        units = (size // 4) - 1
        cmd = bytes([0x80, units & 0xFF, (units >> 8) & 0xFF, 0, 0])
        ser.write(cmd)
        time.sleep(0.02)
        ser.reset_input_buffer()

        ser.write(b'\x0A')

        t0 = time.perf_counter()
        received = 0
        while received < size:
            chunk = ser.read(min(size - received, 16384))
            if not chunk:
                break
            received += len(chunk)
        t1 = time.perf_counter()

        elapsed_ms = (t1 - t0) * 1000
        if received > 0 and elapsed_ms > 0:
            speed_kbs = (received / 1024) / (elapsed_ms / 1000)
            speed_mbps = (received * 8 / 1_000_000) / (elapsed_ms / 1000)
            print(f"{size//1024:>4} KB ({size:>6} B) | {received:>10} B | {elapsed_ms:>14.2f} ms | {speed_kbs:>18.2f} KB/s | {speed_mbps:>16.2f} Mbps")
        else:
            print(f"{size//1024} KB 测试超时未收到数据")
    ser.close()

if __name__ == '__main__':
    run_test()
