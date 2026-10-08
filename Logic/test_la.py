import serial
import time
import sys

def main():
    port = 'COM33'
    baud = 115200
    print(f'=== Testing AG32 Logic Analyzer on {port} ===')
    
    try:
        ser = serial.Serial(port, baud, timeout=2)
    except Exception as e:
        print(f'Failed to open {port}: {e}')
        sys.exit(1)

    time.sleep(0.1)
    ser.reset_input_buffer()
    ser.reset_output_buffer()

    # 1. SUMP Reset
    ser.write(bytes([0x00]))
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
    
    # 4. Perform Capture with 512 samples
    # SUMP_SAMPLE_COUNT: (127 + 1) * 4 = 512 samples
    ser.write(bytes([0x80, 127, 0, 0, 0]))
    # SUMP_DIVIDER: 0 (fastest)
    ser.write(bytes([0x81, 0, 0, 0, 0]))
    # SUMP_TRIGGER_MASK: 0 (immediate trigger)
    ser.write(bytes([0xC1, 0, 0, 0, 0]))
    # SUMP_RUN: 0x01
    ser.write(bytes([0x01]))

    t0 = time.time()
    samples = ser.read(512)
    dt = (time.time() - t0) * 1000
    print(f'3. Capture: received {len(samples)}/512 samples in {dt:.2f} ms')
    assert len(samples) == 512, f'Expected 512 samples, got {len(samples)}'

    # 5. Perform Capture with 4096 samples
    # SUMP_SAMPLE_COUNT: (1023 + 1) * 4 = 4096 samples
    ser.write(bytes([0x80, 0xFF, 0x03, 0, 0]))
    ser.write(bytes([0x01]))
    t0 = time.time()
    samples_4k = ser.read(4096)
    dt_4k = (time.time() - t0) * 1000
    print(f'4. Large Burst: received {len(samples_4k)}/4096 samples in {dt_4k:.2f} ms')
    assert len(samples_4k) == 4096, f'Expected 4096 samples, got {len(samples_4k)}'

    # 6. Perform Full 64KB Capture
    # SUMP_SAMPLE_COUNT: (16383 + 1) * 4 = 65536 samples
    ser.write(bytes([0x80, 0xFF, 0x3F, 0, 0]))
    ser.write(bytes([0x01]))
    t0 = time.time()
    samples_64k = ser.read(65536)
    dt_64k = (time.time() - t0) * 1000
    speed_kb = (len(samples_64k) / 1024.0) / (dt_64k / 1000.0)
    print(f'5. Full 64KB Buffer: received {len(samples_64k)}/65536 samples in {dt_64k:.2f} ms (~{speed_kb:.1f} KB/s)')
    assert len(samples_64k) == 65536, f'Expected 65536 samples, got {len(samples_64k)}'

    print('\n=== ALL HARDWARE LOGIC ANALYZER TESTS PASSED! ===')
    ser.close()

if __name__ == '__main__':
    main()
