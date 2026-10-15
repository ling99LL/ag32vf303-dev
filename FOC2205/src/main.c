// main.c — FOC2205 bring-up flow (see docs/DRV8316+MT6701_FOC驱动板接线设计.md §6-7)
#include <stdio.h>
#include "board.h"
#include "spi.h"
#include "uart.h"
#include "app_io.h"
#include "drv8316.h"
#include "interrupt.h"
#include "mt6701.h"
#include "current.h"
#include "pwm3ph.h"
#include "foc.h"
#include "motion.h"

// 1 = 上电倒计时 3 秒后自动转一圈（倒计时内按 s 可取消）
// 0 = 开机不转：停在 MOTION_IDLE（torque_q = 0，电机自由不出力），等串口命令。
//     手动触发用 'r' / 'R'（±1 圈）。接线/调参阶段建议保持 0。
#ifndef MOTION_AUTORUN
#define MOTION_AUTORUN 0
#endif

#define POLE_PAIRS 7   // 2205(2804) 12N14P — docs/电机参数.md 已确认

// Bring-up stage marker (readable over JTAG): tells which step the firmware
// reached when there is no UART attached. Keep in sync with the values below.
volatile uint32_t g_stage;
#define STAGE(n) (g_stage = (n))

static volatile uint32_t s_isr_count;
// 实测的 PWM 更新中断频率（main 里标定；串口打印与窗口换算都要用）
static uint32_t s_isr_hz_g = 40000u;

static void foc_isr(void)
{
  // 顺序有意为之：FOC 先用上一拍算出的 torque_q 输出并刷新角度，手感层再用
  // 这个新角度算下一拍的指令。foc.c 本身一行未改。
  foc_step_isr();
  motion_step_isr();
  ++s_isr_count;
}

// NOTE (2026-10-15, A/B verified on board): no UART0 fix-up code is needed here.
// board_init() muxes PIN_20/PIN_21 correctly and the console works as-is.
// An earlier "uart0_tx_pad_fixup()" (enable GPIO7 APB clock + re-assert AFSEL)
// was added on the theory that the AF write was dropped; removing it changes
// nothing observable, so it is gone. Do not re-add it without an A/B test.
//
// Debug caveat: GPIO7's APB clock is left OFF by the SDK, so JTAG reads of any
// GPIO7 register return 0x00 (bus artifact, not the real content). tools/
// uart_pad.bat ORs APB_MASK_GPIO7 into SYS->APB_CLKENABLE itself before reading.

static void bringup_banner(void)
{
  printf("\n=== FOC2205 bring-up ===\n");
  printf("SYSCLK=%u BUSCLK=%u\n",
         (unsigned)SYS_GetSysClkFreq(),
         (unsigned)BOARD_BUS_FREQUENCY);
  // BOOT1(PIN_15) is 100% UNTOUCHED and dedicated to boot strap (10k pulldown).
  // INL_EN sits on PIN_28 (JNTRST pad) — DAPLink uses 2-wire Compact-JTAG, so
  // debugging is unaffected; an external 10k pulldown owns the pad at reset.
  printf("BootMode=%d (0=FLASH 1=UARTloader 3=SRAM)\n", (int)SYS_GetBootMode());
}

// Raw MT6701 SSI frames, captured for offline bit-alignment analysis.
volatile uint32_t g_mt_raw[4];
volatile uint32_t g_mt_n;
// CRC pass result per bit alignment: [0]=as captured, [1]=<<1, [2]=>>1.
// Non-zero means CRC6 passed; low 24 bits hold the frame that passed.
volatile uint32_t g_mt_shift[3];

static void mt_capture_raw(void)
{
  // Go through the real mt6701_read() path so the captured frames reflect
  // production timing, not a copy of it.
  mt6701_sample_t s;
  for (int k = 0; k < 4; ++k) {
    mt6701_read(&s);
    g_mt_raw[k] = g_mt_last_raw;
  }
  g_mt_n = 4;

  // Which bit alignment makes CRC6 pass? 0 = as captured, 1 = shifted left,
  // 2 = shifted right. Answers "is the frame off by one bit, and which way".
  for (int i = 0; i < 3; ++i) {
    uint32_t f = (i == 0) ? g_mt_last_raw
               : (i == 1) ? ((g_mt_last_raw << 1) & 0xFFFFFFu)
                          : (g_mt_last_raw >> 1);
    uint8_t rx   = (uint8_t)(f & 0x3Fu);
    uint8_t calc = mt6701_crc6(f >> 6);
    g_mt_shift[i] = (rx == calc) ? (uint32_t)(0x10000u | f) : 0u;  // pass flag + frame
  }
}

