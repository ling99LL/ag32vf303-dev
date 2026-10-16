// Motion state machine. Foreground transitions are atomic against the PWM ISR.
#include <math.h>
#include "motion.h"
#include "foc.h"
#include "pwm3ph.h"
#include "control_lock.h"
#include "control.h"

#define TWO_PI_F 6.28318530718f
#define PI_F 3.14159265359f
#define RAW_TURN 16384
#define Q16 65536LL
#define MAN_TIMEOUT_MS 30000u
#define MAX_DURATION_MS 3600000u

motion_cfg_t g_motion_cfg = {
  .kp=2.0f, .kd=0.02f, .kd_hold=0.0f, .ki=1.5f,
  .kff=0.125f, .kfric=150.0f, .vq_max=1638, .rev_per_s=0.05f,
  .err_follow=500.0f, .err_limit=2048.0f, .settle_raw=200,
  .timeout_ms=10000u, .hyb_slip_deg=15.0f,
  .hyb_corr_pct=0.35f, .hyb_corr_floor=0.05f
};
#ifndef MOTION_HYBRID_DEFAULT
#define MOTION_HYBRID_DEFAULT 1
#endif

typedef enum { POSITION, OPENLOOP, TORQUE, MANUAL } motion_mode_t;
static volatile motion_state_t s_state;
static motion_mode_t s_mode;
static const char *s_fault = "";
static uint32_t s_hz = 20000u, s_ticks, s_duration, s_timeout;
static int s_have_last, s_stuck_flag, s_man_timedout;
static uint16_t s_last_raw, s_vel_win = 256, s_vel_count;
static int64_t s_pos, s_start_pos, s_vel_pos, s_stuck_pos;
// Fixed-point trajectory avoids losing sub-raw steps after many turns.
static int64_t s_cmd, s_target, s_inc;
static int32_t s_vel, s_vel_meas, s_err, s_final_err, s_vq, s_iacc;
static float s_integral;
static uint32_t s_inband, s_stuck_ticks, s_crc0, s_jump_hi, s_jump_lo;
static uint64_t s_vib_sum;
static uint32_t s_vib_n;
static int32_t s_vib_peak;
static uint8_t s_hybrid = MOTION_HYBRID_DEFAULT, s_hy_init;
static float s_angle, s_slip, s_ol_inc;
static uint32_t s_corrections;
static int32_t s_fixed_vq, s_man_pct = 10;
static uint8_t s_man_mask = 1;

