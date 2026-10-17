// UART command parser and telemetry. No interrupt masking across printf.
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <math.h>
#include "board.h"
#include "uart.h"
#include "drv8316.h"
#include "foc.h"
#include "motion.h"
#include "control.h"
#include "console.h"
#include "current.h"
#include "pwm3ph.h"
#include "calibration.h"
#include "build_config.h"
#include "haptic.h"
#include "gptimer.h"
extern volatile uint32_t g_stage;
static uint32_t s_now_ms;
static uint32_t s_isr_hz_g = 20000u;
static int s_cancel_autorun;
static int console_getch(void)
{
  if (UART_IsRxFifoEmpty(UART0)) return -1;
  return (int)(UART_ReceiveData(UART0) & 0xFFu);
}

static const float s_kp_gears[] = { 0.5f, 1.0f, 2.0f, 4.0f, 8.0f };
static const float s_sp_gears[] = { 0.02f, 0.05f, 0.1f, 0.25f, 0.5f };
static const float s_ki_gears[] = { 0.0f, 0.5f, 1.5f, 4.0f, 10.0f };
static const float s_kd_gears[] = { 0.0f, 0.01f, 0.02f, 0.06f, 0.2f };
static const float s_fl_gears[] = { 100.0f, 200.0f, 500.0f, 800.0f, 1600.0f };
static const float s_af_gears[] = { 1.0f, 1.0f / 16.0f, 1.0f / 64.0f,
                                    1.0f / 256.0f, 1.0f / 1024.0f };
static const float s_db_gears[] = { 3.0f, 8.0f, 15.0f, 25.0f, 40.0f };
static const uint16_t s_vw_gears[] = { 32u, 64u, 128u, 256u, 512u };
static const float s_ckp_gears[] = { 2.0f, 4.0f, 8.0f, 16.0f, 32.0f };
static const float s_cki_gears[] = { 0.0f, 25.0f, 50.0f, 100.0f, 200.0f };
static int s_db_gear = 2;      // 默认 15 电角度
static int s_vw_gear = 3;      // 默认 256 拍（与原来的 VEL_WIN 一致）
static int s_kp_gear = 2;
static int s_sp_gear = 1;      // 默认 0.05 rev/s（20 s 一圈）
static int s_ki_gear = 2;
static int s_fl_gear = 2;      // 默认 500 raw
static int s_kd_gear = 2;
static int s_af_gear = 2;      // 默认 1/64
static int s_ckp_gear = 2;     // 电流环 kp 默认 8
static int s_cki_gear = 3;     // 电流环 ki 默认 100
static int s_spin_openloop;    // #0 closed-loop / #1 open-loop
static int s_tel_hz;
static uint32_t s_tel_next_ms;
#define ROT_SPEED_MAX_RPS 0.05f
#define ROT_VQ_MAX 512

static void console_help(void)
{
  printf("\n--- motion console ---\n");
  printf("r / R : closed-loop position servo, +1 / -1 turn\n");
  printf("o / O : +/-1-turn open-loop vector sweep; b / B : +/-5 turns\n");
  printf("f     : read DRV8316 fault registers; F : over-current capture readout+clear\n");
  printf("g / n : release all outputs (same as s)\n");
  printf("?     : one-line status frame (for tools/foc_panel.py)\n");
  printf("m / xN / wN : manual phase force: on / mask 0-7 / strength 5/10/15/20pct\n");
  printf("m0-m4 : free / damping / inertia / SmartKnob detent / hard soft-wall modes\n");
  printf("df fi kp kd kf vl dw ds es sp sb pn px br : haptic parameters\n");
  printf("cd : set haptic center at current angle; rot <deg> : relative move (safe 0.05 rev/s, vq<=512)\n");
  printf("tel <0/10/20/50/100> : compact $T telemetry (0=off)\n");
  printf("p / P : endless SPIN forward / reverse; s ramps down and releases\n");
  printf("#0/#1 : SPIN closed-loop / open-loop mode (set before p/P; 'l' controls current loop)\n");
  printf("V1-4  : SPIN speed 0.05/0.10/0.25/1.00 rev/s  W1-8 : SPIN force 10-80%%\n");
  printf("rpm <3-60> : set SPIN speed continuously (rpm); estop : immediate release\n");
  printf("vp vi vff vfr : closed-loop SPIN velocity PI / feed-forward / friction\n");
  printf("s     : release torque (stop)\n");
  printf("+ / - : modulation limit x1.25 / x0.75 (capped)\n");
  printf("k     : kp gear (pos. gain)      v : speed gear\n");
  printf("i     : ki gear (integral)       c : follow-band gear\n");
  printf("j     : kd gear (damping)        d : dump motion config\n");
  printf("q     : 换向角低通档 (关/16/64/256/1024) —— 闭环抖动的主开关\n");
  printf("y     : 混合换向开关（换向角由指令前馈 + 编码器慢速滑差校正）\n");
  printf("e     : 混合换向滑差死区档（电角度）   u : 速度估计窗口档\n");
  printf("l     : 电流环开关（关=电压模式；待机且输出关闭时切换）\n");
  printf("K / I : 电流环 kp / ki 档（mod LSB per 电流 LSB）\n");
  printf("z : checked fault recovery to idle (no automatic movement)\n");
  printf("a / A : start / cancel slow motor calibration (outputs stay off at boot)\n");
}