// SPI diagnostic buffer: readable over JTAG (no UART needed) while the driver
// self-test is being brought up on new hardware.
//   [0] IC_STAT  [1] CTRL1  [2] CTRL2  [3] CTRL5  [4] CTRL6  [5] CTRL10
// Each entry is the raw 16-bit bridge frame: high byte = STAT, low byte = data.
volatile uint32_t g_diag[8];
volatile uint32_t g_diag_done;

static void drv_dump_regs(void)
{
  drv_resp_t r;
  const uint8_t addr[6] = { DRV_REG_IC_STAT, DRV_REG_CTRL1, DRV_REG_CTRL2,
                            DRV_REG_CTRL5, DRV_REG_CTRL6, DRV_REG_CTRL10 };
  for (int i = 0; i < 6; ++i) {
    r = drv8316_read_reg(addr[i]);
    g_diag[i] = ((uint32_t)r.stat << 8) | (uint32_t)r.data;
  }
  g_diag_done = 1;
}

static int drv_selftest(void)
{
  drv_resp_t r2 = drv8316_read_reg(DRV_REG_CTRL2);
  drv_resp_t r6 = drv8316_read_reg(DRV_REG_CTRL6);
  printf("DRV8316: CTRL2=0x%02x (want 0x7c) CTRL6=0x%02x (want 0x11) STAT=0x%02x\n",
         r2.data, r6.data, r6.stat);
  if (r2.data != DRV_VAL_CTRL2 || r6.data != DRV_VAL_CTRL6) {
    printf("DRV8316 SPI readback FAIL (mode-1 bridge or wiring?)\n");
    return 0;
  }
  if (r6.stat & 0x20) { // IC_STAT bit5 = SPI_FLT
    printf("DRV8316 SPI_FLT set (frame length/parity?)\n");
    return 0;
  }
  return 1;
}

static int mt_selftest(void)
{
  mt6701_sample_t s;
  int ok = 0;
  for (int i = 0; i < 16; ++i) {
    ok += mt6701_read(&s);
  }
  printf("MT6701: CRC pass %d/16, angle=%u field=%u push=%u\n",
         ok, s.angle, s.field, s.push);
  return ok == 16;
}

// ---------------------------------------------------------------------------
// 串口控制台：触发转圈 / 调参。非阻塞轮询 UART0 接收 FIFO（printf 也走 UART0）。
// ---------------------------------------------------------------------------
static int console_getch(void)
{
  if (UART_IsRxFifoEmpty(UART0)) return -1;
  return (int)(UART_ReceiveData(UART0) & 0xFFu);
}

// 位置环增益档。上限被 MOTION_POWER_PCT_MAX 锁死后，能用的力矩非常小，
// kp 稍大就会在极小误差处打满限幅 -> bang-bang 极限环。旧档 {4..48} 全偏高。
// 经验值：err 约 400~800 raw（9~18 机械度）时才打满力矩，系统才线性。
static const float s_kp_gears[] = { 0.5f, 1.0f, 2.0f, 4.0f, 8.0f };
// 速度档（机械圈/秒）。调试期重点在慢速：越慢越容易看出是真同步还是打滑。
// 0.02 rev/s = 50 s 一圈，0.05 = 20 s 一圈。
static const float s_sp_gears[] = { 0.02f, 0.05f, 0.1f, 0.25f, 0.5f };
// 积分档（Q12/(raw*s)）。0 = 纯 PD（调试基线）。
static const float s_ki_gears[] = { 0.0f, 0.5f, 1.5f, 4.0f, 10.0f };
// 电子齿轮跟随带（raw）：指令最多超前转子多少。越小越"贴着转子走"、越不会
// bang-bang，但平均速度会低于设定值；太大就退回失步抖动。
// 阻尼档。速度估计在磁干扰下噪声极大，kd 偏大会把输出打飞（阻尼项已单独
// 限幅，但仍以小值起步）。
static const float s_kd_gears[] = { 0.0f, 0.01f, 0.02f, 0.06f, 0.2f };
static const float s_fl_gears[] = { 100.0f, 200.0f, 400.0f, 800.0f, 1600.0f };
// 换向角低通档：1.0 = 关（用原始编码器角度做换向，即修复前的行为）
static const float s_af_gears[] = { 1.0f, 1.0f / 16.0f, 1.0f / 64.0f,
                                    1.0f / 256.0f, 1.0f / 1024.0f };
