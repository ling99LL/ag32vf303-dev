import serial
import time

def run_suite():
    s = serial.Serial('COM33', 115200, timeout=3)
    s.write(b'\x00\x00\x00\x00\x00')
    time.sleep(0.05)
    s.reset_input_buffer()
    
    tests = [
        (16384, b'\x0B'),
        (32768, b'\x0C'),
        (65536, b'\x0D'),
        (131072, b'\x0E'),
        (262144, b'\x0F'),
    ]
    
    print("=== AG32 USB 2.0 Full-Speed 真实连续吞吐实机极限测定 ===")
    print("测试条件: 硬件直测 (纯USB CDC, 无CPLD解包耗时, 50MHz有源晶振基准)")
    print("-" * 84)
    print(f"{'负载大小':<16} | {'实收字节数':<12} | {'传输耗时 (ms)':<16} | {'实测吞吐 (KB/s)':<18} | {'实测速率 (Mbps)':<14}")
    print("-" * 84)
    
    for size, trigger_cmd in tests:
        s.write(trigger_cmd)
        t0 = time.perf_counter()
        received = 0
        while received < size:
            chunk = s.read(min(size - received, 16384))
            if not chunk:
                break
            received += len(chunk)
        t1 = time.perf_counter()
        
        elapsed_ms = (t1 - t0) * 1000
        if received > 0 and elapsed_ms > 0:
            speed_kbs = (received / 1024.0) / (elapsed_ms / 1000.0)
            speed_mbps = (received * 8.0 / 1000000.0) / (elapsed_ms / 1000.0)
            print(f"{size//1024:>4} KB ({size:>6} B) | {received:>10} B | {elapsed_ms:>14.2f} ms | {speed_kbs:>16.2f} KB/s | {speed_mbps:>12.2f} Mbps")
        else:
            print(f"{size//1024:>4} KB 失败: 未接收到完整数据 (已收 {received} 字节)")
        time.sleep(0.05)
    s.close()

if __name__ == '__main__':
    run_suite()
