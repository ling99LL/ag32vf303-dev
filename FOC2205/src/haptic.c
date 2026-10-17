#include <math.h>
#include <stddef.h>
#include "haptic.h"
#include "foc.h"

#define TWO_PI_F 6.28318530718f
#define PI_F 3.14159265359f
#define RAW_TURN 16384.0f
#define REF_Q12_PER_UNIT 546.0f
#define DET_P_BASE 4.5f
#define DET_D_FRAC 0.05f
#define DET_D_CAP_UNIT 0.4f
#define DET_DZ_FRAC 0.20f
#define DET_DZ_CAP_RAD 0.01745329252f
#define DET_IDLE_VEL 0.05f
#define DET_IDLE_DELAY_S 0.40f
#define DET_RECENTER_TAU_S 0.50f
#define DET_RECENTER_WINDOW_RAD 0.03490658504f
#define DET_RUNAWAY_RADS 30.0f
#define INERTIA_CAP_FRAC 0.08f
#define BOUND_VEL_MAX 0.35f

haptic_cfg_t g_haptic_cfg = {
  .mode = HAPTIC_FREE,
  .k_damp = 0.10f,
  .k_inertia = 0.05f,
  .kp = 5.0f,
  .kd = 0.30f,
  .k_free = 0.02f,
  .det_width_rad = 0.52359877560f,
  .det_strength = 2.5f,
  .end_strength = 4.0f,
  .snap_point = 0.60f,
  .snap_bias = 0.0f,
  .pos_min = 0,
  .pos_max = -1,
  .bound_rad = 0.78539816340f,
  .limit_pct = 20,
};

static int s_center_valid;
static int64_t s_center_raw;
static int32_t s_det_pos;
static float s_det_last_width;
static float s_det_center_offset;
static float s_det_idle_s;
static float s_target_rad;
static float s_det_subpos;

static float clampf(float x, float lo, float hi)
{
  return x < lo ? lo : (x > hi ? hi : x);
}

static int32_t clamp_q12(float x, int32_t limit)
{
  if (limit < 0) limit = 0;
  if (x > (float)limit) x = (float)limit;
  if (x < -(float)limit) x = -(float)limit;
  return (int32_t)x;
}

static float detent_width_eff(void)
{
  float w = g_haptic_cfg.det_width_rad;
  if (!isfinite(w) || w < 0.03490658504f) w = 0.03490658504f; /* 2 deg */
  if (w > PI_F) w = PI_F;
  return w;
}

static int detent_bounded(void)
{
  return g_haptic_cfg.pos_max >= g_haptic_cfg.pos_min;
}

static void detent_reanchor(int64_t pos_raw)
{
  float w = detent_width_eff();
  float rel = (float)(pos_raw - s_center_raw) * TWO_PI_F / RAW_TURN;
  int32_t p = (int32_t)lroundf(rel / w);
  if (detent_bounded())
  {
    if (p < g_haptic_cfg.pos_min) p = g_haptic_cfg.pos_min;
    if (p > g_haptic_cfg.pos_max) p = g_haptic_cfg.pos_max;
  }
  s_det_pos = p;
  s_det_center_offset = 0.0f;
  s_det_idle_s = 0.0f;
  s_det_last_width = w;
}

void haptic_init(void)
{
  s_center_valid = 0;
  s_center_raw = 0;
  s_det_pos = 0;
  s_det_last_width = detent_width_eff();
  s_det_center_offset = 0.0f;
  s_det_idle_s = 0.0f;
  s_target_rad = 0.0f;
  s_det_subpos = 0.0f;
  g_haptic_cfg.mode = HAPTIC_FREE;
}

void haptic_mode_enter(int mode, int64_t pos_raw)
{
  if (mode < HAPTIC_FREE || mode >= HAPTIC_MODE_COUNT) mode = HAPTIC_FREE;
  if (!s_center_valid)
  {
    s_center_raw = pos_raw;
    s_center_valid = 1;
  }
  g_haptic_cfg.mode = mode;
  if (mode == HAPTIC_DETENT) detent_reanchor(pos_raw);
}

void haptic_set_center(int64_t pos_raw)
{
  s_center_raw = pos_raw;
  s_center_valid = 1;
  detent_reanchor(pos_raw);
}

void haptic_config_changed(int64_t pos_raw)
{
  if (g_haptic_cfg.det_width_rad != s_det_last_width)
    detent_reanchor(pos_raw);
}

int haptic_center_valid(void) { return s_center_valid; }
int64_t haptic_center_raw(void) { return s_center_raw; }

float haptic_relative_rad(int64_t pos_raw)
{
  if (!s_center_valid) return 0.0f;
  return (float)(pos_raw - s_center_raw) * TWO_PI_F / RAW_TURN;
}

int32_t haptic_limit_q12(void)
{
  int32_t pct = g_haptic_cfg.limit_pct;
  if (pct < 1) pct = 1;
  if (pct > 100) pct = 100;
  return (int32_t)((int64_t)g_foc.v_limit_q * pct / 100);
}