// 混合换向滑差死区档（电角度）。越大越"像开环"（换向角更自由、更平顺、但
// 负载角可能吃到力矩）；越小越"像闭环"。15 度时 cos=0.966，只损失 3.4%。
static const float s_db_gears[] = { 3.0f, 8.0f, 15.0f, 25.0f, 40.0f };
// 速度估计窗口档（拍）。窗口越短，kd 看到的阻尼越及时，但量化噪声越大。
static const uint16_t s_vw_gears[] = { 32u, 64u, 128u, 256u, 512u };
static int s_db_gear = 2;      // 默认 15 电角度
static int s_vw_gear = 3;      // 默认 256 拍（与原来的 VEL_WIN 一致）
static int s_kp_gear = 2;
static int s_sp_gear = 1;      // 默认 0.05 rev/s（20 s 一圈）
static int s_ki_gear = 2;
static int s_fl_gear = 3;      // 默认 800 raw
static int s_kd_gear = 2;
static int s_af_gear = 2;      // 默认 1/64

static void console_help(void)
{
  printf("\n--- motion console ---\n");
  printf("r / R : closed-loop position servo, +1 / -1 turn\n");
  printf("o     : open-loop voltage-vector sweep (ignores the sensor)\n");
  printf("f     : read DRV8316 fault registers\n");
  printf("p / g : freeze PWM at 75/25/50pct (probe pins) / resume FOC\n");
  printf("?     : one-line status frame (for tools/foc_panel.py)\n");
  printf("m / xN / wN : manual phase force: on / mask 0-7 / strength 25-100pct\n");
  printf("s     : release torque (stop)\n");
  printf("+ / - : torque limit +-0.25V\n");
  printf("k     : kp gear (pos. gain)      v : speed gear\n");
  printf("i     : ki gear (integral)       c : follow-band gear\n");
  printf("j     : kd gear (damping)        d : dump motion config\n");
  printf("q     : 换向角低通档 (关/16/64/256/1024) —— 闭环抖动的主开关\n");
  printf("y     : 混合换向开关（换向角由指令前馈 + 编码器慢速滑差校正）\n");
  printf("e     : 混合换向滑差死区档（电角度）   u : 速度估计窗口档\n");
  printf("n / N : INL_ALL(PIN_28) 拉低 / 拉高 —— 烧录前按 'n' 释放 SWD\n");
}

static void console_dump_cfg(void)
{
  printf("cfg: kp=%d kd=%d/1000 ki=%d/10 kff=%d/1000 kfric=%d vq_max=%d (=%d.%03uV) "
         "speed=%d.%02u rev/s follow=%d err_limit=%d settle=%d timeout=%u\n",
         (int)g_motion_cfg.kp,
         (int)(g_motion_cfg.kd * 1000.0f),
         (int)(g_motion_cfg.ki * 10.0f),
         (int)(g_motion_cfg.kff * 1000.0f),
         (int)g_motion_cfg.kfric,
         (int)g_motion_cfg.vq_max,
         (int)(g_motion_cfg.vq_max / 4096),
         (unsigned)(((g_motion_cfg.vq_max % 4096) * 1000) / 4096),
         (int)g_motion_cfg.rev_per_s,
         (unsigned)(((int)(g_motion_cfg.rev_per_s * 100.0f)) % 100),
         (int)g_motion_cfg.err_follow,
         (int)g_motion_cfg.err_limit,
         (int)g_motion_cfg.settle_raw,
         (unsigned)g_motion_cfg.timeout_ms);
  printf("hybrid=%d slip_db=%d elec_deg corr=%d%% floor=%d/1000 rev/s | "
         "vel_win=%u ang_filt=%s%d\n",
         (int)motion_hybrid_enabled(),
         (int)g_motion_cfg.hyb_slip_deg,
         (int)(g_motion_cfg.hyb_corr_pct * 100.0f),
         (int)(g_motion_cfg.hyb_corr_floor * 1000.0f),
         (unsigned)motion_vel_window(),
         (g_foc.angle_filt_alpha >= 1.0f) ? "OFF" : "1/",
         (g_foc.angle_filt_alpha >= 1.0f)
           ? 0
           : (int)(1.0f / g_foc.angle_filt_alpha));
}

// ---------------------------------------------------------------------------
// 上位机协议（tools/foc_panel.py）
//   '?'  查询 -> 一行 "#FOC,ang=...,deg=...,ia=...,mode=..." 状态帧
//   'm'  进入手动强制三相模式      'g' 退出手动、交还 FOC
//   'xN' 手动三相掩码 N=0..7（bit0=A bit1=B bit2=C，1=高）
//   'wN' 驱动强度 N=1..4 -> 25/50/75/100 pct（压差 = VM * pct/100）
// 手动模式有 30 s 无操作自动释放，防止长时间直流通电烧电机。
// ---------------------------------------------------------------------------
static uint32_t s_drv_stat_cache;    // IC_STAT 缓存（每次查询都读 SPI 太吵）

