#include "alta.h"
#include "foc_knob.h"
#include "hall.h"
#include "util.h"
#include <math.h>

#define DEG60        (M_PI / 3.0f)  // one hall sector in electrical radians
#define VEL_TAU      0.015f         // velocity low-pass [s]
#define RATE_TAU     0.020f         // edge-rate decay when no edges arrive [s]
#define STALE_US     2000u          // start decaying rate after 2ms without edges
#define INTERP_MAX_S 1.0f           // never interpolate beyond one sector
// Knob-use noise filter: phase-current glitches arrive at 1.2~2.4ms spacing,
// real knob motion is <=2 rev/s (>=24ms between edges). Reject anything in
// between. Raise HALL_RATE_CAP if you ever need to track faster motion.
#define HALL_MIN_EDGE_US 1500u
#define HALL_RATE_CAP_DEFAULT 250.0f  // sectors/s (~5 rev/s mech at 7pp)
// Poll-decoder commit: a candidate sector state must hold this long before it
// is accepted. Bounce-type noise (flips back within a few ms) never commits;
// real knob-speed motion dwells tens of ms per sector.
#define HALL_POLL_COMMIT_S 0.010f

// hall state (HU<<2|HV<<1|HW) -> sector index along the forward sequence
// (k*60deg = angle where sector k is entered); 000/111 are illegal (hall
// glitch or wiring problem). Default is the analytic order 5,4,6,2,3,1;
// 'scan' calibration rewrites it from the MEASURED forward order.
static int8_t sector_map[8] = { -1, 5, 3, 4, 1, 0, 2, -1 };

// --- edge context (written by GPIO0_isr, read by FOC loop) ---
static volatile float    s_pos_sec;   // continuous position in 60deg sectors
static volatile float    s_rate_sec;  // signed sector rate [sectors/s], decays to 0
static volatile uint32_t s_t_edge_us; // last hall edge timestamp
static volatile uint32_t s_edt_last;  // last ACCEPTED edge-to-edge interval [us]
static volatile int      s_last_k;    // last sector index, -1 = unknown
static volatile int      s_last_state;
static volatile uint32_t s_edges;
static volatile int      s_net_dk;    // net sector steps (calibration sweep)

// --- calibration anchors ---
static float s_a0;                    // pos_sec measured while rotor held at elec 0
static bool  s_flip;                  // hall sequence runs opposite to FOC angle
// --- scan-cal recorder: raw state + drag step index of every accepted commit
// (step index, not time: progress prints inside the drag loop then shift the
// wall clock but can never skew the learned load angle)
#define HALL_SCAN_MAX 96
static struct { int8_t raw; uint32_t idx; } s_scan[HALL_SCAN_MAX];
static volatile uint32_t s_scan_step;
static int  s_scan_n;
static bool s_scan_on;
// --- output estimates (FOC loop context) ---
static volatile float s_pos_est;      // pos_sec + interpolation
static volatile float s_mech;         // continuous mechanical angle [rad]
static volatile float s_mech_raw;     // ...staircase only, NO interpolation
static volatile float s_mech_vel;     // filtered mechanical velocity [rad/s]
static float s_thr_prev;
static float s_thr_raw_prev;
static float s_pp = MOTOR_POLE_PAIRS;
static volatile float s_rate_cap = HALL_RATE_CAP_DEFAULT;

static float wrap_pi(float x)
{
  return x - (float)(2.0 * M_PI) * floorf((x + (float)M_PI) * (float)(1.0 / (2.0 * M_PI)));
}

static void hall_commit(int s);

static float angle_from_pos(float pos)
{
  return s_flip ? (s_a0 - pos) * DEG60 : (pos - s_a0) * DEG60;
}

void hall_init(void)
{
  SYS_EnableAPBClock(DRV_GPIO_MASK);
  GPIO_SetInput(HALL_GPIO, HALL_BITS);
  GPIO_ClearInt(HALL_GPIO, HALL_BITS);
  GPIO_IntConfig(HALL_GPIO, HALL_BITS, GPIO_INTMODE_BOTHEDGE);
  GPIO_EnableInt(HALL_GPIO, HALL_BITS);
  INT_EnableIRQ(GPIO0_IRQn, IRQ_PRIO_GPIO);
}

