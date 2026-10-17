# Logic/captures/ — 抓图与波形导出

| 文件 | 来源 | 说明 |
|---|---|---|
| `planb-capture-2026-10-10.vcd` | 方案 B CPLD 采样导出 | CH0~CH3 = PIN_7~10；可直接拖进 PulseView / GTKWave |
| `pulseview_check.png` | PulseView 连接验证 | SUMP 协议直连成功截图 |

生成方式：`Logic/run_la.py` / `Logic/capture_and_visualize.py`（默认在 `Logic/` 下输出 `capture.vcd`，需要留档时移入本目录并加日期后缀）。

> `Logic/.gitignore` 默认忽略 `*.vcd`，但保留 `!captures/*.vcd`，本目录内的波形可入库。