int32_t haptic_compute_q12(int64_t pos_raw, int32_t vel_rawps, float dt,
                           int32_t limit_q)
{
  if (!(dt > 0.0f)) dt = 1.0f / 20000.0f;
  if (!s_center_valid)
  {
    s_center_raw = pos_raw;
    s_center_valid = 1;
  }
  if (limit_q <= 0) limit_q = haptic_limit_q12();
  if (limit_q < 0) limit_q = 0;

  float rel = haptic_relative_rad(pos_raw);
  float vel = (float)vel_rawps * TWO_PI_F / RAW_TURN;
  float torque = 0.0f;
  float width = detent_width_eff();

  if (g_haptic_cfg.det_width_rad != s_det_last_width)
    detent_reanchor(pos_raw);

  s_target_rad = rel;
  s_det_subpos = 0.0f;

  if (fabsf(vel) > DET_RUNAWAY_RADS)
    return 0;

  switch (g_haptic_cfg.mode)
  {
    case HAPTIC_DAMP:
      torque = -g_haptic_cfg.k_damp * REF_Q12_PER_UNIT * vel;
      break;

    case HAPTIC_INERTIA:
      torque = g_haptic_cfg.k_inertia * REF_Q12_PER_UNIT * vel;
      {
        float assist_cap = (float)limit_q * INERTIA_CAP_FRAC;
        torque = clampf(torque, -assist_cap, assist_cap);
      }
      break;

    case HAPTIC_DETENT:
    {
      int bounded = detent_bounded();
      float center = (float)s_det_pos * width + s_det_center_offset;
      float err = rel - center;
      int oob = 0;

      if (bounded)
      {
        if (s_det_pos < g_haptic_cfg.pos_min) s_det_pos = g_haptic_cfg.pos_min;
        if (s_det_pos > g_haptic_cfg.pos_max) s_det_pos = g_haptic_cfg.pos_max;
        center = (float)s_det_pos * width + s_det_center_offset;
        err = rel - center;
        oob = (err < 0.0f && s_det_pos == g_haptic_cfg.pos_min) ||
              (err > 0.0f && s_det_pos == g_haptic_cfg.pos_max);
      }

      float snap_r = width * clampf(g_haptic_cfg.snap_point, 0.5f, 1.5f);
      float bias_r = width * clampf(g_haptic_cfg.snap_bias, 0.0f, 0.49f);
      float snap_hi = snap_r + ((s_det_pos >= 0) ? -bias_r : bias_r);
      float snap_lo = -snap_r + ((s_det_pos <= 0) ? bias_r : -bias_r);
      if (!oob && err > snap_hi && (!bounded || s_det_pos < g_haptic_cfg.pos_max))
      {
        ++s_det_pos;
        s_det_center_offset = 0.0f;
        s_det_idle_s = 0.0f;
        center = (float)s_det_pos * width;
        err = rel - center;
      }
      else if (!oob && err < snap_lo && (!bounded || s_det_pos > g_haptic_cfg.pos_min))
      {
        --s_det_pos;
        s_det_center_offset = 0.0f;
        s_det_idle_s = 0.0f;
        center = (float)s_det_pos * width;
        err = rel - center;
      }

      if (fabsf(vel) < DET_IDLE_VEL)
        s_det_idle_s += dt;
      else
        s_det_idle_s = 0.0f;

      // Strong detent pull is required to break static friction at the click.
      // Once the rotor is parked within 2 degrees of the detent center, creep
      // that detent center onto the rotor so the hold torque decays to zero.
      if (!oob && s_det_idle_s >= DET_IDLE_DELAY_S &&
          fabsf(err) < DET_RECENTER_WINDOW_RAD)
      {
        float step = err * fminf(dt / DET_RECENTER_TAU_S, 0.05f);
        s_det_center_offset += step;
        center += step;
        err = rel - center;
      }

      float dz = fminf(DET_DZ_FRAC * width, DET_DZ_CAP_RAD);
      float err_eff = err - clampf(err, -dz, dz);
      float strength = oob ? g_haptic_cfg.end_strength : g_haptic_cfg.det_strength;
      if (strength < 0.0f) strength = 0.0f;
      float p_gain = strength * DET_P_BASE * REF_Q12_PER_UNIT;
      float d_gain = fminf(strength * DET_D_FRAC, DET_D_CAP_UNIT) * REF_Q12_PER_UNIT;
      torque = -p_gain * err_eff - d_gain * vel;
      s_target_rad = center;
      s_det_subpos = err / width;
      break;
    }

    case HAPTIC_BOUNDED:
    {
      float b = fabsf(g_haptic_cfg.bound_rad);
      if (!isfinite(b) || b < 0.01745329252f) b = 0.01745329252f;
      if (rel > b)
      {
        s_target_rad = b;
        float v_ref = clampf(g_haptic_cfg.kp * (b - rel), -BOUND_VEL_MAX, 0.0f);
        torque = g_haptic_cfg.kd * REF_Q12_PER_UNIT * (v_ref - vel);
      }
      else if (rel < -b)
      {
        s_target_rad = -b;
        float v_ref = clampf(g_haptic_cfg.kp * (-b - rel), 0.0f, BOUND_VEL_MAX);
        torque = g_haptic_cfg.kd * REF_Q12_PER_UNIT * (v_ref - vel);
      }
      else
      {
        s_target_rad = rel;
        torque = -g_haptic_cfg.k_free * REF_Q12_PER_UNIT * vel;
      }
      break;
    }

    case HAPTIC_FREE:
    default:
      torque = 0.0f;
      break;
  }

  return clamp_q12(torque, limit_q);
}

float haptic_target_rad(void) { return s_target_rad; }
int32_t haptic_detent_position(void) { return s_det_pos; }
float haptic_detent_subpos(void) { return s_det_subpos; }

const char *haptic_mode_name(int mode)
{
  switch (mode)
  {
    case HAPTIC_FREE: return "free";
    case HAPTIC_DAMP: return "damping";
    case HAPTIC_INERTIA: return "inertia";
    case HAPTIC_DETENT: return "detent";
    case HAPTIC_BOUNDED: return "bounded";
    default: return "?";
  }
}