// GPIO0_isr lives here so hall edges and (unused) port siblings share one ISR
void GPIO0_isr(void)
{
  uint8_t mis = (uint8_t)GPIO_GetMaskedIntStatus(GPIO0);
  GPIO_ClearInt(GPIO0, mis);
  if (mis & HALL_BITS) hall_isr();
}

void hall_isr(void)
{
  hall_commit(hall_state());
}

// one decoded hall transition; ISR context pre-cal, polled context post-cal
static void hall_commit(int s)
{
  uint32_t now = UTIL_GetUSec();
  if (s == s_last_state) return;          // not a new state
  int k = sector_map[s];
  s_last_state = s;
  if (k < 0) return;                      // 000/111: ignore, update will see it
  if (s_last_k < 0) {                     // first valid state
    s_last_k = k;
    s_pos_sec = k + 0.5f;
    s_pos_est = s_pos_sec;
    s_t_edge_us = now;
    if (s_scan_on && s_scan_n < HALL_SCAN_MAX) {
      s_scan[s_scan_n].raw = (int8_t)s;
      s_scan[s_scan_n].idx = s_scan_step;
      s_scan_n++;
    }
    return;
  }
  int dk = k - s_last_k;
  if (dk > 3) dk -= 6; else if (dk < -3) dk += 6;
  s_last_k = k;
  if (dk == 0) return;
  uint32_t edt = now - s_t_edge_us;
  if (edt < HALL_MIN_EDGE_US) return;   // PWM switching noise burst
  float r = 0.0f;                       // sectors per second
  if (edt < 200000u) r = 1.0f / ((float)edt * 1e-6f);
  if (r > s_rate_cap) return;           // too fast to be real motion: noise
  if (s_scan_on && s_scan_n < HALL_SCAN_MAX) {
    s_scan[s_scan_n].raw = (int8_t)s;
    s_scan[s_scan_n].idx = s_scan_step;
    s_scan_n++;
  }
  // entering sector k forward happens at pos=k, backward at pos=k+1: move the
  // CONTINUOUS position there by the shortest wrapped step. An absolute
  // assignment drops the turn count and injected a phantom +-60deg(mech)
  // jump at every electrical-rev wrap, so the mech angle never accumulated -
  // wrap_pi could not catch it (5 steps = 50deg mech < 180deg at 6pp).
  float target = (dk > 0) ? (float)k : (float)(k + 1);
  float d = target - s_pos_sec;
  d -= 6.0f * floorf((d + 3.0f) * (1.0f / 6.0f));
  s_pos_sec += d;
  s_pos_est = s_pos_sec;
  s_t_edge_us = now;
  s_edt_last = edt;
  s_rate_sec = (dk > 0) ? r : -r;       // r == 0 when the edge was very old
  s_net_dk += dk;                       // signed accumulation
  s_edges++;
}