static void print_status_frame(void)
{
  int16_t ia = 0, ib = 0, ic = 0;
  foc_last_currents(&ia, &ib, &ic);
  int32_t ang = foc_last_angle();
  uint32_t deg10 = (uint32_t)(((uint64_t)(uint32_t)ang * 3600u) / 16384u);
  int mode = motion_manual_active() ? 1 : 0;
  printf("#FOC,ang=%d,deg=%u.%u,crc=%u,ia=%d,ib=%d,ic=%d,mode=%d,mask=%u,pct=%d,"
         "drv=0x%02x,vq=%ld,iacc=%ld,err=%ld,vel=%ld,st=%d,hyb=%d,slip=%ld\n",
         (int)ang, (unsigned)(deg10 / 10u), (unsigned)(deg10 % 10u),
         (unsigned)foc_crc_errors(), (int)ia, (int)ib, (int)ic,
         mode, (unsigned)motion_manual_mask(), (int)motion_manual_pct(),
         (unsigned)(s_drv_stat_cache & 0xFFu), (long)motion_cmd_q12(),
         (long)motion_iacc_q12(),
         (long)motion_error_raw(), (long)motion_vel_rawps(),
         (int)motion_state(), (int)motion_hybrid_enabled(),
         (long)motion_slip_raw());
}

// 'x' / 'w' 是带一个参数的两字符命令；这里记住"等参数"的状态
static int s_arg_cmd;

