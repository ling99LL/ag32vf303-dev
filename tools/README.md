# tools/ — 工作区级调试探针

这里放**不绑定单一工程**的板级调试脚本。用途：JTAG/SWD 直读寄存器、确认目标板是否卡死、验证 Supra 器件库是否可用。

## openocd/ — OpenOCD 直读探针

用法（把 cfg 路径换成实际位置）：

```bash
openocd -f <interface.cfg> -f <target.cfg> -f tools/openocd/probe-pc.cfg
```

| 文件 | 做什么 | 判读 |
|---|---|---|
| `probe-pc.cfg` | halt 后打印当前 PC 再 resume | PC ≈ `0x0001xxxx` = 卡在 ROM（多为 logic 未烧 / 位流地址不符） |
| `probe-flash-id.cfg` | 读 `0x80000000` 起 4 个字 | 校验 flash 头部内容 |
| `probe-gpio4-regs.cfg` | 读 `0x40018000` GPIO4 寄存器组 | Demo 板 LED（GPIO4_1..4，低电平点亮）驱动状态 |
| `probe-sys-state.cfg` | 读 GPIO0 / GPIO4 / UART0 状态寄存器 | 输入冻结、UART 是否就绪 |

> 说明：`mdw` 在 `openocd_cmd.bat` 下可能静默，脚本统一用 `mem2array` + `echo` 输出。

## supra/ — Supra 探针

| 文件 | 做什么 |
|---|---|
| `probe-arch-AGRV2KL100.tcl` | 加载 AGRV2KL100 架构并打印器件信息，验证 Supra 安装可用 |

```bash
af_cmd.bat -f tools/supra/probe-arch-AGRV2KL100.tcl
```

## 相关

- 工程内探针：`FOC2205/tools/probe_state.bat`（DMI 直读判 AHB 挂死）、`Logic/read_reg.cfg` 等。
- 完整索引见 [../INDEX.md](../INDEX.md)。