// called once per FOC pass (dt = measured loop period)
void hall_update(float dt)
{
  // Synchronous decode: this IRQ runs at the PWM counter peak/underflow where
  // the drive is in a settled state. A raw state must hold 200us before it is
  // committed, so switching-synchronous glitches never decode as motion.
  static int   s_poll = -1;
  static float s_poll_t = 0.0f;
  int s = hall_state();
  if (s == s_poll) {
    s_poll_t += dt;
  } else {
    s_poll = s;
    s_poll_t = 0.0f;
  }
  if (s_poll_t >= HALL_POLL_COMMIT_S) hall_commit(s);

  uint32_t since = UTIL_GetUSec() - s_t_edge_us;

  // Extrapolate the angle at the measured edge rate while that is plausible:
  // up to 1.3x the last accepted edge interval (capped at 300ms). Without it
  // the decode is a 60deg-elec STAIRCASE at crawl speed - every sector
  // crossing makes the estimate leapfrog the reference and the position loop
  // sawtooths (violent shake during 'rot'). With it the estimate ramps
  // smoothly between real edges. The cap bounds the phantom advance after a
  // sudden stop, and the rate decays away (tau RATE_TAU) once past horizon,
  // so a stopped rotor settles back onto the true sector center.
  uint32_t horizon = (uint32_t)(1.3f * (float)s_edt_last);
  if (horizon > 300000u) horizon = 300000u;
  if (horizon < STALE_US) horizon = STALE_US;
  if (since > horizon) {
    float a = dt / RATE_TAU;
    if (a > 0.2f) a = 0.2f;
    s_rate_sec += (0.0f - s_rate_sec) * a;
  }

  // interpolate inside the sector, never beyond one sector
  float pos = s_pos_sec;
  if (since < 1000000u) {
    float fr = (float)since * 1e-6f * s_rate_sec;
    if (fr > INTERP_MAX_S) fr = INTERP_MAX_S;
    if (fr < -INTERP_MAX_S) fr = -INTERP_MAX_S;
    pos += fr;
  }
  s_pos_est = pos;

  // continuous mechanical angle = electrical angle / pole pairs
  float thr = angle_from_pos(pos) / s_pp;
  s_mech += wrap_pi(thr - s_thr_prev);
  s_thr_prev = thr;
  // staircase-only twin (no interpolation): the detent engine consumes this -
  // during decode chatter the interpolated angle swings +-5..15deg on a light
  // touch while the rotor barely moved, and a P/D loop on that phantom kicks
  // the rotor across half a revolution ("轻轻动一下就乱抖", traced 2026-10-01).
  float thr_raw = angle_from_pos(s_pos_sec) / s_pp;
  s_mech_raw += wrap_pi(thr_raw - s_thr_raw_prev);
  s_thr_raw_prev = thr_raw;

  // mechanical velocity from hall edge timing (much smoother than angle diff).
  // STALENESS GATE, tighter than the angle's: the extrapolated rate is fine
  // for smoothing the ANGLE, but as a VELOCITY it may point the wrong way -
  // the rotor can reverse (detent wall turnaround) inside the extrapolation
  // window while s_rate_sec keeps claiming the old direction. Feeding that
  // phantom into a D term ACCELERATES the reversal: the detent relay
  // oscillator ("挡位档一直在抖", 3V rails at every wall, no decay) was
  // traced to exactly this pump. One full interval without a confirming edge
  // => the direction claim is void: zero it now and drain the filter fast.
  float w = s_rate_sec * (DEG60 / s_pp);
  if (s_flip) w = -w;
  uint32_t v_stale = (uint32_t)(1.0f * (float)s_edt_last);
  if (v_stale < STALE_US) v_stale = STALE_US;
  bool vel_stale = since > v_stale;
  if (vel_stale) w = 0.0f;
  float a = dt / (vel_stale ? 0.004f : VEL_TAU);
  if (a > 0.5f) a = 0.5f;
  s_mech_vel += (w - s_mech_vel) * a;
}

float hall_electrical_angle(void)
{
  float a = angle_from_pos(s_pos_est);
  return a - (float)(2.0 * M_PI) * floorf(a * (float)(1.0 / (2.0 * M_PI)));
}

float hall_mech_angle(void)    { return s_mech; }
float hall_mech_angle_raw(void){ return s_mech_raw; }
float hall_mech_velocity(void) { return s_mech_vel; }
int   hall_state(void)         { return (GPIO_GetValue(HALL_GPIO, HALL_BITS) >> 4) & 7; }
bool  hall_state_valid(void)   { return sector_map[hall_state()] >= 0; }
uint32_t hall_edges(void)      { return s_edges; }