static void console_cmd(int ch)
{
  if (s_arg_cmd) {
    int cmd = s_arg_cmd;
    s_arg_cmd = 0;
    if (cmd == 'x' && ch >= '0' && ch <= '7') {
      if (!motion_manual_active()) {
        printf("not in manual mode (press m first)\n");
      } else {
        motion_manual_set((uint8_t)(ch - '0'), -1);
        printf("manual mask=%u (A=%d B=%d C=%d) pct=%d\n",
               (unsigned)motion_manual_mask(),
               (motion_manual_mask() & 1) ? 1 : 0,
               (motion_manual_mask() & 2) ? 1 : 0,
               (motion_manual_mask() & 4) ? 1 : 0,
               (int)motion_manual_pct());
      }
    } else if (cmd == 'w' && ch >= '1' && ch <= '4') {
      int pct = (ch - '0') * 25;
      if (!motion_manual_active()) {
        printf("not in manual mode (press m first)\n");
      } else {
        motion_manual_set(0xFFu, pct);
        printf("manual pct=%d (phase diff = VM * %d/100)\n", pct, pct);
      }
    } else {
      printf("bad arg after '%c'\n", (char)cmd);
    }
    return;
  }
  switch (ch) {
    case 'x': case 'X':
      s_arg_cmd = 'x';          // 下一个字符是掩码 '0'..'7'
      break;
    case 'w': case 'W':
      s_arg_cmd = 'w';          // 下一个字符是强度 '1'..'4'
      break;
    case 'm': case 'M':
      motion_manual_start(motion_manual_mask(), motion_manual_pct());
      printf("manual ON: mask=%u (A=%d B=%d C=%d) pct=%d -- 'g' to release\n",
             (unsigned)motion_manual_mask(),
             (motion_manual_mask() & 1) ? 1 : 0,
             (motion_manual_mask() & 2) ? 1 : 0,
             (motion_manual_mask() & 4) ? 1 : 0,
             (int)motion_manual_pct());
      break;
    case 'g': case 'G':
      if (motion_manual_active()) {
        motion_manual_stop();
        printf("manual OFF: FOC has the outputs back\n");
      } else {
        INT_EnableIRQ(GPTIMER0_IRQn, 1);
        printf("FOC ISR re-enabled\n");
      }
      break;
    case '?':
      print_status_frame();
      break;
    case 'r': case 'R': {
      float turns = (ch == 'r') ? 1.0f : -1.0f;
      if (motion_start_turns(turns, g_motion_cfg.rev_per_s, g_motion_cfg.vq_max)) {
        printf("move start: %s1 turn @ %d.%02u rev/s, vq_max=%d\n",
               (turns < 0) ? "-" : "+",
               (int)g_motion_cfg.rev_per_s,
               (unsigned)(((int)(g_motion_cfg.rev_per_s * 100.0f)) % 100),
               (int)g_motion_cfg.vq_max);
      } else {
        printf("busy: a move is already running (press s first)\n");
      }
      break;
    }
    case 'o': {
      int32_t vq = g_motion_cfg.vq_max;
      if (vq > 4096) vq = 4096;      // 开环没有反馈兜底，电压减半起步
      // 慢速开环：走正好一圈，速度取当前档（'v' 可调，默认 0.05 rev/s = 20 s/圈）
      float rps = g_motion_cfg.rev_per_s;
      if (rps < 0.005f) rps = 0.005f;
      uint32_t ms = (uint32_t)(1000.0f / rps) + 500u;   // 一圈 + 收尾余量
      if (motion_openloop_start(rps, vq, ms)) {
        printf("open-loop: 1 turn at %d.%03u rev/s, vq=%d, %u ms\n",
               (int)rps, (unsigned)((int)(rps * 1000.0f) % 1000),
               (int)vq, (unsigned)ms);
      } else {
        printf("busy\n");
      }
      break;
    }
    case 't': case 'T': {
      // 诊断：绕过位置环，直接按恒定 q 轴电压 3 秒，看转子动不动
      int32_t vq = (ch == 't') ? g_motion_cfg.vq_max : -g_motion_cfg.vq_max;
      if (motion_torque_hold(vq, 3000u)) {
        printf("torque hold: vq=%d for 3000ms\n", (int)vq);
      } else {
        printf("busy\n");
      }
      break;
    }
    case 'f': case 'F': {
      // DRV8316 故障面：IC_STAT bit6=BK_FLT 5=SPI_FLT 4=OCP 3=NPOR(1=VM ok) 2=OVP 1=OT 0=FAULT
      drv_resp_t s0 = drv8316_read_reg(DRV_REG_IC_STAT);
      drv_resp_t s1 = drv8316_read_reg(DRV_REG_STAT1);
      drv_resp_t s2 = drv8316_read_reg(DRV_REG_STAT2);
      printf("DRV: IC_STAT=0x%02x STAT1=0x%02x STAT2=0x%02x (frame stat=0x%02x)\n",
             s0.data, s1.data, s2.data, s0.stat);
      break;
    }
    case 'p': case 'P': {
      // 静态占空比，方便用万用表确认 PWM 到底有没有出到引脚上：
      // PIN_7/8/9 对应约 2.48V / 0.83V / 1.65V（3V3 * duty）
      INT_EnableIRQ(GPTIMER0_IRQn, 0);
      motion_stop();
      pwm3ph_set(1874, 625, 1250);
      printf("static PWM: CCR0=1874 (75pct) CCR1=625 (25pct) CCR2=1250 (50pct)\n");
      printf("  expect PIN_7~2.48V  PIN_8~0.83V  PIN_9~1.65V; 'g' to resume FOC\n");
      break;
    }
    case 's': case 'S': case ' ':
      motion_stop();
      printf("released (torque_q=0)\n");
      break;
    case 'n': case 'N': {
      // 手动控制 INL_ALL(PIN_28)。'n' = 拉低（默认/空闲态）。
      //
      // ⚠ 这是**烧录逃生口**：PIN_28 是 JNTRST 焊盘，DAPLink 把 nTRST 恒驱动
      //   为低；固件把它驱动高就会与之顶牛，SWD 线上全是 JUNK，openocd 报
      //   `cannot read IDR` 再也连不上。烧录前按 'n' 把这条线让出来。
      int hi = (ch == 'N');
      if (hi) drv_inl_high(); else drv_inl_low();
      printf("INL_ALL(PIN_28) = %s%s\n", hi ? "HIGH" : "LOW",
             hi ? "  (SWD may be blocked until you press 'n')"
                : "  (SWD free - safe to flash)");
      break;
    }
    case '+': case '=': {
      // 比例步进（x1.25），上限锁在全局出力闸门（默认 5%），
      // 否则老式的 +1024 一步就冲过 5% 档位。
      int32_t hard = motion_vq_limit();
      int32_t v = g_motion_cfg.vq_max + (g_motion_cfg.vq_max / 4);
      if (v < g_motion_cfg.vq_max + 8) v = g_motion_cfg.vq_max + 8;
      if (v > hard) v = hard;
      g_motion_cfg.vq_max = v;
      printf("vq_max=%d (%d%% of %d)\n", (int)v,
             (int)(v * 100 / g_foc.v_limit_q), (int)g_foc.v_limit_q);
      break;
    }
    case '-': case '_': {
      int32_t v = g_motion_cfg.vq_max - (g_motion_cfg.vq_max / 4);
      if (v < 32) v = 32;
      g_motion_cfg.vq_max = v;
      printf("vq_max=%d (%d%% of %d)\n", (int)v,
             (int)(v * 100 / g_foc.v_limit_q), (int)g_foc.v_limit_q);
      break;
    }
    case 'k': case 'K':
      s_kp_gear = (s_kp_gear + 1) % 5;
      g_motion_cfg.kp = s_kp_gears[s_kp_gear];
      printf("kp=%d\n", (int)g_motion_cfg.kp);
      break;
    case 'v': case 'V':
      s_sp_gear = (s_sp_gear + 1) % 5;
      g_motion_cfg.rev_per_s = s_sp_gears[s_sp_gear];
      printf("speed=%d.%02u rev/s\n",
             (int)g_motion_cfg.rev_per_s,
             (unsigned)(((int)(g_motion_cfg.rev_per_s * 100.0f)) % 100));
      break;
    case 'j': case 'J':
      s_kd_gear = (s_kd_gear + 1) % 5;
      g_motion_cfg.kd = s_kd_gears[s_kd_gear];
      printf("kd=%d/1000\n", (int)(g_motion_cfg.kd * 1000.0f));
      break;
    case 'i': case 'I':
      s_ki_gear = (s_ki_gear + 1) % 5;
      g_motion_cfg.ki = s_ki_gears[s_ki_gear];
      printf("ki=%d/10\n", (int)(g_motion_cfg.ki * 10.0f));
      break;
    case 'c': case 'C':
      s_fl_gear = (s_fl_gear + 1) % 5;
      g_motion_cfg.err_follow = s_fl_gears[s_fl_gear];
      printf("follow band=%d raw (= %d.%u mech deg)\n",
             (int)g_motion_cfg.err_follow,
             (int)(g_motion_cfg.err_follow * 360 / 16384),
             (unsigned)(((int)(g_motion_cfg.err_follow * 3600 / 16384)) % 10));
      break;
    case 'q': case 'Q':
      // 换向角低通 A/B 开关：1.0 = 关（原始编码器），其余 = 一阶低通系数
      s_af_gear = (s_af_gear + 1) % 5;
      g_foc.angle_filt_alpha = s_af_gears[s_af_gear];
      printf("angle filter alpha=%s (lag ~%u us at 40kHz)\n",
             (g_foc.angle_filt_alpha >= 1.0f) ? "OFF" : "",
             (g_foc.angle_filt_alpha >= 1.0f)
               ? 0u
               : (unsigned)(1000000u / (uint32_t)(40000.0f * g_foc.angle_filt_alpha)));
      break;
    case 'e': case 'E':
      // 混合换向的滑差死区：换向角允许偏离真实转子角的电角度。
      // 这是"平顺 vs 力矩裕度"的旋钮 —— 死区越大越像开环（更平顺），
      // 但负载角吃掉的力矩越多（cos(deadband)）。
      s_db_gear = (s_db_gear + 1) % 5;
      g_motion_cfg.hyb_slip_deg = s_db_gears[s_db_gear];
      printf("hybrid slip deadband=%d elec deg (= %d mech raw)\n",
             (int)g_motion_cfg.hyb_slip_deg,
             (int)(g_motion_cfg.hyb_slip_deg * 16384.0f /
                   (360.0f * (float)g_foc.pole_pairs)));
      break;
    case 'u': case 'U':
      // 速度估计窗口：短 = 阻尼及时但噪声大；长 = 平滑但 kd 迟滞
      s_vw_gear = (s_vw_gear + 1) % 5;
      motion_set_vel_window(s_vw_gears[s_vw_gear]);
      printf("vel window=%u ticks (= %u us)\n",
             (unsigned)motion_vel_window(),
             (unsigned)(((uint32_t)motion_vel_window() * 1000000u) / s_isr_hz_g));
      break;
    case 'y': case 'Y':
      motion_hybrid_enable(!motion_hybrid_enabled());
      printf("hybrid commutation %s (%s)\n",
             motion_hybrid_enabled() ? "ON" : "OFF",
             motion_hybrid_enabled()
               ? "angle from command feed-forward + slow slip correction"
               : "angle straight from the encoder");
      break;
    case 'd': case 'D':
      console_dump_cfg();
      break;
    case 'h': case 'H':
      console_help();
      break;
    default:
      break;                        // 忽略换行等
  }
}