static float wrap(float a)
{
  while (a < 0) a += TWO_PI_F;
  while (a >= TWO_PI_F) a -= TWO_PI_F;
  return a;
}
static float shortest(float a)
{
  while (a > PI_F) a -= TWO_PI_F;
  while (a < -PI_F) a += TWO_PI_F;
  return a;
}
static float encoder_elec(void)
{
  float a = TWO_PI_F * (float)(((uint32_t)foc_last_angle() *
             g_foc.pole_pairs) & 0x3fffu) / RAW_TURN;
  return wrap((a - g_foc.zero_electric_angle) * g_foc.sensor_direction);
}
int32_t motion_vq_limit(void)
{
  if (g_foc.v_limit_q <= 0) return 0;
  return (int32_t)((int64_t)g_foc.v_limit_q * MOTION_POWER_PCT_MAX / 100);
}
static int32_t cap_vq(int32_t v)
{
  int32_t cap = motion_vq_limit();
  if (v > cap) v = cap;
  if (v < -cap) v = -cap;
  return v;
}
static void release(void)
{
  pwm3ph_release();
  g_foc.torque_q = 0;
  g_foc.voltage_d_q = 0;
  g_foc.comm_override = 0;
  s_hy_init = 0;
  s_vq = s_iacc = 0;
  s_integral = 0;
}
static void abort_move(const char *why)
{
  release();
  s_fault = why;
  s_state = MOTION_FAULT;
}
void motion_trip(const char *why)
{
  uint32_t key = control_lock();
  if (s_state != MOTION_FAULT) abort_move(why ? why : "safety fault");
  control_unlock(key);
}
void motion_stop(void)
{
  uint32_t key = control_lock();
  release();
  if (s_state != MOTION_FAULT) s_state = MOTION_IDLE;
  control_unlock(key);
}
int motion_recover(void)
{
  uint32_t key = control_lock();
  int ok = s_state == MOTION_FAULT;
  if (ok) {
    release();
    s_have_last = 0;
    s_vel = s_vel_meas = 0;
    s_vel_count = 0;
    s_vel_pos = s_pos;
    s_fault = "";
    s_state = MOTION_IDLE;
  }
  control_unlock(key);
  return ok;
}
void motion_init(void)
{
  motion_stop();
  s_state = MOTION_IDLE;
  s_fault = "";
  s_pos = s_start_pos = s_vel_pos = 0;
  s_have_last = 0;
  s_vel = s_vel_meas = 0;
  s_vel_count = 0;
  s_ticks = 0;
  s_hybrid = MOTION_HYBRID_DEFAULT;
  g_motion_cfg.vq_max = motion_vq_limit();
}
void motion_set_isr_rate(uint32_t hz)
{
  uint32_t key = control_lock();
  if (s_state != MOTION_RUN && hz >= 1000u && hz <= 200000u) s_hz = hz;
  control_unlock(key);
}
// Caller holds control_lock. Outputs stay off until all state is committed.
static int begin(motion_mode_t mode, uint32_t ms)
{
  if (!control_ready()) return 0;
  release();
  s_mode = mode;
  s_ticks = s_inband = s_stuck_ticks = 0;
  s_stuck_flag = s_man_timedout = 0;
  s_err = s_final_err = 0;
  s_start_pos = s_stuck_pos = s_pos;
  s_crc0 = foc_crc_errors();
  foc_oc_reset();   // 每段动作重新捕获过流峰值/计数/快照（foc.h）
  s_vib_sum = s_vib_n = s_vib_peak = 0;
  s_duration = (uint32_t)((uint64_t)ms * s_hz / 1000u);
  s_state = MOTION_RUN;
  // Clear stale compare preloads while MOE/INL are off. Counter keeps running
  // even when idle so sensor acquisition and fault detection stay alive.
  if (!pwm3ph_arm()) { abort_move("driver break"); return 0; }
  return 1;
}
int motion_start_turns(float turns, float rps, int32_t vq)
{
  uint32_t key = control_lock();
  int ok = 0;
  if (s_state == MOTION_RUN || s_state == MOTION_FAULT ||
      !isfinite(turns) || turns == 0 || fabsf(turns) > 1000) goto done;
  if (!isfinite(rps)) goto done;
  if (rps <= 0) rps = g_motion_cfg.rev_per_s;
  if (!isfinite(rps) || rps < 0.005f || rps > 2) goto done;
  float need = 2000.0f * fabsf(turns) / rps + 5000.0f;
  if (need > MAX_DURATION_MS) goto done;
  if (vq <= 0) vq = g_motion_cfg.vq_max;
  g_motion_cfg.vq_max = cap_vq(vq);
  g_motion_cfg.rev_per_s = rps;
  s_timeout = g_motion_cfg.timeout_ms;
  if (s_timeout < (uint32_t)need) s_timeout = (uint32_t)need;
  if (s_timeout > MAX_DURATION_MS) s_timeout = MAX_DURATION_MS;
  s_cmd = 0;
  s_target = (int64_t)(turns * RAW_TURN * (float)Q16);
  s_inc = (int64_t)(rps * RAW_TURN * (float)Q16 / s_hz);
  if (turns < 0) s_inc = -s_inc;
  ok = begin(POSITION, 0);
done:
  control_unlock(key);
  return ok;
}
static int start_fixed(motion_mode_t mode, int32_t vq, uint32_t ms, float rps)
{
  if (s_state == MOTION_RUN || s_state == MOTION_FAULT ||
      !ms || ms > MAX_DURATION_MS) return 0;
  s_fixed_vq = cap_vq(vq);
  // The inverse Park puts the field 90 deg electrical ahead of this angle, so
  // starting on the rotor angle snapped the rotor forward before the sweep could
  // take over (measured 2026-10-16: ~9 deg mechanical back-swing at the start of
  // every reverse sweep). Park the field ON the rotor instead - torque starts at
  // zero and builds in the sweep's own direction. Torque-hold keeps the field
  // ahead, which is how it applies a torque from rest.
  float th = encoder_elec();
  s_angle = (mode == OPENLOOP) ? wrap(th - (float)(PI_F / 2.0)) : th;
  // Direct commutation hook: zero offset and sensor direction never change.
  s_ol_inc = rps * TWO_PI_F * g_foc.pole_pairs * g_foc.sensor_direction / s_hz;
  if (!begin(mode, ms)) return 0;
  if (mode == OPENLOOP) {
    g_foc.comm_angle_e = s_angle;
    g_foc.comm_override = 1;
  }
  return 1;
}
int motion_openloop_start(float rps, int32_t vq, uint32_t ms)
{
  uint32_t key = control_lock();
  int ok = 0;
  if (isfinite(rps) && fabsf(rps) >= 0.005f && fabsf(rps) <= 2)
    ok = start_fixed(OPENLOOP, vq, ms, rps);
  control_unlock(key);
  return ok;
}
int motion_torque_hold(int32_t vq, uint32_t ms)
{
  uint32_t key = control_lock();
  int ok = start_fixed(TORQUE, vq, ms, 0);
  control_unlock(key);
  return ok;
}
void motion_manual_start(uint8_t mask, int32_t pct)
{
  uint32_t key = control_lock();
  if (s_state != MOTION_FAULT && control_ready()) {
    if (pct >= 0) s_man_pct = pct;
    if (s_man_pct > MOTION_POWER_PCT_MAX) s_man_pct = MOTION_POWER_PCT_MAX;
    if (s_man_pct < 0) s_man_pct = 0;
    s_man_mask = mask & 7u;
    begin(MANUAL, MAN_TIMEOUT_MS);
  }
  control_unlock(key);
}
void motion_manual_set(uint8_t mask, int32_t pct)
{
  uint32_t key = control_lock();
  if (motion_manual_active()) {
    if (mask != 0xffu) s_man_mask = mask & 7u;
    if (pct >= 0) s_man_pct = pct > MOTION_POWER_PCT_MAX ? MOTION_POWER_PCT_MAX : pct;
    s_ticks = 0;
  }
  control_unlock(key);
}
void motion_manual_stop(void) { motion_stop(); }
int motion_manual_active(void) { return s_state == MOTION_RUN && s_mode == MANUAL; }
uint8_t motion_manual_mask(void) { return s_man_mask; }
int32_t motion_manual_pct(void) { return s_man_pct; }
int motion_manual_timed_out(void)
{
  uint32_t key = control_lock();
  int r = s_man_timedout;
  s_man_timedout = 0;
  control_unlock(key);
  return r;
}
void motion_hybrid_enable(int on)
{
  uint32_t key = control_lock();
  s_hybrid = !!on;
  s_hy_init = 0;
  if (s_mode != OPENLOOP || s_state != MOTION_RUN) g_foc.comm_override = 0;
  control_unlock(key);
}
int motion_hybrid_enabled(void) { return s_hybrid; }
uint32_t motion_slip_corr(void) { return s_corrections; }
int32_t motion_slip_raw(void)
{
  return g_foc.pole_pairs ? (int32_t)(s_slip * RAW_TURN /
                                   (TWO_PI_F * g_foc.pole_pairs)) : 0;
}
void motion_set_vel_window(uint16_t win)
{
  uint32_t key = control_lock();
  s_vel_win = win < 8 ? 8 : win > 4096 ? 4096 : win;
  s_vel_count = 0;
  s_vel_pos = s_pos;
  control_unlock(key);
}
uint16_t motion_vel_window(void) { return s_vel_win; }
static void update_position(void)
{
  uint16_t raw = foc_last_angle() & 0x3fffu;
  int32_t d = s_have_last ? (int32_t)raw - s_last_raw : 0;
  s_last_raw = raw;
  s_have_last = 1;
  if (d > 8192) d -= RAW_TURN;
  if (d < -8192) d += RAW_TURN;
  int32_t max_d = 8 * RAW_TURN / s_hz + 2;
  if (d > max_d) { d = max_d; ++s_jump_hi; }
  if (d < -max_d) { d = -max_d; ++s_jump_lo; }
  s_pos += d;
  if (++s_vel_count >= s_vel_win) {
    int64_t dp = s_pos - s_vel_pos;
    s_vel_pos = s_pos;
    s_vel_count = 0;
    int32_t max_dp = 3 * RAW_TURN * (int32_t)s_vel_win / s_hz + 4;
    if (dp > max_dp) dp = max_dp;
    if (dp < -max_dp) dp = -max_dp;
    s_vel_meas = (int32_t)(dp * s_hz / s_vel_win);
    s_vel += (s_vel_meas - s_vel) / 4;
    if (s_state == MOTION_RUN) {
      int32_t av = s_vel_meas < 0 ? -s_vel_meas : s_vel_meas;
      s_vib_sum += av;
      ++s_vib_n;
      if (av > s_vib_peak) s_vib_peak = av;
    }
  }
}
static int hybrid_step(float advance)
{
  if (!s_hybrid) { g_foc.comm_override = 0; return 1; }
  float enc = encoder_elec();
  if (!s_hy_init) { s_angle = enc; s_hy_init = 1; }
  float dth = advance * TWO_PI_F * g_foc.pole_pairs * g_foc.sensor_direction / RAW_TURN;
  s_angle = wrap(s_angle + dth);
  s_slip = shortest(s_angle - enc);
  if (fabsf(s_slip) > 1.4f) { abort_move("pole slip (hybrid)"); return 0; }
  float db = g_motion_cfg.hyb_slip_deg * PI_F / 180;
  float ex = s_slip > db ? s_slip-db : s_slip < -db ? s_slip+db : 0;
  if (ex != 0) {
    float gain = ex / (20 * PI_F / 180);
    if (gain > 1) gain = 1;
    if (gain < -1) gain = -1;
    float cap = fabsf(dth) * g_motion_cfg.hyb_corr_pct +
                g_motion_cfg.hyb_corr_floor * TWO_PI_F * g_foc.pole_pairs / s_hz;
    s_angle = wrap(s_angle - gain * cap);
    ++s_corrections;
  }
  g_foc.comm_angle_e = s_angle;
  g_foc.comm_override = 1;
  return 1;
}
static void finish(void)
{
  s_final_err = s_err;
  release();
  s_state = MOTION_DONE;
}
void motion_step_isr(void)
{
  update_position();
  if (s_state != MOTION_RUN) { g_foc.torque_q = 0; return; }
  ++s_ticks;
  if (foc_crc_errors() - s_crc0 > 200u) { abort_move("crc storm"); return; }
  if (s_mode != POSITION && s_ticks >= s_duration) {
    if (s_mode == MANUAL) s_man_timedout = 1;
    finish();
    return;
  }
  if (s_mode == MANUAL) {
    int32_t hi = PWM3PH_ARR * (100 + s_man_pct) / 200;
    int32_t lo = PWM3PH_ARR * (100 - s_man_pct) / 200;
    pwm3ph_set(s_man_mask & 1 ? hi : lo, s_man_mask & 2 ? hi : lo,
               s_man_mask & 4 ? hi : lo);
    return;
  }
  if (s_mode == OPENLOOP) {
    s_angle = wrap(s_angle + s_ol_inc);
    g_foc.comm_angle_e = s_angle;
    g_foc.comm_override = 1;
    s_vq = cap_vq(s_fixed_vq);
  } else if (s_mode == TORQUE) {
    s_vq = cap_vq(s_fixed_vq);
  } else {
    if ((uint64_t)s_ticks * 1000 / s_hz > s_timeout) {
      abort_move("timeout"); return;
    }
    int64_t position = (s_pos - s_start_pos) * Q16;
    float e = (float)(s_cmd - position) / Q16;
    int64_t prev = s_cmd;
    float fol = g_motion_cfg.err_follow;
    if ((s_inc > 0 && e < fol) || (s_inc < 0 && e > -fol)) {
      s_cmd += s_inc;
      if ((s_inc > 0 && s_cmd > s_target) || (s_inc < 0 && s_cmd < s_target))
        s_cmd = s_target;
    }
    e = (float)(s_cmd - position) / Q16;
    s_err = (int32_t)e;
    if (fabsf(e) > g_motion_cfg.err_limit) { abort_move("stall (error > limit)"); return; }
    if (!hybrid_step((float)(s_cmd - prev) / Q16)) return;
    float lim = cap_vq(g_motion_cfg.vq_max);
    float vel_cmd = (float)(s_cmd - prev) * s_hz / Q16;
    float damping = g_motion_cfg.kd * (vel_cmd - s_vel);
    if (damping > lim * .25f) damping = lim * .25f;
    if (damping < -lim * .25f) damping = -lim * .25f;
    float u = g_motion_cfg.kp * e + damping + g_motion_cfg.kff * vel_cmd +
              (vel_cmd > 0 ? g_motion_cfg.kfric : vel_cmd < 0 ? -g_motion_cfg.kfric : 0);
    float band = g_motion_cfg.settle_raw;
    if (band < 20) band = 20;
    float try_u = u + s_integral;
    if (fabsf(e) < band * 4 && !((try_u >= lim && e > 0) || (try_u <= -lim && e < 0))) {
      s_integral += g_motion_cfg.ki * e / s_hz;
      if (s_integral > lim * .4f) s_integral = lim * .4f;
      if (s_integral < -lim * .4f) s_integral = -lim * .4f;
    } else s_integral -= s_integral / s_hz;
    s_iacc = (int32_t)s_integral;
    u += s_integral;
    if (u > lim) u = lim;
    if (u < -lim) u = -lim;
    s_vq = (int32_t)u;
    if (s_cmd == s_target) {
      if (fabsf(e) < band) {
        if (++s_inband >= s_hz / 20) { finish(); return; }
      } else s_inband = 0;
      if (s_pos - s_stuck_pos < 6 && s_pos - s_stuck_pos > -6) {
        if (++s_stuck_ticks >= s_hz) {
          s_stuck_flag = 1;
          abort_move("target not reached (blocked)"); return;
        }
      } else { s_stuck_pos = s_pos; s_stuck_ticks = 0; }
    }
  }
  g_foc.torque_q = s_vq;
}

