import serial
import time
import sys

def capture_samples(port="COM33", count=1024, divider=9):
    ser = serial.Serial(port, 115200, timeout=2)
    ser.reset_input_buffer()
    ser.reset_output_buffer()

    # SUMP Reset
    ser.write(bytes([0x00] * 5))
    time.sleep(0.05)
    ser.reset_input_buffer()

    # SUMP Divider (0x80): 24-bit divider
    ser.write(bytes([0x80, divider & 0xFF, (divider >> 8) & 0xFF, (divider >> 16) & 0xFF, 0]))

    # SUMP Sample Count (0x81): readcount = (count // 4) - 1
    readcount = (count // 4) - 1
    if readcount < 0:
        readcount = 0
    ser.write(bytes([0x81, readcount & 0xFF, (readcount >> 8) & 0xFF, 0, 0]))

    # SUMP Flags (0x82): 1 changroup
    ser.write(bytes([0x82, 0, 0, 0, 0]))

    # Trigger Mask & Val (0xC0, 0xC1): mask = 0 (immediate capture)
    ser.write(bytes([0xC0, 0, 0, 0, 0]))
    ser.write(bytes([0xC1, 0, 0, 0, 0]))

    # Run Capture (0x01)
    ser.write(bytes([0x01]))

    data = ser.read(count)
    ser.close()
    return list(data)

def export_vcd(samples, filename="capture.vcd", time_step_ns=100):
    with open(filename, "w", encoding="utf-8") as f:
        f.write("$date\n  " + time.asctime() + "\n$end\n")
        f.write("$version\n  AG32 Logic Analyzer (Plan B CPLD Sampler) VCD Export\n$end\n")
        f.write("$timescale 1ns $end\n")
        f.write("$scope module ag32_cpld_la $end\n")
        f.write("$var wire 1 ! ch0_pin7 $end\n")
        f.write("$var wire 1 \" ch1_pin8 $end\n")
        f.write("$var wire 1 # ch2_pin9 $end\n")
        f.write("$var wire 1 $ ch3_pin10 $end\n")
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

def print_ascii_waveform(samples, length=80):
    print("\n=== Real-time Channel Waveforms (First " + str(length) + " Samples) ===")
    ch_names = ["CH0 (PIN_7)", "CH1 (PIN_8)", "CH2 (PIN_9)", "CH3 (PIN_10)"]
    for ch in range(4):
        line = f"{ch_names[ch]:14s}: "
        for s in samples[:length]:
            bit = (s >> ch) & 1
            line += "-" if bit == 1 else "_"
        print(line)
    print(" " * 16 + "0" + " " * (length - 3) + str(length))

def main():
    print("Capturing 1024 samples from AG32 Logic Analyzer on COM33 (Plan B: CPLD Sampler)...")
    samples = capture_samples("COM33", 1024, divider=9) # 10 MSa/s
    print(f"Successfully captured {len(samples)} samples!")

    ch3_ones = sum(1 for s in samples if (s >> 3) & 1)
    ch3_zeros = len(samples) - ch3_ones
    transitions = sum(1 for i in range(1, len(samples)) if ((samples[i] >> 3) & 1) != ((samples[i-1] >> 3) & 1))
    print(f"CH3 (PIN_10 jumper to PIN_11): High={ch3_ones}, Low={ch3_zeros}, Edge transitions={transitions}")

    print_ascii_waveform(samples, length=80)
    
    export_vcd(samples, r"C:\Users\Administrator\Documents\AG32\Logic\capture.vcd")
    print("\nExported standard VCD waveform to capture.vcd (Ready for PulseView / GTKWave).")

if __name__ == "__main__":
    main()
