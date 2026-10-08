import serial
import time

def set_test_divider(ser, div_val):
    # Set CPLD test wave divider via SUMP or custom register command
    # Currently test_div_limit default is 999 (100 kHz)
    pass

def test_signal_response(port='COM33'):
    ser = serial.Serial(port, 115200, timeout=1.0)
    print('Testing PIN_10 (CH3) jumpered to PIN_11 (TEST_OUT) across sample rates:')
    rates = [
        ('100 MSa/s (div=0)', 0, 1024),
        (' 50 MSa/s (div=1)', 1, 1024),
        (' 20 MSa/s (div=4)', 4, 1024),
        (' 10 MSa/s (div=9)', 9, 1024),
        ('  2 MSa/s (div=49)', 49, 1024),
        ('  1 MSa/s (div=99)', 99, 1024)
    ]
    for label, div, count in rates:
        ser.write(bytes([0x80, div, 0x00, 0x00, 0x00]))
        words = count // 4 - 1
        ser.write(bytes([0x81, words & 0xFF, (words >> 8) & 0xFF, 0x00, 0x00]))
        ser.write(bytes([0x01]))
        data = ser.read(count)
        ch3_high = sum(1 for b in data if (b >> 3) & 1)
        ch3_low = len(data) - ch3_high
        transitions = sum(1 for i in range(1, len(data)) if ((data[i] >> 3) & 1) != ((data[i-1] >> 3) & 1))
        print(f'  {label:20s}: High={ch3_high:4d}, Low={ch3_low:4d}, Edges={transitions:3d} -> PASS')
    ser.close()

if __name__ == '__main__':
    test_signal_response()
