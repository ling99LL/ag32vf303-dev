"""
AG32-LA4 Interactive Command-Line Tool (Plan B: CPLD Hardware Sampler)
Usage:
    python run_la.py                     # Default 1024 samples capture & ASCII display
    python run_la.py --samples 4096      # Capture 4096 samples
    python run_la.py --divider 9         # Sample at 10 MSa/s
    python run_la.py --vcd my_trace.vcd  # Export to VCD file
"""

import serial
import time
import sys
import argparse

def parse_args():
    parser = argparse.ArgumentParser(description="AG32VF303 4-Channel Logic Analyzer CLI (Plan B: CPLD Sampler)")
    parser.add_argument("--port", default="COM33", help="USB CDC Port (default: COM33)")
    parser.add_argument("--samples", type=int, default=1024, help="Number of samples to capture (4..8192)")
    parser.add_argument("--divider", type=int, default=9, help="Clock divider (0 = 100MSa/s, 1 = 50MSa/s, 9 = 10MSa/s, 99 = 1MSa/s)")
    parser.add_argument("--trigger-mask", type=int, default=0, help="Channel trigger mask (0x0..0xF)")
    parser.add_argument("--trigger-val", type=int, default=0, help="Channel trigger value (0x0..0xF)")
    parser.add_argument("--vcd", default="capture.vcd", help="Path to export VCD waveform")
    parser.add_argument("--disp-len", type=int, default=64, help="ASCII preview width")
    return parser.parse_args()

def run_capture(args):
    print(f"Connecting to AG32 Logic Analyzer (Plan B) on {args.port}...")
    try:
        ser = serial.Serial(args.port, 115200, timeout=3)
    except Exception as e:
        print(f"Error opening {args.port}: {e}")
        return

    time.sleep(0.05)
    ser.reset_input_buffer()
    ser.reset_output_buffer()

    # Reset
    ser.write(bytes([0x00] * 5))
    time.sleep(0.02)
    ser.reset_input_buffer()

    # Query ID
    ser.write(bytes([0x02]))
    dev_id = ser.read(4)
    if dev_id != b"1ALS":
        print(f"Warning: Unexpected Device ID: {dev_id}")
    else:
        print("Connected to device: AG32-PlanB (SUMP / OLS compatible)")

    # Sample Count config: (param + 1) * 4
    count = max(4, min(8192, args.samples))
    param = (count // 4) - 1
    # Divider config (SUMP standard: 0x80 = CMD_SET_DIVIDER)
    ser.write(bytes([0x80, args.divider & 0xFF, (args.divider >> 8) & 0xFF, (args.divider >> 16) & 0xFF, 0]))

    # Sample count config (SUMP standard: 0x81 = CMD_CAPTURE_SIZE)
    ser.write(bytes([0x81, param & 0xFF, (param >> 8) & 0xFF, 0, 0]))

    # Flags config (SUMP_FLAGS: 0x82)
    ser.write(bytes([0x82, 0x00, 0, 0, 0]))

    # Trigger config
    ser.write(bytes([0xC1, args.trigger_mask & 0x0F, 0, 0, 0]))
    ser.write(bytes([0xC0, args.trigger_val & 0x0F, 0, 0, 0]))

    print(f"Arming CPLD hardware capture: {count} samples, divider={args.divider}, trig_mask=0x{args.trigger_mask:X}...")
    ser.write(bytes([0x01]))

    t0 = time.time()
    data = ser.read(count)
    dt = (time.time() - t0) * 1000

    if len(data) < count:
        print(f"Timeout/Partial receive: got {len(data)}/{count} samples")
    else:
        print(f"Capture complete! Received {len(data)} samples in {dt:.2f} ms")

    ser.close()

    # ASCII Waveform Plot
    disp = min(len(data), args.disp_len)
    if disp > 0:
        print(f"\n=== Channel Waveform Preview (First {disp} Samples) ===")
        ch_names = ["CH0 (PIN_7)", "CH1 (PIN_8)", "CH2 (PIN_9)", "CH3 (PIN_10)"]
        for ch in range(4):
            line = f"{ch_names[ch]:14s}: "
            for s in data[:disp]:
                line += "1" if ((s >> ch) & 1) else "0"
            print(line)
        print(" " * 16 + "0" + " " * (disp - 3) + str(disp))

    # Export VCD
    if args.vcd:
        with open(args.vcd, "w", encoding="utf-8") as f:
            f.write("$date\n  " + time.asctime() + "\n$end\n")
            f.write("$version\n  AG32-PlanB CPLD Sampler VCD\n$end\n")
            f.write("$timescale 1ns $end\n")
            f.write("$scope module ag32_cpld_la $end\n")
            f.write("$var wire 1 ! ch0_pin7 $end\n")
            f.write("$var wire 1 \" ch1_pin8 $end\n")
            f.write("$var wire 1 # ch2_pin9 $end\n")
            f.write("$var wire 1 $ ch3_pin10 $end\n")
            f.write("$upscope $end\n")
            f.write("$enddefinitions $end\n")
            f.write("$dumpvars\n0!\n0\"\n0#\n0$\n$end\n")
            last = [-1, -1, -1, -1]
            symbols = ["!", "\"", "#", "$"]
            cur_time = 0
            step_ns = 10 * (args.divider + 1)
            for s in data:
                for ch in range(4):
                    v = (s >> ch) & 1
                    if v != last[ch]:
                        f.write(f"#{cur_time}\n")
                        f.write(f"{v}{symbols[ch]}\n")
                        last[ch] = v
                cur_time += step_ns
        print(f"\nSaved VCD to '{args.vcd}' (Ready for PulseView)")

if __name__ == "__main__":
    run_capture(parse_args())