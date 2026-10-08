import serial
import time
import sys

def capture_samples(port="COM33", count=256, divider=0):
    ser = serial.Serial(port, 115200, timeout=2)
    ser.reset_input_buffer()
    ser.reset_output_buffer()

    # SUMP Reset
    ser.write(bytes([0x00]))
    time.sleep(0.05)
    ser.reset_input_buffer()

    # SUMP Sample Count: (param + 1) * 4
    param = (count // 4) - 1
    if param < 0:
        param = 0
    ser.write(bytes([0x80, param & 0xFF, (param >> 8) & 0xFF, 0, 0]))

    # Divider
    ser.write(bytes([0x81, divider & 0xFF, (divider >> 8) & 0xFF, (divider >> 16) & 0xFF, 0]))

    # Trigger Mask: 0
    ser.write(bytes([0xC1, 0, 0, 0, 0]))

    # Run
    ser.write(bytes([0x01]))

    data = ser.read(count)
    ser.close()
    return list(data)

def export_vcd(samples, filename="capture.vcd", time_step_ns=50):
    with open(filename, "w", encoding="utf-8") as f:
        f.write("$date\n  " + time.asctime() + "\n$end\n")
        f.write("$version\n  AG32 Logic Analyzer VCD Export\n$end\n")
        f.write("$timescale 1ns $end\n")
        f.write("$scope module ag32_la $end\n")
        f.write("$var wire 1 ! ch0 $end\n")
        f.write("$var wire 1 \" ch1 $end\n")
        f.write("$var wire 1 # ch2 $end\n")
        f.write("$var wire 1 $ ch3 $end\n")
        f.write("$upscope $end\n")
        f.write("$enddefinitions $end\n")
        f.write("$dumpvars\n0!\n0\"\n0#\n0$\n$end\n")

        last_ch = [-1, -1, -1, -1]
        cur_time = 0
        symbols = ["!", "\"", "#", "$"]

        for sample in samples:
            for ch in range(4):
                val = (sample >> ch) & 1
                if val != last_ch[ch]:
                    f.write(f"#{cur_time}\n")
                    f.write(f"{val}{symbols[ch]}\n")
                    last_ch[ch] = val
            cur_time += time_step_ns

def print_ascii_waveform(samples, length=64):
    print("\n=== Real-time Channel Waveforms (First " + str(length) + " Samples) ===")
    ch_names = ["CH0 (PIN_7 (CH0))", "CH1 (PIN_8 (CH1))", "CH2 (PIN_9 (CH2))", "CH3 (PIN_10 (CH3))"]
    for ch in range(4):
        line = f"{ch_names[ch]:14s}: "
        for s in samples[:length]:
            bit = (s >> ch) & 1
            line += "-" if bit == 1 else "_"
        print(line)
    print(" " * 16 + "0" + " " * (length - 3) + str(length))

def main():
    print("Capturing 512 samples from AG32 Logic Analyzer on COM33...")
    samples = capture_samples("COM33", 512, divider=0)
    print(f"Successfully captured {len(samples)} samples!")
    
    print_ascii_waveform(samples, length=64)
    
    export_vcd(samples, r"C:\Users\Administrator\Documents\AG32\Logic\capture.vcd")
    print("\nExported standard VCD waveform to capture.vcd (Ready for PulseView / GTKWave).")

if __name__ == "__main__":
    main()
