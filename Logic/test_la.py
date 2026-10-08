import serial
import time
import sys

def main():
    port = 'COM33'
    baud = 115200
    print(f'=== Testing AG32 Logic Analyzer (Plan B: CPLD Sampler) on {port} ===')
    
    try:
        ser = serial.Serial(port, baud, timeout=2)
    except Exception as e:
        print(f'Failed to open {port}: {e}')
        sys.exit(1)

    time.sleep(0.1)
    ser.reset_input_buffer()
    ser.reset_output_buffer()

    # 1. SUMP Reset
    ser.write(bytes([0x00] * 5))
    time.sleep(0.05)
    ser.reset_input_buffer()

    # 2. Query Device ID
    ser.write(bytes([0x02]))
    dev_id = ser.read(4)
    id_str = dev_id.decode('latin1', errors='replace')
    print(f'1. Device ID: {id_str} (Expected: 1ALS)')
    assert dev_id == b'1ALS', f'Unexpected Device ID: {dev_id}'

    # 3. Query Metadata
    ser.write(bytes([0x04]))
    time.sleep(0.05)
    meta = ser.read(64)
    print(f'2. Metadata raw bytes ({len(meta)} B): {list(meta)}')
    # Check advertised name in metadata
    name_end = meta.find(b'\x00', 1)
    dev_name = meta[1:name_end].decode('ascii', errors='replace')
    print(f'   Device Name: {dev_name}')

    # 4. Perform Capture with 512 samples
    readcount_512 = (512 // 4) - 1
    ser.write(bytes([0x80, 0x09, 0, 0, 0])) # 10 MSa/s divider
    ser.write(bytes([0x81, readcount_512 & 0xFF, (readcount_512 >> 8) & 0xFF, 0, 0]))
    ser.write(bytes([0x82, 0, 0, 0, 0]))
    ser.write(bytes([0xC0, 0, 0, 0, 0]))
    ser.write(bytes([0xC1, 0, 0, 0, 0]))
    ser.write(bytes([0x01]))

    t0 = time.time()
    samples = ser.read(512)
    dt = (time.time() - t0) * 1000
    print(f'3. Capture (512 samples): received {len(samples)}/512 in {dt:.2f} ms')
    assert len(samples) == 512, f'Expected 512 samples, got {len(samples)}'

    # 5. Perform Capture with 4096 samples
    readcount_4k = (4096 // 4) - 1
    ser.write(bytes([0x81, readcount_4k & 0xFF, (readcount_4k >> 8) & 0xFF, 0, 0]))
    ser.write(bytes([0x01]))
    t0 = time.time()
    samples_4k = ser.read(4096)
    dt_4k = (time.time() - t0) * 1000
    print(f'4. Large Capture (4096 samples): received {len(samples_4k)}/4096 in {dt_4k:.2f} ms')
    assert len(samples_4k) == 4096, f'Expected 4096 samples, got {len(samples_4k)}'

    # 6. Perform Full CPLD BRAM Capture (8192 samples)
    readcount_8k = (8192 // 4) - 1
    ser.write(bytes([0x81, readcount_8k & 0xFF, (readcount_8k >> 8) & 0xFF, 0, 0]))
    ser.write(bytes([0x01]))
    t0 = time.time()
    samples_8k = ser.read(8192)
    dt_8k = (time.time() - t0) * 1000
    speed_kb = (len(samples_8k) / 1024.0) / (dt_8k / 1000.0)
    print(f'5. Full CPLD BRAM Buffer (8192 samples): received {len(samples_8k)}/8192 in {dt_8k:.2f} ms (~{speed_kb:.1f} KB/s)')
    assert len(samples_8k) == 8192, f'Expected 8192 samples, got {len(samples_8k)}'

    # Verify square wave on PIN_10 (CH3)
    ch3 = [(b >> 3) & 1 for b in samples_8k]
    transitions = sum(1 for i in range(1, len(ch3)) if ch3[i] != ch3[i-1])
    print(f'6. PIN_10 (CH3) signal verification: High={ch3.count(1)}, Low={ch3.count(0)}, Transitions={transitions}')
    assert transitions > 5, f'Expected square wave transitions on PIN_10, got {transitions}'

    print('\n=== ALL PLAN B CPLD LOGIC ANALYZER HARDWARE TESTS PASSED! ===')
    ser.close()

if __name__ == '__main__':
    main()