// Motion controller on top of the FOC voltage/current loop.
// Position: 16384 raw/turn; velocity: raw/s. Q12 commands are normalized to
// g_foc.v_limit_q; no Vbus measurement exists to infer physical phase volts.
// STOP/DONE/FAULT disable INL and MOE. FAULT requires control_recover(), which
// checks hardware before calling motion_recover(); starts never clear a fault.
#ifndef MOTION_H
#define MOTION_H

#include <stdint.h>

typedef enum
{
  MOTION_IDLE  = 0,
  MOTION_RUN   = 1,
  MOTION_HOLD  = 2,   // reserved wire value; completion releases output
  MOTION_FAULT = 3,
  MOTION_DONE  = 4
} motion_state_t;

typedef struct
{
  float    kp;
  float    kd;
  float    kd_hold; // reserved, unused
  float    ki;
  float    kff;
  float    kfric;
  int32_t  vq_max;
  float    rev_per_s;
  float    err_follow;
  float    err_limit;
  int32_t  settle_raw;
  uint32_t timeout_ms;
  float    hyb_slip_deg;
  float    hyb_corr_pct;
  float    hyb_corr_floor;
  // Closed-loop SPIN velocity PI. Output and errors use mechanical raw/s;
  // the PI output is Q12 modulation/current reference, like torque_q.
  float    spin_vel_kp;
  float    spin_vel_ki;
  float    spin_vel_ff;
  float    spin_vel_fric;
} motion_cfg_t;

extern motion_cfg_t g_motion_cfg;

void motion_init(void);
void motion_set_isr_rate(uint32_t hz);
void motion_step_isr(void);

int  motion_start_turns(float turns, float rev_per_s, int32_t vq_max_q12);
void motion_stop(void);
void motion_trip(const char *why);
int motion_recover(void);
int  motion_openloop_start(float rev_per_s, int32_t vq_q12, uint32_t ms);
int  motion_torque_hold(int32_t vq_q12, uint32_t ms);

// Endless rotation ("SPIN"). Closed loop uses a velocity PI on the encoder;
// open loop advances a fixed voltage vector. The host must poll at least once
// per second or the ISR starts a bounded deceleration and releases the bridge.
#ifndef SPIN_POWER_PCT_MAX
#define SPIN_POWER_PCT_MAX 80
#endif
#ifndef SPIN_POWER_PCT_DEFAULT
#define SPIN_POWER_PCT_DEFAULT 20
#endif
#ifndef SPIN_OPENLOOP_POWER_PCT_MAX
#define SPIN_OPENLOOP_POWER_PCT_MAX 20
#endif
int  motion_spin_start(int direction, float rev_per_s, int power_pct);
int  motion_spin_start_mode(int direction, float rev_per_s, int power_pct,
                            int open_loop);
void motion_spin_stop(void);
void motion_spin_keepalive(void);
void motion_spin_set_speed(float rev_per_s);
void motion_spin_set_power(int power_pct);
int  motion_spin_power_cap(void);
int  motion_spin_active(void);
int  motion_spin_stopping(void);
int32_t motion_spin_pct(void);
float   motion_spin_rps(void);
int  motion_spin_timed_out(void);
void motion_spin_set_velocity_gains(float kp, float ki, float ff, float friction);
float motion_spin_vel_kp(void);
float motion_spin_vel_ki(void);
float motion_spin_vel_ff(void);
float motion_spin_vel_friction(void);
int32_t motion_spin_target_vel_rawps(void);
int32_t motion_spin_feedback_rawps(void);
int32_t motion_spin_vel_error_rawps(void);

void motion_manual_start(uint8_t mask, int32_t pct);
void motion_manual_set(uint8_t mask, int32_t pct);
void motion_manual_stop(void);
int  motion_manual_active(void);
uint8_t motion_manual_mask(void);
int32_t  motion_manual_pct(void);
int  motion_manual_timed_out(void);

// Native high-resolution force-feedback modes (m0..m4).
int  motion_haptic_start(int mode);
void motion_haptic_keepalive(void);
int  motion_haptic_active(void);
int  motion_haptic_mode(void);
int  motion_haptic_timed_out(void);
int  motion_haptic_timeout_pending(void);
void motion_haptic_set_center(void);
void motion_haptic_config_changed(void);
int32_t motion_haptic_limit_q12(void);
int32_t motion_haptic_vel_rawps(void);
float   motion_haptic_angle_rad(void);
float   motion_haptic_target_rad(void);
int32_t motion_haptic_position(void);
float   motion_haptic_subpos(void);

void motion_hybrid_enable(int on);
int  motion_hybrid_enabled(void);
int32_t  motion_slip_raw(void);
uint32_t motion_slip_corr(void);
void     motion_set_vel_window(uint16_t win);
uint16_t motion_vel_window(void);

motion_state_t motion_state(void);
int32_t  motion_error_raw(void);
int32_t  motion_final_err_raw(void);
int32_t  motion_vel_rawps(void);
int32_t  motion_vel_meas_rawps(void);
uint32_t motion_jump_hi(void);
uint32_t motion_jump_lo(void);
int32_t  motion_cmd_q12(void);
int32_t  motion_vib_mean(void);
int32_t  motion_vib_peak(void);
int      motion_hold_relaxed(void);
int32_t  motion_iacc_q12(void);
uint32_t motion_elapsed_ms(void);
int32_t  motion_travelled_raw(void);
int      motion_settled_stuck(void);
#ifndef MOTION_POWER_PCT_MAX
#define MOTION_POWER_PCT_MAX 20
#endif

int32_t motion_vq_limit(void);

const char *motion_fault_msg(void);

#endif