void hall_begin_align(void)
{
  int k = sector_map[hall_state()];
  if (k < 0) k = 0;
  s_a0 = k + 0.5f;
  s_pos_sec = s_a0;
  s_pos_est = s_a0;
  s_last_k = k;
  s_last_state = hall_state();
  s_rate_sec = 0.0f;
  s_t_edge_us = UTIL_GetUSec();
  s_net_dk = 0;
  s_flip = false;
  s_thr_prev = 0.0f;
  s_thr_raw_prev = 0.0f;
  s_mech = 0.0f;
  s_mech_raw = 0.0f;
  s_mech_vel = 0.0f;
}

int hall_sweep_net_dk(void) { return s_net_dk; }

void hall_finish_calib(bool flip)
{
  s_flip = flip;
  s_pos_est = s_pos_sec;
  s_rate_sec = 0.0f;
  s_thr_prev = angle_from_pos(s_pos_est) / s_pp;
  s_thr_raw_prev = angle_from_pos(s_pos_sec) / s_pp;
  s_mech = 0.0f;
  s_mech_raw = 0.0f;
  s_mech_vel = 0.0f;
}

void hall_set_flip(bool flip) { hall_finish_calib(flip); }

void hall_set_pp(float pp)
{
  if (pp < 1.0f) pp = 1.0f;
  if (pp > 30.0f) pp = 30.0f;
  s_pp = pp;
}

float hall_get_pp(void) { return s_pp; }

void hall_set_rate_cap(float cap)
{
  if (cap < 50.0f) cap = 50.0f;
  if (cap > 2000.0f) cap = 2000.0f;
  s_rate_cap = cap;
}

float hall_get_rate_cap(void) { return s_rate_cap; }

// --- scan calibration: learn map/direction/anchor from an open-loop drag ---
void hall_reset_decode(void)
{
  s_last_k = -1;
  s_last_state = -1;
  s_pos_sec = 0.0f;
  s_pos_est = 0.0f;
  s_rate_sec = 0.0f;
  s_edt_last = 0;
  s_net_dk = 0;
  s_t_edge_us = UTIL_GetUSec();
}

void hall_scan_begin(void) { s_scan_n = 0; s_scan_step = 0; s_scan_on = true; }
void hall_scan_note_step(uint32_t idx) { s_scan_step = idx; }
void hall_scan_end(void)   { s_scan_on = false; }
int  hall_scan_count(void) { return s_scan_n; }

bool hall_scan_get(int i, int *raw, uint32_t *idx)
{
  if (i < 0 || i >= s_scan_n) return false;
  *raw = s_scan[i].raw;
  *idx = s_scan[i].idx;
  return true;
}

// install the scan-learned map and anchor. pos0 is the rotor's CURRENT sector
// (from the pins, entry convention). The decode is anchored SECTOR-CENTERED
// (a0 = -0.5 -> electrical angle = (pos+0.5)*60): at near-zero speed there is
// no edge interpolation, so an entry-anchored decode lags the true angle by up
// to a full sector and the torque angle then sweeps to the 60deg stability
// edge (rotor stalls mid-sector). Centered, the error is bounded to +/-30deg
// elec -> torque never drops below 0.87 of commanded, at any speed.
void hall_scan_apply(const int8_t map[8], float pos0)
{
  for (int i = 0; i < 8; i++) sector_map[i] = map[i];
  s_flip = false;
  s_a0 = -0.5f;
  s_pos_sec = pos0;
  s_pos_est = pos0;
  s_last_k = (int)floorf(pos0);
  if (s_last_k < 0) s_last_k = 0;
  if (s_last_k > 5) s_last_k = 5;
  s_last_state = hall_state();
  s_rate_sec = 0.0f;
  s_edt_last = 0;
  s_net_dk = 0;
  s_t_edge_us = UTIL_GetUSec();
  s_thr_prev = angle_from_pos(pos0) / s_pp;
  s_thr_raw_prev = s_thr_prev;
  s_mech = 0.0f;
  s_mech_raw = 0.0f;
  s_mech_vel = 0.0f;
}

void hall_reset_origin(void) { s_mech = 0.0f; s_mech_raw = 0.0f; }
