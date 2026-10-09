import serial, time

ser = serial.Serial('COM33', 115200, timeout=1.0)
ser.dtr = True
ser.rts = True
time.sleep(0.05)
ser.write(b'\x00' * 5)
time.sleep(0.02)
ser.reset_input_buffer()

# Capture 1024 samples at 10 MSa/s (div=9)
ser.write(bytes([0x80, 0x09, 0, 0, 0])) # 10 MSa/s
words = 1024 // 4 - 1
ser.write(bytes([0x81, words & 0xFF, (words >> 8) & 0xFF, 0, 0]))
ser.write(bytes([0xC0, 0, 0, 0, 0])) # Immediate capture
ser.reset_input_buffer()
ser.write(b'\x01')
data = list(ser.read(1024))
ser.close()

width = 1000
height = 380
margin_left = 220
margin_right = 50
margin_top = 45
plot_width = width - margin_left - margin_right
row_h = 70

n_pts = 120
step_x = plot_width / (n_pts - 1)

channels = [
    ('CH0 (PIN 7, Input)', [(b >> 0) & 1 for b in data[:n_pts]], '#00d2d3'),
    ('CH1 (PIN 8, Input)', [(b >> 1) & 1 for b in data[:n_pts]], '#ff9f43'),
    ('CH2 (PIN 9, Input)', [(b >> 2) & 1 for b in data[:n_pts]], '#1dd1a1'),
    ('CH3 (PIN 10, Input)', [(b >> 3) & 1 for b in data[:n_pts]], '#ee5253'),
]

svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" style="background:#181825; font-family:Consolas, monospace;">']
svg.append(f'<text x="{width//2}" y="28" fill="#cdd6f4" font-size="16" text-anchor="middle" font-weight="bold">AG32VF303 4-CH Logic Analyzer Live Capture (50MHz Ext Crystal Ref @ 10 MSa/s)</text>')

# Time axis grid
for i in range(0, n_pts + 1, 10):
    if i < n_pts:
        x = margin_left + i * step_x
        svg.append(f'<line x1="{x}" y1="{margin_top}" x2="{x}" y2="{height-40}" stroke="#313244" stroke-dasharray="3,3" />')
        svg.append(f'<text x="{x}" y="{height-22}" fill="#a6adc8" font-size="10" text-anchor="middle">{i*0.1:.1f}us</text>')

for idx, (ch_name, sig, color) in enumerate(channels):
    y_base = margin_top + idx * row_h + 50
    y_high = y_base - 32
    
    # Status label
    high_cnt = sum(sig)
    status_text = "Active Waveform" if high_cnt > 0 else "Weak Pulled-Down (0 Noise)"
    
    svg.append(f'<text x="{margin_left-15}" y="{y_base-14}" fill="{color}" font-size="12" text-anchor="end" font-weight="bold">{ch_name}</text>')
    svg.append(f'<text x="{margin_left-15}" y="{y_base}" fill="#6c7086" font-size="9" text-anchor="end">{status_text}</text>')
    svg.append(f'<line x1="{margin_left}" y1="{y_base}" x2="{width-margin_right}" y2="{y_base}" stroke="#45475a" stroke-dasharray="2,4" />')
    
    path = []
    for i in range(n_pts):
        x = margin_left + i * step_x
        y = y_high if sig[i] == 1 else y_base
        if i == 0:
            path.append(f'M {x:.1f} {y:.1f}')
        else:
            prev_y = y_high if sig[i-1] == 1 else y_base
            if prev_y != y:
                path.append(f'H {x:.1f} V {y:.1f}')
            else:
                path.append(f'H {x:.1f}')
    
    svg.append(f'<path d="{" ".join(path)}" fill="none" stroke="{color}" stroke-width="2.5" stroke-linejoin="round" />')

svg.append('</svg>')
svg_out = r'C:\Users\Administrator\Documents\AG32\Logic\plan_b_live_waveform.svg'
with open(svg_out, 'w', encoding='utf-8') as f:
    f.write('\n'.join(svg))
print('Live SVG updated successfully:', svg_out)
