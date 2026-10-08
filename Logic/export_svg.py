import serial, time

ser = serial.Serial('COM33', 115200, timeout=2)
ser.write(b'\x00' * 5)
time.sleep(0.02)
ser.write(bytes([0x80, 0x09, 0, 0, 0])) # 10 MSa/s
ser.write(bytes([0x81, 0xFF, 0, 0, 0])) # 1024 samples
ser.write(bytes([0x82, 0, 0, 0, 0]))
ser.write(bytes([0xC0, 0x08, 0, 0, 0])) # Trigger on CH3
ser.write(bytes([0xC1, 0x08, 0, 0, 0]))
ser.write(b'\x01')
data = list(ser.read(1024))
ser.close()

width = 960
height = 360
margin_left = 180
margin_right = 40
margin_top = 40
plot_width = width - margin_left - margin_right
row_h = 65

channels = [
    ('CH0 (PIN 7)', [(b >> 0) & 1 for b in data[:120]], '#00d2d3'),
    ('CH1 (PIN 8)', [(b >> 1) & 1 for b in data[:120]], '#ff9f43'),
    ('CH2 (PIN 9)', [(b >> 2) & 1 for b in data[:120]], '#1dd1a1'),
    ('CH3 (PIN 10 -> PIN 11)', [(b >> 3) & 1 for b in data[:120]], '#ee5253'),
]

svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" style="background:#1e1e2e; font-family:Consolas, monospace;">']
svg.append(f'<text x="{width//2}" y="25" fill="#cdd6f4" font-size="16" text-anchor="middle" font-weight="bold">AG32 Logic Analyzer (Plan B: CPLD Hardware Sampler) Live Capture @ 10 MSa/s</text>')

n_pts = 120
step_x = plot_width / (n_pts - 1)
for i in range(0, n_pts, 10):
    x = margin_left + i * step_x
    svg.append(f'<line x1="{x}" y1="40" x2="{x}" y2="{height-40}" stroke="#313244" stroke-dasharray="3,3" />')
    svg.append(f'<text x="{x}" y="{height-25}" fill="#a6adc8" font-size="10" text-anchor="middle">{i*0.1:.1f}us</text>')

for idx, (ch_name, sig, color) in enumerate(channels):
    y_base = margin_top + idx * row_h + 45
    y_high = y_base - 30
    svg.append(f'<text x="{margin_left-15}" y="{y_base-10}" fill="{color}" font-size="13" text-anchor="end" font-weight="bold">{ch_name}</text>')
    svg.append(f'<line x1="{margin_left}" y1="{y_base}" x2="{width-margin_right}" y2="{y_base}" stroke="#45475a" />')
    
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
print('SVG exported successfully to:', svg_out)