motion_state_t motion_state(void) { return s_state; }
const char *motion_fault_msg(void) { return s_fault; }
int32_t motion_error_raw(void) { return s_err; }
int32_t motion_final_err_raw(void) { return s_final_err; }
int32_t motion_vel_rawps(void) { return s_vel; }
int32_t motion_vel_meas_rawps(void) { return s_vel_meas; }
uint32_t motion_jump_hi(void) { return s_jump_hi; }
uint32_t motion_jump_lo(void) { return s_jump_lo; }
int32_t motion_cmd_q12(void) { return s_vq; }
int32_t motion_iacc_q12(void) { return s_iacc; }
uint32_t motion_elapsed_ms(void) { return (uint32_t)((uint64_t)s_ticks * 1000 / s_hz); }
int32_t motion_travelled_raw(void)
{
  uint32_t key = control_lock();
  int64_t d = s_pos - s_start_pos;
  control_unlock(key);
  return d > INT32_MAX ? INT32_MAX : d < INT32_MIN ? INT32_MIN : (int32_t)d;
}
int32_t motion_vib_mean(void)
{
  uint32_t key = control_lock();
  int32_t r = s_vib_n ? (int32_t)(s_vib_sum / s_vib_n) : 0;
  control_unlock(key);
  return r;
}
int32_t motion_vib_peak(void) { return s_vib_peak; }
int motion_hold_relaxed(void) { return s_state != MOTION_RUN; }
int motion_settled_stuck(void)
{
  uint32_t key = control_lock();
  int r = s_stuck_flag;
  s_stuck_flag = 0;
  control_unlock(key);
  return r;
}