static void console_dump_cfg(void)
{
  printf("cfg: kp=%d kd=%d/1000 ki=%d/10 kff=%d/1000 kfric=%d vq_max=%d (ref=%d.%03u) "
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
  printf("curloop=%d kp=%d ki=%d ref_div=%d filt=%s%d cap=%d trip=%d (mod LSB)\n",
         (int)foc_current_loop_enabled(), (int)g_foc.cur_kp, (int)g_foc.cur_ki,
         (int)g_foc.cur_ref_div,
         (g_foc.cur_filt_alpha >= 1.0f) ? "OFF" : "1/",
         (g_foc.cur_filt_alpha >= 1.0f) ? 0 : (int)(1.0f / g_foc.cur_filt_alpha),
         (int)g_foc.cur_v_cap, (int)g_foc.cur_trip_lsb);
  printf("spinvel: vp=%d/1000 vi=%d/1000 vff=%d/1000 vfr=%d (Q12 per raw/s)\n",
         (int)(motion_spin_vel_kp() * 1000.0f + 0.5f),
         (int)(motion_spin_vel_ki() * 1000.0f + 0.5f),
         (int)(motion_spin_vel_ff() * 1000.0f + 0.5f),
         (int)motion_spin_vel_friction());
  printf("haptic: mode=%d(%s) limit=%d%% df=%d/1000 fi=%d/1000 kp=%d/100 kd=%d/1000 kf=%d/1000\n",
         g_haptic_cfg.mode, haptic_mode_name(g_haptic_cfg.mode), (int)g_haptic_cfg.limit_pct,
         (int)(g_haptic_cfg.k_damp * 1000.0f), (int)(g_haptic_cfg.k_inertia * 1000.0f),
         (int)(g_haptic_cfg.kp * 100.0f), (int)(g_haptic_cfg.kd * 1000.0f),
         (int)(g_haptic_cfg.k_free * 1000.0f));
  printf("haptic geom: dw=%d/100 deg ds=%d/100 es=%d/100 sp=%d/100 sb=%d/100 pn=%ld px=%ld br=%d/100 deg\n",
         (int)(g_haptic_cfg.det_width_rad * 18000.0f / 3.14159265359f),
         (int)(g_haptic_cfg.det_strength * 100.0f),
         (int)(g_haptic_cfg.end_strength * 100.0f),
         (int)(g_haptic_cfg.snap_point * 100.0f),
         (int)(g_haptic_cfg.snap_bias * 100.0f),
         (long)g_haptic_cfg.pos_min, (long)g_haptic_cfg.pos_max,
         (int)(g_haptic_cfg.bound_rad * 18000.0f / 3.14159265359f));
}

// SPIN is the only feature allowed above the global motion-power ceiling.
// Apply the empirically smooth 3-15 rpm configuration explicitly so a stale
// interactive tuning session cannot silently leak into an unattended run.
static void console_spin_preset(void)
{
  s_kp_gear = 4;      g_motion_cfg.kp = s_kp_gears[s_kp_gear];
  s_kd_gear = 3;      g_motion_cfg.kd = s_kd_gears[s_kd_gear];
  s_ki_gear = 2;      g_motion_cfg.ki = s_ki_gears[s_ki_gear];
  s_fl_gear = 2;      g_motion_cfg.err_follow = s_fl_gears[s_fl_gear];
  // 60 rpm needs less angle-filter lag: 1/256 at 3-15 rpm was best, while
  // 1/64 removes the 7 Hz electrical ripple at 60 rpm.
  s_af_gear = (motion_spin_rps() >= 0.5f) ? 2 : 3;
  g_foc.angle_filt_alpha = s_af_gears[s_af_gear];
  s_vw_gear = 3;      motion_set_vel_window(s_vw_gears[s_vw_gear]);
  s_ckp_gear = 2;     g_foc.cur_kp = s_ckp_gears[s_ckp_gear];
  s_cki_gear = 3;     g_foc.cur_ki = s_cki_gears[s_cki_gear];
  g_motion_cfg.err_limit = 2048.0f;
  g_motion_cfg.settle_raw = 200;
  motion_hybrid_enable(0);
  if (s_spin_openloop) {
    if (foc_current_loop_enabled()) foc_current_loop_enable(0);
  }
  printf("SPIN preset: mode=%s hyb=0 kp=8 kd=60/1000 filt=%s%d loop=%s velpi=%s\n",
         s_spin_openloop ? "open" : "closed",
         (g_foc.angle_filt_alpha >= 1.0f) ? "OFF" : "1/",
         (g_foc.angle_filt_alpha >= 1.0f) ? 0 : (int)(1.0f / g_foc.angle_filt_alpha),
         foc_current_loop_enabled() ? "ON" : "OFF",
         s_spin_openloop ? "n/a" : "ON");
}



static void print_status_frame(void)
{
  int16_t ia = 0, ib = 0, ic = 0;
  foc_last_currents(&ia, &ib, &ic);
  int32_t ang = foc_last_angle();
  uint32_t deg10 = (uint32_t)(((uint64_t)(uint32_t)ang * 3600u) / 16384u);
  int mode = motion_haptic_active() ? 3 : motion_manual_active() ? 1 : motion_spin_active() ? 2 : 0;
  int pct = (mode == 3) ? (int)g_haptic_cfg.limit_pct :
            (mode == 2) ? (int)motion_spin_pct() : (int)motion_manual_pct();
  int16_t id16 = 0, iq16 = 0;
  foc_last_dq(&id16, &iq16);
  foc_oc_t oc;
  foc_oc_get(&oc);
  printf("#FOC,proto=3,ang=%d,deg=%u.%u,crc=%u,ia=%d,ib=%d,ic=%d,mode=%d,mask=%u,pct=%d,"
         "drv=0x%02x,vq=%ld,iacc=%ld,err=%ld,vel=%ld,st=%d,hyb=%d,slip=%ld,"
         "diag=1,fw=20261017.27,up=%u,hz=%u,stage=%u,calst=%d,calpk=%u,calok=%d,ready=%d,aligned=%d,"
         "drvok=%d,encok=%d,mg=%u,adcok=%d,cal=%d,adce=%u,brk=%d,out=%d,"
         "cl=%d,open=%d,vsp=%ld,vfb=%ld,verr=%ld,vkp=%d,vki=%d,vff=%d,vfr=%d,"
         "id=%d,iq=%d,iref=%ld,ipa=%d,ipb=%d,ipc=%d,ocn=%u,ocmx=%u,ocg=%u,"
         "hm=%d,hact=%d,hpos=%ld,hsub=%ld,htgt=%ld,hto=%d,fault=%s\n",
         (int)ang, (unsigned)(deg10 / 10u), (unsigned)(deg10 % 10u),
         (unsigned)foc_crc_errors(), (int)ia, (int)ib, (int)ic,
         mode, (unsigned)motion_manual_mask(), pct,
         (unsigned)(control_driver_status() & 0xFFu), (long)motion_cmd_q12(),
         (long)motion_iacc_q12(),
         (long)motion_error_raw(), (long)motion_vel_rawps(),
         (int)motion_state(), (int)motion_hybrid_enabled(),
         (long)motion_slip_raw(),
         (unsigned)s_now_ms, (unsigned)s_isr_hz_g, (unsigned)g_stage,
         calibration_stage(), (unsigned)calibration_peak(), control_calibration_ready(),
         control_ready(), control_is_aligned(), control_driver_ready(),
         foc_angle_valid(), (unsigned)foc_sensor_status(), foc_current_valid(),
         current_calibrated(), (unsigned)foc_adc_errors(), pwm3ph_faulted(),
         pwm3ph_enabled(),
         foc_current_loop_enabled(), s_spin_openloop,
         (long)motion_spin_target_vel_rawps(), (long)motion_spin_feedback_rawps(),
         (long)motion_spin_vel_error_rawps(),
         (int)(motion_spin_vel_kp() * 1000.0f + 0.5f),
         (int)(motion_spin_vel_ki() * 1000.0f + 0.5f),
         (int)(motion_spin_vel_ff() * 1000.0f + 0.5f),
         (int)motion_spin_vel_friction(),
         (int)id16, (int)iq16, (long)foc_last_iq_ref(),
         (int)oc.pk_a, (int)oc.pk_b, (int)oc.pk_c,
         (unsigned)oc.events, (unsigned)oc.max_run, (unsigned)oc.glitches,
         g_haptic_cfg.mode, motion_haptic_active(),
         (long)motion_haptic_position(),
         (long)(motion_haptic_subpos() * 100.0f),
         (long)(motion_haptic_target_rad() * 18000.0f / 3.14159265359f),
         motion_haptic_timeout_pending(),
         motion_fault_msg());
}

static int s_arg_cmd;
static uint32_t s_arg_since;

void console_feed(int ch)
{
  if (ch == 's' || ch == 'S' || ch == ' ' || ch == 'n' || ch == 'g' || ch == 'G') {
    s_arg_cmd = 0;
    s_cancel_autorun = 1;
    calibration_cancel();
    if (motion_spin_active()) {
      motion_spin_stop();
      printf("SPIN stopping: bounded deceleration, then output release\n");
      return;
    }
    motion_stop();
    printf("released; state=%d (z requests checked fault recovery)\n", motion_state());
    return;
  }
  if (ch == 'A') {
    calibration_cancel();
    printf("calibration cancel requested; stage=%d\n", calibration_stage());
    return;
  }
  if (s_arg_cmd) {
    int cmd = s_arg_cmd;
    s_arg_cmd = 0;
    if (cmd == '#') {
      if (motion_state() == MOTION_RUN) {
        printf("SPIN mode: stop the current rotation first\n");
      } else if (ch == '0' || ch == '1') {
        s_spin_openloop = (ch == '1');
        printf("SPIN mode=%s (current loop %s; use l to change)\n",
               s_spin_openloop ? "OPEN: voltage/fixed vector"
                               : "CLOSED: velocity PI + synchronous feed-forward",
               foc_current_loop_enabled() ? "ON" : "OFF");
      } else {
        printf("bad arg after '#' (use 0=closed, 1=open)\n");
      }
    } else if (cmd == 'x' && ch >= '0' && ch <= '7') {
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
      int pct = (ch - '0') * MOTION_POWER_PCT_MAX / 4;
      if (!motion_manual_active()) {
        printf("not in manual mode (press m first)\n");
      } else {
        motion_manual_set(0xFFu, pct);
        printf("manual pct requested=%d (cap=%d)\n", pct, MOTION_POWER_PCT_MAX);
      }
    } else if (cmd == 'V' && ch >= '1' && ch <= '4') {
      static const float rps[4] = { 0.05f, 0.10f, 0.25f, 1.00f };
      float v = rps[ch - '1'];
      motion_spin_set_speed(v);
      printf("SPIN speed=%d.%02u rev/s (%d rpm)\n",
             (int)v, (unsigned)(((int)(v * 100.0f)) % 100),
             (int)(v * 60.0f + 0.5f));
    } else if (cmd == 'W' && ch >= '1' && ch <= '8') {
      int pct = (ch - '0') * 10;
      int cap = motion_spin_power_cap();
      if (pct > cap) pct = cap;
      motion_spin_set_power(pct);
      printf("SPIN force=%d%% (mode cap %d%%)\n", pct,
             cap);
    } else {
      printf("bad arg after '%c'\n", (char)cmd);
    }
    return;
  }
  switch (ch) {
    case 'a':
      if (calibration_start())
        printf("calibration started: slow %d%% electrical sweep; press A or s to cancel\n", CALIBRATION_PCT);
      else
        printf("calibration refused: check status/driver/encoder/ADC and keep outputs off\n");
      break;
    case '#':
      s_arg_cmd = '#';          // 下一个字符：0=闭环，1=开环
      break;
    case 'x': case 'X':
      s_arg_cmd = 'x';          // 下一个字符是掩码 '0'..'7'
      break;
    case 'w':
      s_arg_cmd = 'w';          // 下一个字符是强度 '1'..'4'
      break;
    case 'W':
      s_arg_cmd = 'W';          // SPIN 力度 '1'..'8' = 10%..80%
      break;
    case 'm': case 'M':
      motion_manual_start(0, motion_manual_pct()); // neutral until an explicit xN
      if (!motion_manual_active()) { printf("manual refused: fault latched\n"); break; }
      printf("manual ON: mask=%u (A=%d B=%d C=%d) pct=%d -- 'g' to release\n",
             (unsigned)motion_manual_mask(),
             (motion_manual_mask() & 1) ? 1 : 0,
             (motion_manual_mask() & 2) ? 1 : 0,
             (motion_manual_mask() & 4) ? 1 : 0,
             (int)motion_manual_pct());
      break;
    case 'p': case 'P': {
      if (motion_spin_active()) {
        printf("SPIN already active; press s before changing direction\n");
        break;
      }
      if (motion_state() == MOTION_RUN) { printf("busy: stop the current move first\n"); break; }
      if (motion_state() == MOTION_FAULT) { printf("fault latched; use z for checked recovery\n"); break; }
      if (calibration_active()) { printf("busy: calibration is active\n"); break; }
      if (!control_ready()) { printf("SPIN refused: calibration/driver/encoder/ADC not ready\n"); break; }
      console_spin_preset();
      int dir = (ch == 'P') ? -1 : 1;
      if (motion_spin_start_mode(dir, motion_spin_rps(), (int)motion_spin_pct(),
                                 s_spin_openloop)) {
        printf("SPIN start: %s %s %.2f rev/s (%d rpm), force cap=%ld%%\n",
               s_spin_openloop ? "open-loop" : "closed-loop",
               dir < 0 ? "reverse" : "forward", motion_spin_rps(),
               (int)(motion_spin_rps() * 60.0f + 0.5f),
               (long)motion_spin_pct());
        printf("host watchdog: 1 s without commands -> ramp stop; 's' stops now\n");
      } else {
        printf("SPIN start refused (state=%d)\n", motion_state());
      }
      break;
    }
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
        printf(motion_state() == MOTION_FAULT
                 ? "fault latched; use z for checked recovery\n"
                 : "busy: a move is already running (press s first)\n");
      }
      break;
    }
    case 'o': case 'O': case 'b': case 'B': {
      int32_t vq = g_motion_cfg.vq_max;
      if (vq > 4096) vq = 4096;      // 开环没有反馈兜底，电压减半起步
      float rps = g_motion_cfg.rev_per_s;
      if (rps < 0.005f) rps = 0.005f;
      int turns = (ch == 'b' || ch == 'B') ? 5 : 1;
      uint32_t ms = (uint32_t)(turns * 1000.0f / rps);
      if (ch == 'O' || ch == 'B') rps = -rps;
      if (motion_openloop_start(rps, vq, ms)) {
        printf("open-loop vector sweep: rps=%d/1000, vq=%d, %u ms\n",
               (int)(rps * 1000.0f),
               (int)vq, (unsigned)ms);
      } else {
        printf("busy\n");
      }
      break;
    }
    case 't': case 'T': {
      int32_t vq = (ch == 't') ? g_motion_cfg.vq_max : -g_motion_cfg.vq_max;
      if (motion_torque_hold(vq, 3000u)) {
        printf("torque hold: vq=%d for 3000ms\n", (int)vq);
      } else {
        printf("busy\n");
      }
      break;
    }
    case 'f': {
#if !FOC_CPLD_BRINGUP
      printf("fault read refused: FOC_CPLD_BRINGUP=0 (logic image not trusted)\n");
#else
      drv_resp_t s0 = drv8316_read_reg(DRV_REG_IC_STAT);
      drv_resp_t s1 = drv8316_read_reg(DRV_REG_STAT1);
      drv_resp_t s2 = drv8316_read_reg(DRV_REG_STAT2);
      drv_resp_t c1 = drv8316_read_reg(DRV_REG_CTRL1);
      drv_resp_t c2 = drv8316_read_reg(DRV_REG_CTRL2);
      drv_resp_t c5 = drv8316_read_reg(DRV_REG_CTRL5);
      drv_resp_t c6 = drv8316_read_reg(DRV_REG_CTRL6);
      drv_resp_t c10 = drv8316_read_reg(DRV_REG_CTRL10);
      printf("DRV: IC_STAT=0x%02x STAT1=0x%02x STAT2=0x%02x (frame stat=0x%02x)\n",
             s0.data, s1.data, s2.data, s0.stat);
      printf("DRV config: CTRL1=0x%02x CTRL2=0x%02x CTRL5=0x%02x CTRL6=0x%02x CTRL10=0x%02x\n",
             c1.data, c2.data, c5.data, c6.data, c10.data);
      printf("release diag: SR=%08x/%08x/%08x GPIO4=%02x/%02x BDTR=%08x nowSR=%08x nowGPIO4=%02x\n",
             (unsigned)g_pwm_release_diag[0], (unsigned)g_pwm_release_diag[1], (unsigned)g_pwm_release_diag[2],
             (unsigned)g_pwm_release_diag[3], (unsigned)g_pwm_release_diag[4], (unsigned)g_pwm_release_diag[5],
             (unsigned)GPTIMER0->SR, (unsigned)GPIO_GetValue(GPIO4, 0xff));
#endif
      break;
    }
    case 'F': {
      foc_oc_t oc;
      foc_oc_get(&oc);
      printf("OC: pkA=%d pkB=%d pkC=%d lsb over=%u maxrun=%u glitch=%u last=%d/%d/%d\n",
             (int)oc.pk_a, (int)oc.pk_b, (int)oc.pk_c,
             (unsigned)oc.events, (unsigned)oc.max_run, (unsigned)oc.glitches,
             (int)oc.last_a, (int)oc.last_b, (int)oc.last_c);
      if (oc.snap_kind) {
        printf("OC snap: kind=%s run=%u mask=%u (thr=%d lsb):\n",
               (oc.snap_kind == 2u) ? "trip" : "glitch",
               (unsigned)oc.snap_run, (unsigned)oc.snap_mask,
               (int)g_foc.cur_trip_lsb);
        for (int i = 0; i < oc.snap_n; ++i)
          printf("  %d: %d %d %d\n", i, (int)oc.snap[i][0],
                 (int)oc.snap[i][1], (int)oc.snap[i][2]);
      }
      foc_oc_reset();
      printf("OC capture reset\n");
      break;
    }
    case '!':
#if FOC_CPLD_BRINGUP
      if (motion_state() == MOTION_IDLE && !calibration_active() && !pwm3ph_enabled() &&
          !pwm3ph_faulted() && !(GPIO_GetValue(GPIO2, DRV_INL_BIT))) {
        // INL stays LOW throughout: exercise timer MOE with driver Hi-Z.
        pwm3ph_prepare();
        pwm3ph_outputs(1);
        delay_us(30);
        pwm3ph_release();
        delay_us(30);
        printf("MOE-only cycle: INL=%u BRK=%d SR=%08x/%08x/%08x\n",
               (unsigned)GPIO_GetValue(GPIO2, DRV_INL_BIT), pwm3ph_faulted(),
               (unsigned)g_pwm_release_diag[0], (unsigned)g_pwm_release_diag[1], (unsigned)g_pwm_release_diag[2]);
      } else printf("MOE-only diagnostic refused\n");
#endif
      break;
    case 'z': case 'Z':
#if !FOC_CPLD_BRINGUP
      printf("recovery refused: FOC_CPLD_BRINGUP=0; verify logic then rebuild bring-up image\n");
#else
      printf(control_recover() ? "recovered: idle, outputs off\n"
                              : "recovery refused: check f/status; startup calibration failures need reboot\n");
#endif
      break;
    case 'N':
      printf("raw power bypass removed; use bounded manual mode m/xN/wN\n");
      break;
    case '+': case '=': {
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
    case 'k':
      s_kp_gear = (s_kp_gear + 1) % 5;
      g_motion_cfg.kp = s_kp_gears[s_kp_gear];
      printf("kp=%d\n", (int)g_motion_cfg.kp);
      break;
    case 'K':
      s_ckp_gear = (s_ckp_gear + 1) % 5;
      g_foc.cur_kp = s_ckp_gears[s_ckp_gear];
      printf("cur kp=%d (mod LSB per current LSB)\n", (int)g_foc.cur_kp);
      break;
    case 'v':
      s_sp_gear = (s_sp_gear + 1) % 5;
      g_motion_cfg.rev_per_s = s_sp_gears[s_sp_gear];
      printf("speed=%d.%02u rev/s\n",
             (int)g_motion_cfg.rev_per_s,
             (unsigned)(((int)(g_motion_cfg.rev_per_s * 100.0f)) % 100));
      break;
    case 'V':
      s_arg_cmd = 'V';          // SPIN 速度 '1'..'3'
      break;
    case 'j': case 'J':
      s_kd_gear = (s_kd_gear + 1) % 5;
      g_motion_cfg.kd = s_kd_gears[s_kd_gear];
      printf("kd=%d/1000\n", (int)(g_motion_cfg.kd * 1000.0f));
      break;
    case 'i':
      s_ki_gear = (s_ki_gear + 1) % 5;
      g_motion_cfg.ki = s_ki_gears[s_ki_gear];
      printf("ki=%d/10\n", (int)(g_motion_cfg.ki * 10.0f));
      break;
    case 'I':
      s_cki_gear = (s_cki_gear + 1) % 5;
      g_foc.cur_ki = s_cki_gears[s_cki_gear];
      printf("cur ki=%d (mod LSB per LSB/s)\n", (int)g_foc.cur_ki);
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
      s_af_gear = (s_af_gear + 1) % 5;
      g_foc.angle_filt_alpha = s_af_gears[s_af_gear];
      printf("angle filter alpha=%s (lag ~%u us)\n",
             (g_foc.angle_filt_alpha >= 1.0f) ? "OFF" : "",
             (g_foc.angle_filt_alpha >= 1.0f)
               ? 0u
               : (unsigned)(1000000u / (uint32_t)((float)s_isr_hz_g * g_foc.angle_filt_alpha)));
      break;
    case 'e': case 'E':
      s_db_gear = (s_db_gear + 1) % 5;
      g_motion_cfg.hyb_slip_deg = s_db_gears[s_db_gear];
      printf("hybrid slip deadband=%d elec deg (= %d mech raw)\n",
             (int)g_motion_cfg.hyb_slip_deg,
             (int)(g_motion_cfg.hyb_slip_deg * 16384.0f /
                   (360.0f * (float)g_foc.pole_pairs)));
      break;
    case 'u': case 'U':
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
    case 'l':
      if (motion_state() == MOTION_RUN || calibration_active() || pwm3ph_enabled()) {
        printf("current loop: stop first ('s'); switching under load is refused\n");
      } else {
        int on = !foc_current_loop_enabled();
        foc_current_loop_enable(on);
        printf("current loop %s (kp=%d ki=%d iref=torque/%d cap=%d)\n",
               on ? "ON: PI on measured id/iq" : "OFF: direct voltage mode",
               (int)g_foc.cur_kp, (int)g_foc.cur_ki,
               (int)g_foc.cur_ref_div, (int)g_foc.cur_v_cap);
      }
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


static int console_set_haptic_param(const char *name, float val)
{
  int changed = 1;
  if (!isfinite(val)) return 0;
  if (!strcmp(name, "df")) {
    g_haptic_cfg.k_damp = val < 0.0f ? 0.0f : val > 1.0f ? 1.0f : val;
  } else if (!strcmp(name, "fi")) {
    g_haptic_cfg.k_inertia = val < 0.0f ? 0.0f : val > 0.3f ? 0.3f : val;
  } else if (!strcmp(name, "kp")) {
    g_haptic_cfg.kp = val < 0.0f ? 0.0f : val > 15.0f ? 15.0f : val;
  } else if (!strcmp(name, "kd")) {
    g_haptic_cfg.kd = val < 0.0f ? 0.0f : val > 2.0f ? 2.0f : val;
  } else if (!strcmp(name, "kf")) {
    g_haptic_cfg.k_free = val < 0.0f ? 0.0f : val > 0.5f ? 0.5f : val;
  } else if (!strcmp(name, "vl")) {
    int n = (int)(val + (val >= 0.0f ? 0.5f : -0.5f));
    if (n < 5) n = 5;
    if (n > MOTION_POWER_PCT_MAX) n = MOTION_POWER_PCT_MAX;
    g_haptic_cfg.limit_pct = n;
  } else if (!strcmp(name, "dw")) {
    float deg = val < 2.0f ? 2.0f : val > 90.0f ? 90.0f : val;
    g_haptic_cfg.det_width_rad = deg * 3.14159265359f / 180.0f;
  } else if (!strcmp(name, "ds")) {
    g_haptic_cfg.det_strength = val < 0.0f ? 0.0f : val > 6.0f ? 6.0f : val;
  } else if (!strcmp(name, "es")) {
    g_haptic_cfg.end_strength = val < 0.0f ? 0.0f : val > 6.0f ? 6.0f : val;
  } else if (!strcmp(name, "sp")) {
    g_haptic_cfg.snap_point = val < 0.5f ? 0.5f : val > 1.5f ? 1.5f : val;
  } else if (!strcmp(name, "sb")) {
    g_haptic_cfg.snap_bias = val < 0.0f ? 0.0f : val > 0.49f ? 0.49f : val;
  } else if (!strcmp(name, "pn")) {
    int n = (int)val;
    if (n < -64) n = -64;
    if (n > 64) n = 64;
    g_haptic_cfg.pos_min = n;
  } else if (!strcmp(name, "px")) {
    int n = (int)val;
    if (n < -64) n = -64;
    if (n > 64) n = 64;
    g_haptic_cfg.pos_max = n;
  } else if (!strcmp(name, "br")) {
    float deg = val < 1.0f ? 1.0f : val > 170.0f ? 170.0f : val;
    g_haptic_cfg.bound_rad = deg * 3.14159265359f / 180.0f;
  } else {
    changed = 0;
  }
  if (changed) motion_haptic_config_changed();
  return changed;
}

static int console_set_spin_velocity_param(const char *name, float val)
{
  if (!isfinite(val)) return 0;
  float kp = motion_spin_vel_kp();
  float ki = motion_spin_vel_ki();
  float ff = motion_spin_vel_ff();
  float fr = motion_spin_vel_friction();
  if (!strcmp(name, "vp")) kp = val;
  else if (!strcmp(name, "vi")) ki = val;
  else if (!strcmp(name, "vff")) ff = val;
  else if (!strcmp(name, "vfr")) fr = val;
  else return 0;
  motion_spin_set_velocity_gains(kp, ki, ff, fr);
  return 1;
}

static void console_position_preset(void)
{
  // The low-speed position loop is sensitive to inherited SPIN gains.
  // Use the measured smooth profile for GUI/rot positioning.
  g_motion_cfg.kp = 4.0f;
  g_motion_cfg.kd = 0.20f;
  g_motion_cfg.ki = 0.0f;
  g_motion_cfg.kff = 0.125f;
  g_motion_cfg.kfric = 150.0f;
  g_foc.angle_filt_alpha = 1.0f / 64.0f;
  motion_set_vel_window(256);
}

static int console_line_command(const char *line)
{
  while (*line == ' ' || *line == '\t') ++line;
  size_t n = strlen(line);
  while (n && (line[n - 1] == ' ' || line[n - 1] == '\t' ||
               line[n - 1] == '\r')) --n;
  if (!n) return 0;

  if (!strcmp(line, "estop")) {
    motion_stop();
    printf("EMERGENCY STOP: power stage released immediately\n");
    return 1;
  }

  if (n == 2 && (line[0] == 'm' || line[0] == 'M') &&
      line[1] >= '0' && line[1] <= '4') {
    int mode = line[1] - '0';
    if (motion_haptic_start(mode))
      printf("haptic m%d %s active; s releases, ? keeps heartbeat\n",
             mode, haptic_mode_name(mode));
    else
      printf("haptic m%d refused: stop other motion and check ready/fault\n", mode);
    return 1;
  }

  char cmd[16];
  float val;
  int used = 0;
  if (sscanf(line, "%15s %f%n", cmd, &val, &used) == 2) {
    while (line[used] == ' ' || line[used] == '\t') ++used;
    if (line[used] != '\0') return 0;

    if (!strcmp(cmd, "tel")) {
      int hz = (int)(val + (val >= 0.0f ? 0.5f : -0.5f));
      if (hz != 0 && hz != 10 && hz != 20 && hz != 50 && hz != 100) {
        printf("tel refused: use 0/10/20/50/100 Hz\n");
        return 1;
      }
      s_tel_hz = hz;
      s_tel_next_ms = s_now_ms;
      printf("telemetry %d Hz%s\n", hz, hz ? "" : " (off)");
      return 1;
    }
    if (!strcmp(cmd, "rot")) {
      if (motion_haptic_active()) motion_stop();
      if (motion_state() == MOTION_RUN || motion_state() == MOTION_FAULT) {
        printf("rot refused: stop current motion first\n");
        return 1;
      }
      if (val == 0.0f || val < -720.0f || val > 720.0f) {
        printf("rot refused: use -720..720 deg (nonzero)\n");
        return 1;
      }
      console_position_preset();
      float rps = g_motion_cfg.rev_per_s;
      if (rps > ROT_SPEED_MAX_RPS) rps = ROT_SPEED_MAX_RPS;
      if (rps < 0.005f) rps = 0.005f;
      int32_t vq = g_motion_cfg.vq_max;
      if (vq > ROT_VQ_MAX) vq = ROT_VQ_MAX;
      if (motion_start_turns(val / 360.0f, rps, vq))
        printf("rot start: %d/1000 deg at %d/1000 rev/s, vq=%d\n",
               (int)(val * 1000.0f), (int)(rps * 1000.0f), (int)vq);
      else
        printf("rot refused (state=%d)\n", (int)motion_state());
      return 1;
    }
    if (!strcmp(cmd, "rpm")) {
      if (val < 3.0f || val > 60.0f) {
        printf("rpm refused: use 3..60\n");
        return 1;
      }
      motion_spin_set_speed(val / 60.0f);
      printf("SPIN speed=%d rpm (%.4f rev/s)\n",
             (int)(val + 0.5f), val / 60.0f);
      return 1;
    }
    if (console_set_spin_velocity_param(cmd, val) ||
        console_set_haptic_param(cmd, val)) {
      printf("%s=%.3f\n", cmd, val);
      return 1;
    }
    return 0;
  }

  if (!strcmp(line, "cd")) {
    motion_haptic_set_center();
    printf("haptic center set at current angle\n");
    return 1;
  }
  return 0;
}

static int console_legacy_token(const char *t, int n)
{
  if (n == 1) {
    char c = t[0];
    return c == '?' || c == 'a' || c == 'A' || c == 'b' || c == 'B' ||
           c == 'c' || c == 'C' || c == 'd' || c == 'D' || c == 'e' ||
           c == 'E' || c == 'f' || c == 'F' || c == 'g' || c == 'G' ||
           c == 'h' || c == 'H' || c == 'i' || c == 'I' || c == 'j' ||
           c == 'J' || c == 'k' || c == 'K' || c == 'l' || c == 'L' ||
           c == 'm' || c == 'M' || c == 'n' || c == 'N' || c == 'o' ||
           c == 'O' || c == 'p' || c == 'P' || c == 'q' || c == 'Q' ||
           c == 'r' || c == 'R' || c == 's' || c == 'S' || c == 't' ||
           c == 'T' || c == 'u' || c == 'U' || c == 'v' || c == 'V' ||
           c == 'w' || c == 'W' || c == 'x' || c == 'X' || c == 'y' ||
           c == 'Y' || c == 'z' || c == 'Z' || c == '!' || c == '+' ||
           c == '-' || c == '=' || c == '_' || c == ' ';
  }
  if (n == 2 && t[0] == '#' && (t[1] == '0' || t[1] == '1')) return 1;
  if (n == 2 && (t[0] == 'x' || t[0] == 'X') && t[1] >= '0' && t[1] <= '7') return 1;
  if (n == 2 && (t[0] == 'w' || t[0] == 'W') && t[1] >= '1' && t[1] <= '8') return 1;
  if (n == 2 && t[0] == 'V' && t[1] >= '1' && t[1] <= '4') return 1;
  if (n == 3 && t[0] == 'm' && t[1] == 'w' && t[2] >= '1' && t[2] <= '4') return 1;
  return 0;
}

static int console_keepalive_cmd(int ch);

static void console_dispatch_legacy(const char *t, int n)
{
  for (int i = 0; i < n; ++i) {
    int ch = (unsigned char)t[i];
    if (console_keepalive_cmd(ch)) motion_spin_keepalive();
    if (ch == '?' || ch == 'a' || ch == 'A' || ch == 's' || ch == 'S' ||
        ch == ' ' || ch == 'n' || ch == 'g' || ch == 'G')
      calibration_keepalive();
    console_feed(ch);
  }
  motion_haptic_keepalive();
}

static int console_legacy_len_at(const char *t, int n)
{
  if (n >= 3 && t[0] == 'm' && t[1] == 'w' && t[2] >= '1' && t[2] <= '4')
    return 3;
  if (n >= 2 && t[0] == '#' && (t[1] == '0' || t[1] == '1')) return 2;
  if (n >= 2 && (t[0] == 'x' || t[0] == 'X') && t[1] >= '0' && t[1] <= '7') return 2;
  if (n >= 2 && (t[0] == 'w' || t[0] == 'W') && t[1] >= '1' && t[1] <= '8') return 2;
  if (n >= 2 && t[0] == 'V' && t[1] >= '1' && t[1] <= '4') return 2;
  return console_legacy_token(t, 1) ? 1 : 0;
}

static int console_legacy_sequence(const char *t, int n)
{
  int i = 0;
  while (i < n) {
    int len = console_legacy_len_at(t + i, n - i);
    if (!len) return 0;
    i += len;
  }
  return i == n && n > 1;
}

static void console_dispatch_legacy_sequence(const char *t, int n)
{
  int i = 0;
  while (i < n) {
    int len = console_legacy_len_at(t + i, n - i);
    if (!len) return;
    console_dispatch_legacy(t + i, len);
    i += len;
  }
}

static void telemetry_emit(void)
{
  int hm = motion_haptic_active() ? motion_haptic_mode() : 0;
  int16_t ia = 0, ib = 0, ic = 0;
  foc_last_currents(&ia, &ib, &ic);
  long ang = (long)(motion_haptic_angle_rad() * 18000.0f / 3.14159265359f);
  int32_t raw_vel = motion_haptic_active()
                  ? motion_haptic_vel_rawps() : motion_vel_rawps();
  long vel = (long)((int64_t)raw_vel * 6283 / 16384);
  long tq = (long)motion_cmd_q12();
  long tgt = (long)(motion_haptic_target_rad() * 18000.0f / 3.14159265359f);
  long pos = hm == 3 ? (long)motion_haptic_position() : 0;
  long sub = hm == 3 ? (long)(motion_haptic_subpos() * 100.0f) : 0;
  int raw = (int)(foc_last_angle() & 0x3fffu);
  printf("$T,3,%d,%ld,%ld,%ld,%ld,%ld,%ld,%d,%d,%u,%d,%d,%d,%d,%d\n",
         hm, ang, vel, tq, tgt, pos, sub,
         (int)motion_state(), pwm3ph_enabled(), (unsigned)s_isr_hz_g, raw,
         (int)ia, (int)ib, (int)ic, foc_current_valid() ? 1 : 0);
}

void console_telemetry_poll(uint32_t now_ms)
{
  if (!s_tel_hz) return;
  if (!s_tel_next_ms || (int32_t)(now_ms - s_tel_next_ms) >= 0) {
    telemetry_emit();
    s_tel_next_ms = now_ms + (uint32_t)(1000 / s_tel_hz);
  }
}

int console_telemetry_active(void) { return s_tel_hz != 0; }

void console_init(uint32_t hz)
{
  if (hz >= 1000) s_isr_hz_g = hz;
  console_help();
  console_dump_cfg();
}
int console_autorun_cancelled(void) { return s_cancel_autorun; }

// Only a recognized protocol byte proves that a live host is still talking to
// the board. A pulled cable can leave the UART RX line floating and produce
// arbitrary bytes; those must not refresh the SPIN host watchdog.
static int console_keepalive_cmd(int ch)
{
  switch (ch) {
    case '?': case 'a': case 'A': case 'b': case 'B': case 'c': case 'C':
    case 'd': case 'D': case 'e': case 'E': case 'f': case 'F': case 'g':
    case 'G': case 'h': case 'H': case 'i': case 'I': case 'j': case 'J':
    case 'k': case 'K': case 'l': case 'L': case 'm': case 'M': case 'n':
    case 'N': case 'o': case 'O': case 'p': case 'P': case 'q': case 'Q':
    case 'r': case 'R': case 's': case 'S': case 't': case 'T': case 'u':
    case 'U': case 'v': case 'V': case 'w': case 'W': case 'x': case 'X':
    case 'y': case 'Y': case 'z': case 'Z': case '!': case '+': case '-':
    case '=': case '_': case ' ': case '#':
      return 1;
    default:
      return 0;
  }
}

static char s_linebuf[65];
static int s_linelen;
static uint32_t s_line_last_ms;

static void console_process_token(void)
{
  if (!s_linelen) return;
  char token[65];
  memcpy(token, s_linebuf, (size_t)s_linelen);
  token[s_linelen] = '\0';
  int len = s_linelen;
  s_linelen = 0;

  if (console_line_command(token)) {
    motion_spin_keepalive();
    motion_haptic_keepalive();
    return;
  }
  if (console_legacy_token(token, len)) {
    console_dispatch_legacy(token, len);
    return;
  }
  if (console_legacy_sequence(token, len)) {
    console_dispatch_legacy_sequence(token, len);
    return;
  }
  printf("unknown command: %s\n", token);
}

void console_poll(uint32_t now_ms)
{
  s_now_ms = now_ms;
  if (s_arg_cmd && (uint32_t)(now_ms - s_arg_since) > 1000u) s_arg_cmd = 0;

  for (int i = 0; i < 64; ++i) {
    int ch = console_getch();
    if (ch < 0) break;
    if (ch == '\r') continue;
    if (ch == '\n') {
      console_process_token();
      continue;
    }
    if (ch < 0x20 || ch > 0x7e) continue;
    if (s_linelen >= (int)sizeof(s_linebuf) - 1) {
      printf("command too long; dropped\n");
      s_linelen = 0;
    }
    s_linebuf[s_linelen++] = (char)ch;
    s_line_last_ms = now_ms;
  }

  // Legacy host tools send one-byte or fixed two/three-byte commands without a
  // newline. New m0..m4 and parameter commands are delivered with newline.
  if (s_linelen && (uint32_t)(now_ms - s_line_last_ms) >= 10u) {
    char token[65];
    memcpy(token, s_linebuf, (size_t)s_linelen);
    token[s_linelen] = '\0';
    int new_mode = s_linelen == 2 && (token[0] == 'm' || token[0] == 'M') &&
                   token[1] >= '0' && token[1] <= '4';
    if (new_mode || console_legacy_token(token, s_linelen) ||
        console_legacy_sequence(token, s_linelen))
      console_process_token();
  }

  if (s_arg_cmd) s_arg_since = now_ms;
}