int main(void)
{
  board_init();          // clocks + UART0 printf
  STAGE(1);
  bringup_banner();
  app_io_init();
  STAGE(2);

  // --- DRV8316 power-up ---
  drv_wake();
  delay_ms(50);          // TPwrUp + tREADY
  printf("nSLEEP released\n");

  // --- PWM first (all outputs low) per datasheet order ---
  pwm3ph_init();
  STAGE(3);
  printf("PWM3ph ready: %u Hz, ARR=%u\n", (unsigned)PWM3PH_FREQ_HZ, (unsigned)PWM3PH_ARR);

  // --- driver configuration with auto-retry on bus glitch / lock state (D-1 fix) ---
  int drv_ready = 0;
  for (int retry = 0; retry < 3; ++retry) {
    drv8316_init();
    if (drv_selftest()) {
      drv_ready = 1;
      break;
    }
    printf("DRV8316 init retry %d...\n", retry + 1);
    drv8316_sleep_pulse_reset();
  }
  if (!drv_ready) {
    STAGE(4);
    printf("HALT: fix SPI before enabling power stage\n");
    drv_dump_regs();
    while (1) { }
  }
  STAGE(5);
  drv_dump_regs();
  // P0-3: INLx must stay LOW while CTRL2.PWM_MODE is written (Table 8-2) — that
  // write already happened in drv8316_init().
  //
  // ⚠ 这里**不再**拉高 INL（2026-10-15）：PIN_28 是 JNTRST 焊盘，DAPLink 把
  //   nTRST 恒驱动为低，固件拉高就与之顶牛，SWD 线上全是 JUNK，
  //   openocd 报 `cannot read IDR` 再也连不上。改为"只在运动期间拉高"
  //   （见 motion.c begin_common），空闲保持低 —— 冲突消失，随时可烧录。
  printf("INLx held low (idle); raised on demand when a move starts\n");

  // --- 烧录/调试逃生口：手动控制 INL，见串口 'n' / 'N' ---

  // --- encoder ---
  mt6701_init();
  if (!mt_selftest()) {
    STAGE(6);
    mt_capture_raw();
    printf("HALT: SSI CRC failing (check MODE pin = VDD, wiring, fallback B)\n");
    while (1) { }
  }
  STAGE(7);

  // --- current sense zero cal (motor unpowered) ---
  current_init();
  STAGE(8);
  printf("Izero: A=%d B=%d C=%d\n", g_cur_cal.off_a, g_cur_cal.off_b, g_cur_cal.off_c);

  // --- FOC loop & alignment ---
  foc_init(POLE_PAIRS);
  STAGE(9);
  printf("Aligning rotor to d-axis...\n");
  foc_align_sensor();
  STAGE(10);
  // NOTE: the SDK printf does not implement the '+' flag, so print the sign
  // explicitly. "%+d" would be emitted literally.
  printf("Zero angle offset: %d/1000 rad, sensor direction: %s%d\n",
         (int)(g_foc.zero_electric_angle * 1000.0f),
         (g_foc.sensor_direction < 0) ? "-" : "+",
         (int)((g_foc.sensor_direction < 0) ? -g_foc.sensor_direction
                                            : g_foc.sensor_direction));
  // 方向探测的原始角度差：+1571 = +90 度(正向)，+4712 = 270 度(反向)。
  printf("dir probe delta=%d/1000 rad (1571=+90deg, 4712=-90deg)\n",
         (int)(g_align_delta * 1000.0f));

  pwm3ph_on_update(foc_isr);
  pwm3ph_outputs(1);
  STAGE(11);
  printf("FOC loop running\n");

  // 实测 PWM 更新中断频率（斜坡增量与 ISR 内计时都按它换算）
  //
  // 用两个独立时基交叉校验：UTIL_IdleMs（走 UTIL_IdleUs / UTIL_McycleToUs）和
  // mcycle 直接计时。开环实测机械转速恒为指令值的 0.497 倍（0.25/0.05/0.5 rev/s
  // 三档皆然），这种与速度无关的固定 2 倍只可能来自时基换算，而不是打滑 ——
  // 若任一时基偏慢 2 倍，isr_hz 就会被高估一倍，斜坡/开环推进全都慢一半。
  uint32_t c0 = s_isr_count;
  uint64_t m0 = UTIL_GetMcycle();
  UTIL_IdleMs(200);
  uint64_t m1 = UTIL_GetMcycle();
  uint32_t dcount = s_isr_count - c0;
  uint32_t dt_us_mc = (uint32_t)((m1 - m0) / 200u);          // mcycle -> us @200MHz
  uint32_t isr_hz_ms = dcount * 5u;                          // 200ms 窗口 -> Hz
  uint32_t isr_hz_mc = (dt_us_mc > 0)
                     ? (uint32_t)(((uint64_t)dcount * 1000000u) / dt_us_mc) : 0u;
  uint32_t isr_hz = isr_hz_mc;                               // 以 mcycle 时基为准
  s_isr_hz_g = isr_hz;
  motion_init();
  motion_set_isr_rate(isr_hz);
  printf("ISR rate: IdleMs=%u Hz, mcycle=%u Hz (dt=%u us, cnt=%u)\n",
         (unsigned)isr_hz_ms, (unsigned)isr_hz_mc,
         (unsigned)dt_us_mc, (unsigned)dcount);
  console_help();
  console_dump_cfg();

  uint32_t up_ms = 0;
  uint32_t print_acc = 0;
  uint32_t isr_base = s_isr_count;
  uint32_t drv_next_ms = 1000u;
  int autorun_fired = 0;
  motion_state_t last_state = motion_state();

  for (;;) {
    UTIL_IdleUs(100000);              // 100ms 轮询：串口响应要快
    up_ms   += 100;
    print_acc += 100;

    int ch = console_getch();
    if (ch >= 0) {
      console_cmd(ch);
    }

#if MOTION_AUTORUN
    // 上电先给 3 秒（倒计时内按 s 可取消），然后自动尝试转一圈
    if (!autorun_fired && up_ms >= 3000u) {
      autorun_fired = 1;
      printf("auto: turning +1 turn now\n");
      motion_start_turns(1.0f, g_motion_cfg.rev_per_s, g_motion_cfg.vq_max);
    }
    if (!autorun_fired && (up_ms % 1000u) == 0u) {
      printf("auto-run in %u s (press s to cancel)\n", (unsigned)((3000u - up_ms) / 1000u));
    }
#else
    // 开机不转：力矩保持为 0，电机可自由转动；等待串口 'r'/'R' 手动触发。
    if (!autorun_fired) {
      autorun_fired = 1;
      printf("auto-run OFF: holding torque 0, press 'r' to turn +1 rev\n");
    }
#endif

    if (motion_manual_timed_out()) {
      printf("manual mode auto-released (30 s idle) -- outputs back to FOC\n");
    }

    if (up_ms >= drv_next_ms) {          // 每秒刷一次故障面供上位机显示
      drv_next_ms = up_ms + 1000u;
      s_drv_stat_cache = (uint32_t)drv8316_read_reg(DRV_REG_IC_STAT).data;
    }

    motion_state_t st = motion_state();
    if (st != last_state) {
      int32_t tr = motion_travelled_raw();
      uint32_t mag = (uint32_t)((tr < 0) ? -tr : tr);
      if (st == MOTION_HOLD) {
        int32_t resid = motion_final_err_raw();
        uint32_t rmag = (uint32_t)((resid < 0) ? -resid : resid);
        printf("MOVE DONE: travelled %s%ld raw (%u/1000 turn) in %u ms, "
               "residual %s%u raw\n",
               (tr < 0) ? "-" : "+", (long)mag,
               (unsigned)(mag * 1000u / 16384u), (unsigned)motion_elapsed_ms(),
               (resid < 0) ? "-" : "+", (unsigned)rmag);
        // 抖动指标：真实速度 = rev_per_s * 16384 raw/s，测出来的 |vm| 越接近
        // 它就越平顺。开环基线约几百，闭环修好前是两三万。
        printf("  jitter: |vm| mean=%ld peak=%ld raw/s (ideal %ld raw/s)\n",
               (long)motion_vib_mean(), (long)motion_vib_peak(),
               (long)(g_motion_cfg.rev_per_s * 16384.0f));
        if (motion_settled_stuck()) {
          // 不是故障：力矩已打满但静摩擦顶住了。如实报告残差，别假装到位。
          printf("  NOTE: stopped against static friction (10%% torque cap), "
                 "residual was %ld raw (%ld.%lu mech deg)\n",
                 (long)resid,
                 (long)(resid * 360 / 16384),
                 (unsigned long)(((resid < 0 ? -resid : resid)
                                  * 3600 / 16384) % 10));
        }
      } else if (st == MOTION_FAULT) {
        printf("MOVE ABORT: %s (err=%ld raw, vel=%ld raw/s, vq=%ld, t=%u ms)\n",
               motion_fault_msg(), (long)motion_error_raw(),
               (long)motion_vel_rawps(), (long)motion_cmd_q12(),
               (unsigned)motion_elapsed_ms());
        motion_stop();               // 回到 IDLE，等下一条命令
      }
      last_state = motion_state();
    }

    if (print_acc >= 250u) {
      print_acc = 0;
      uint32_t now = s_isr_count;
      printf("isr=%u ang=%d crc=%u j=%u/%u | st=%d err=%ld vm=%ld vel=%ld vq=%ld i=%ld"
             " t=%u hyb=%d sl=%ld rx=%d\n",
             (unsigned)(now - isr_base), (int)foc_last_angle(),
             (unsigned)foc_crc_errors(),
             (unsigned)motion_jump_hi(), (unsigned)motion_jump_lo(),
             (int)st, (long)motion_error_raw(),
             (long)motion_vel_meas_rawps(), (long)motion_vel_rawps(),
             (long)motion_cmd_q12(), (long)motion_iacc_q12(),
             (unsigned)motion_elapsed_ms(),
             (int)motion_hybrid_enabled(), (long)motion_slip_raw(),
             (int)motion_hold_relaxed());
      isr_base = now;
    }
  }
}
