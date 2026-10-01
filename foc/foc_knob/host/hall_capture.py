import serial, time, json

ser = serial.Serial("COM26", 115200, timeout=0.05)
time.sleep(0.5)
ser.reset_input_buffer()
ser.write(b"tel 200\r\n")
time.sleep(0.3)
ser.reset_input_buffer()

def edges():
    ser.write(b"st\r\n"); time.sleep(0.3)
    t = ser.read(4096).decode(errors="replace")
    for l in t.splitlines():
        if "mode=" in l:
            return int(l.split("edges=")[1].split()[0])
    return -1

e0 = edges()
print("等待开始转动 (edges=%d)..." % e0, flush=True)
t0 = time.time()
started = False
while time.time() - t0 < 90:
    e = edges()
    if e != e0 and e >= 0:
        started = True
        break
if not started:
    print("TIMEOUT: 90s 内未检测到转动")
    ser.write(b"tel 0\r\n"); ser.close(); raise SystemExit

print("检测到转动！采集 12 秒...", flush=True)
t1 = time.time(); buf = b""
t_start = time.time()
while time.time() - t1 < 12:
    buf += ser.read(16384)
ser.write(b"tel 0\r\n"); time.sleep(0.2)
e1 = edges()
txt = buf.decode(errors="replace")
rows = []
for l in txt.splitlines():
    if l.startswith("$T,"):
        p = l.split(",")
        if len(p) >= 9:
            rows.append({"t": round(time.time()-t_start, 3), "hall": int(p[6]),
                         "ang": int(p[2])/100.0, "vel": int(p[3])/1000.0})
out = {"edges_before": e0, "edges_after": e1, "frames": rows}
with open(r"C:\Users\Administrator\Documents\AG32\foc\foc_knob\hall_seq.json", "w") as f:
    json.dump(out, f)
print("采集完成: %d 帧, edges %d -> %d, 已存 hall_seq.json" % (len(rows), e0, e1), flush=True)
ser.close()
