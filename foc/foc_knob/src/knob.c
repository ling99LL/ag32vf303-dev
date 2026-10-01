// knob.c - force-feedback effects in voltage-mode torque control.
// Reference: CSDN "基于FOC的项目----力反馈旋钮" (ratchet / bounded / damping /
// inertia), extended with spring + free modes, all sharing one PD shape.
// Mode 3 (KNOB_DETENT) is a port of scottbez1/smartknob's haptic state
// machine (firmware/src/motor_task.cpp), adapted to the 60deg-elec hall
// quantization - see the notes at detent_track().
#include "foc_knob.h"
#include "hall.h"
#include "util.h"
#include <math.h>

KnobParams g_knob = {
  .mode          = KNOB_FREE,
  .voltage_limit = VOLT_LIMIT_DEFAULT,
  .kp            = 5.0f,   // V/rad: 0.2rad (11deg) error -> 1V
  // D for the bounded-wall effect: a FIXED-magnitude brake on the
  // LAST REAL PIN DIRECTION (bang-bang, V). A continuous -kd*w with w from
  // the edge-interval EWMA lags a fast reversal by the turnaround coast
  // plus the EWMA fill (~110ms); at the ~2.6Hz quantized-spring cycle that
  // is past 90deg of phase, and the D term becomes the ENERGY PUMP - kd
  // 0.05->0.45 GREW the limit cycle from 19deg to 28.5deg (census 2026-10-01).
  // The bang brake cannot lag more than one turnaround coast, and it is
  // zero at rest (w_det gate), so parked stays silent.
  .kd            = 0.45f,  // V, bang-brake magnitude (bounded wall)
  .k_damp        = 0.10f,
  .k_inertia     = 0.05f,
  .k_free        = 0.02f,
  .detents       = 8.0f,
  .bound_rad     = (float)(45.0 * M_PI / 180.0),
  .center        = 0.0f,
  .det_width     = (float)(30.0 * M_PI / 180.0),
  // Detent pull = strength * DET_KP_BASE V/rad. 5.0 held two sectors off
  // at 2.0V and railed the snap at 3V - the user found the blocking too
  // hard (2026-10-01) and asked for half: 2.5 keeps every hold inside the
  // detent <= ~0.85V (deep sub-breakaway, silent) and softens the click.
  // Shake safety does NOT depend on the strength: holds + D stay far under
  // breakaway at any strength, and the mid-detent box is eaten by the
  // jitter re-center. If the click now feels too weak, the ds slider is
  // live - honest range 2.5 (light) .. 5.0 (hard snap).
  .det_strength  = 2.5f,
  .end_strength  = 4.0f,
  .snap_point    = 0.6f,
  .snap_bias     = 0.0f,
  .pos_min       = 0,
  .pos_max       = -1,     // max < min -> unbounded (SmartKnob convention)
};

// ---------------- SmartKnob detent engine tuning constants ------------------
// P = strength * DET_KP_BASE [V/rad]. The base is sized so that EVERY
// parkable quantized rest sits WELL below the ~2.5V breakaway: one sector
// off holds at strength*0.75V, two sectors at strength*2.0V (0.75V/2.0V @
// ds 5 - 20% margin under breakaway). The margin is what stops the
// "release between detents and it shakes forever" cycle: a rotor arriving
// at a wall with residual speed must STICK there (wall < static friction),
// or the wall re-launches it each pass and the bounce self-sustains
// (traced: 29s of 1030<->1070 pin bouncing, walls at 2.48V vs 2.5V break).
// From the THIRD sector on (genuinely between detents) the force rails at
// voltage_limit - the snap click is untouched.
#define DET_KP_BASE       1.5f       // P = strength * this [V/rad]
#define DET_DZ_RAD        0.0174533f // dead zone hard cap: 1 deg (SmartKnob)
#define DET_DZ_WIDTH_FRAC 0.2f       // ...and 20% of the detent width
#define DET_CROSS_W       15.0f      // snap crossings need |vel| below this
                                     // [rad/s] - effectively "always", the
                                     // runaway guard at 30 is the real cap.
                                     // History: this gate was 4 rad/s as a
                                     // second line of defense against the
                                     // relay oscillator, but blocking snaps
                                     // during a normal flick makes the stale
                                     // center rail 3V AGAINST the hand (a
                                     // rubber-band grab) and then yank forward
                                     // on the catch-up - the "甩动抖". The
                                     // relay's actual engines (sub-breakaway
                                     // holds + the hall velocity staleness
                                     // gate) are both in place, so count
                                     // crossings like SmartKnob does.
#define DET_RUNAWAY_W     30.0f      // |vel| cut-off [rad/s]: the hall decode
                                     // is rate-capped at ~44 rad/s (250
                                     // sect/s), so this never false-triggers
                                     // on noise, only on real bursts
#define DET_IDLE_VEL      0.05f      // below this EWMA velocity = parked
#define DET_IDLE_DELAY_US 500000u    // parked this long -> re-center
#define DET_VEL_TAU       1.0f       // idle-detector EWMA time constant [s]
#define DET_RECENTER_TAU  2.0f       // re-center time constant [s] (SmartKnob
                                     // uses 0.0005/loop @1kHz = tau 2s)

static struct {
  bool     init;       // (re)anchor center/position on the next pass
  float    origin;     // detent 0 center [rad mech, continuous]
  float    center;     // current detent center [rad mech]
  float    last_width; // raw det_width the anchor was computed with
  int32_t  position;   // integer detent index
  float    subpos;     // fractional position inside the detent
  float    vel_ewma;   // low-passed velocity for the idle detector
  uint32_t idle_since; // us since motion stopped (0 = moving)
} g_det;

int32_t knob_detent_position(void) { return g_det.position; }
float   knob_detent_subpos(void)   { return g_det.subpos; }

// 'z' (angle zero) and 'fl' (commutation flip) teleport the hall decode; the
// detent grid must restart from the new decode instead of counting endless
// crossings. Explicit on purpose - see detent_track().
void knob_detent_reanchor(void) { g_det.init = true; }

volatile float g_knob_uq     = 0.0f;
volatile float g_knob_target = 0.0f;
// field angle override: the rot drag applies ITS OWN integrated field angle
// (g_knob_th) instead of the hall decode - foc_loop_irq checks g_knob_th_valid
volatile float g_knob_th       = 0.0f;
volatile bool  g_knob_th_valid = false;

// one-shot rotation trajectory (host 'rot' command): rate-locked DRAG with a
// slow position trim. The field angle advances kinematically at the commanded
// (ramped) rate - exactly how the calibration drag, which this motor runs
// butter-smooth - and uq is the constant drag voltage. The hall position error
// only bends the field RATE (integrator output, clamped to +-10%): a plain
// position loop on the 60deg-quantized hall decode must build more than one
// sector of P error to break static friction and then bursts (violent shake),
// while an integrator-driven rate is physically unable to kick the rotor.
static struct {
  volatile bool  active;
  volatile bool  hold;     // arrived: rate command zero, trim closes the gap
  volatile float dir;      // commanded direction (+1/-1)
  volatile float target;   // ramping reference [rad, continuous mech angle]
  volatile float goal;
  volatile float speed;    // reference slew rate [rad/s]
  volatile float th_ff;    // drag field electrical angle [rad, integrated]
} g_spin;

void knob_spin_start(float from_rad, float goal_rad, float speed_rads)
{
  g_spin.target = from_rad;
  g_spin.goal   = goal_rad;
  g_spin.speed  = speed_rads > 0.05f ? speed_rads : 0.05f;
  g_spin.dir    = (goal_rad >= from_rad) ? 1.0f : -1.0f;
  // start at the max-torque load angle for the commanded direction: x=0
  // (field on the rotor) for forward, x=pi (field anti-phase, cos=-1) for
  // reverse - starting reverse at x=0 applies FULL FORWARD torque and the
  // rotor pole-slips at half speed instead of dragging
  g_spin.th_ff  = hall_electrical_angle() +
                  ((goal_rad >= from_rad) ? 0.0f : (float)M_PI);
  g_spin.hold   = false;
  g_spin.active = true;
}

void knob_spin_stop(void)     { g_spin.active = false; g_spin.hold = false; }
bool knob_spin_active(void)   { return g_spin.active; }
bool knob_spin_settling(void) { return g_spin.active && g_spin.hold; }
void knob_spin_hold(void)     { g_spin.hold = true; }
void knob_spin_release(void)  { g_spin.active = false; g_spin.hold = false; }
float knob_spin_goal(void)    { return g_spin.goal; }

static float clampf(float x, float lo, float hi)
{
  return x < lo ? lo : (x > hi ? hi : x);
}

// ---------------- SmartKnob detent engine (mode 3) --------------------------
// Detent width snapped to WHOLE hall sectors: the decode is a (60deg/pp)
// mechanical staircase, so a detent center must be able to coincide with a
// decode value - otherwise the engine would stand on the rotor with a torque
// it can never zero out (constant current, hum, heat).
static float detent_width_eff(void)
{
  float sector = (float)(M_PI / 3.0) / hall_get_pp();   // mech rad per sector
  float w = g_knob.det_width;
  if (w < sector) w = sector;
  return floorf(w / sector + 0.5f) * sector;
}

// Position tracker: anchor + snap-point crossings. Runs on every pass while
// mode 3 is selected - INCLUDING during a 'rot' drag - so the counter stays
// continuous through host-driven moves. Torque is applied separately.
static void detent_track(float th, float vel)
{
  float w = detent_width_eff();
  // (re)anchor ONLY on explicit events (mode entry, width change, and the
  // 'z'/'fl' commands via knob_detent_reanchor). There is deliberately NO
  // "decode too far from center" auto re-anchor: a rotor held past a bound
  // is legitimately far from its detent, and re-anchoring there would make
  // the engine follow the rotor instead of pulling it back.
  if (g_det.init || g_knob.det_width != g_det.last_width) {
    if (g_det.init) {
      // Align the grid PHASE with the hall decode staircase (the width is
      // already a whole number of sectors): detent centers then sit exactly
      // ON decode values, so a rotor parked at a center reads angle==0
      // instead of a permanent +-5deg phase offset that the P term turns
      // into standing torque (shake fuel).
      float sector = (float)(M_PI / 3.0) / hall_get_pp();
      g_det.origin = roundf(th / sector) * sector;
    }
    g_det.center     = g_det.origin + roundf((th - g_det.origin) / w) * w;
    g_det.position   = (int32_t)roundf((g_det.center - g_det.origin) / w);
    g_det.last_width = g_knob.det_width;
    g_det.init       = false;
  }
  int num_pos = g_knob.pos_max - g_knob.pos_min + 1;    // <=0: unbounded
  // bounds received while the rotor sits beyond them: clamp the index (the
  // center follows), so out_of_bounds fires and the endstop pulls it home
  if (num_pos > 0) {
    if (g_det.position > g_knob.pos_max) {
      g_det.position = g_knob.pos_max;
      g_det.center   = g_det.origin + (float)g_det.position * w;
    } else if (g_det.position < g_knob.pos_min) {
      g_det.position = g_knob.pos_min;
      g_det.center   = g_det.origin + (float)g_det.position * w;
    }
  }
  // crossing check with hysteresis (SmartKnob snap_point >= 0.5 makes
  // adjacent detents unable to oscillate) and home-side asymmetry
  // (snap_point_bias > 0 = harder to leave position 0, easier to return).
  // Speed-gated (DET_CROSS_W): a fast flight overshooting a snap point must
  // not flip the center mid-air - with a quantized decode the flipped center
  // re-launches the rotor from the far wall and the engine never settles.
  // Both walls then pull home and D + friction kill the bounce instead.
  float angle  = th - g_det.center;
  if (fabsf(vel) <= DET_CROSS_W) {
    float snap_r = w * g_knob.snap_point;
    float bias_r = w * g_knob.snap_bias;
    float snap_hi =  snap_r + ((g_det.position >= 0) ? -bias_r : bias_r);
    float snap_lo = -snap_r + ((g_det.position <= 0) ?  bias_r : -bias_r);
    if (angle > snap_hi &&
        (num_pos <= 0 || g_det.position < g_knob.pos_max)) {
      g_det.center += w;
      g_det.position++;
    } else if (angle < snap_lo &&
               (num_pos <= 0 || g_det.position > g_knob.pos_min)) {
      g_det.center -= w;
      g_det.position--;
    }
  }
  g_det.subpos = (th - g_det.center) / w;
}

// dt drives the spin reference ramp; effects themselves are P/D on angle+velocity
float knob_compute_uq(float th, float w, float dt)
{
  float uq = 0.0f;
  g_knob_th_valid = false;

  // mode switch arms a re-anchor; track positions (incl. during 'rot') in mode 3
  static int s_last_mode = -1;
  if (g_knob.mode != s_last_mode) {
    s_last_mode = g_knob.mode;
    g_det.init = true;
  }
  // All effects run on TRUTHFUL state: the raw staircase angle (no
  // interpolation) and an edge-interval velocity that decays to zero between
  // edges. The interpolated th/rate lie during decode chatter - a light
  // touch at a pin boundary threw th +-5..15deg and 'vel' to +-5rad/s while
  // the rotor barely moved, and P/D at full rail on that phantom shook the
  // knob across half a revolution ("轻轻动一下就乱抖", traced 2026-10-01).
  // The detent engine proved this filter (its release-shake died with it);
  // the 2026-10-01 all-mode census then caught the SAME engine feeding the
  // spring mode a self-sustained +-1-sector limit cycle, so the observer is
  // now shared by every mode that converts velocity into torque.
  // New pins are accepted DIRECTIONALLY: a step continuing the current
  // direction (or jumping 2+ pins) is real motion and accepted at once - a
  // 30ms hold here made the held angle lag the pull-home flight by sectors
  // and ratcheted the angle away (-8780deg). A REVERSING step is the
  // signature of boundary dither / wall ping-pong and must hold 30ms before
  // the engine believes it: that ping-pong is what fed the release-shake.
  static float s_det_hold, s_det_cand, s_det_wd;
  static uint32_t s_det_cand_us, s_det_last_chg;
  static int8_t   s_det_dir;
  static bool s_det_init;
  static float s_rev_ewma;   // reversal fraction of accepted pin steps
  float th_det = th, w_det = w;
  uint32_t nowu = UTIL_GetUSec();
  {
    float th_raw = hall_mech_angle_raw();
    if (!s_det_init) {
      s_det_hold = th_raw;
      s_det_cand = th_raw;
      s_det_cand_us = nowu;
      s_det_last_chg = nowu;
      s_det_init = true;
    } else {
      if (th_raw != s_det_cand) {
        s_det_cand = th_raw;              // new pin: restart its settle timer
        s_det_cand_us = nowu;
      }
      float step = th_raw - s_det_hold;
      int8_t sgn = (step > 0.0f) ? 1 : (step < 0.0f ? -1 : 0);
      bool cont = (sgn != 0 && sgn == s_det_dir) ||
                  (fabsf(step) > 1.5f * ((float)(M_PI / 3.0) / hall_get_pp()));
      // REVERSING steps split by their gap from the previous pin: a real
      // turnaround must decelerate to zero and cross back, ~2x(sector/speed)
      // - at 7rad/s that is ~50ms; boundary flicker (the spring's ratchet,
      // the detent's release-shake) re-crosses every 6..15ms. Below 25ms a
      // reversal is flicker: hold it for the 30ms candidate window instead.
      // Believing faster reversals turned the bang brake into a shaker (v5:
      // dsgn flipped at flick rate, uq a +-0.45V square wave at 83Hz).
      uint32_t gap = (uint32_t)(nowu - s_det_last_chg);
      bool rev_real = (sgn != 0 && sgn != s_det_dir && gap >= 25000u);
      if (th_raw != s_det_hold &&
          (cont || rev_real || (uint32_t)(nowu - s_det_cand_us) >= 30000u)) {
        float w_edge = step / (float)((uint32_t)(nowu - s_det_last_chg) * 1e-6f);
        if (w_edge > 60.0f) w_edge = 60.0f;
        if (w_edge < -60.0f) w_edge = -60.0f;
        s_det_wd += (w_edge - s_det_wd) * 0.3f;
        s_det_last_chg = nowu;
        s_det_hold = th_raw;
        // reversal-rate EWMA: ~0 while really turning, ~0.5 at a hall
        // boundary flicker (the rotor jittering around one boundary). It
        // flags "boundary jitter" for the detent idle detector - jitter is
        // motion to vel_ewma but it is NOT motion to a human hand.
        {
          float rev = (sgn != 0 && sgn != s_det_dir) ? 1.0f : 0.0f;
          s_rev_ewma += (rev - s_rev_ewma) * 0.15f;
        }
        if (sgn != 0) s_det_dir = sgn;
      }
      if ((uint32_t)(nowu - s_det_last_chg) > 30000u) {
        // 30ms without a confirmed pin: start bleeding the last edge velocity
        // (same gentle rate as before). Real flight crosses pins every <=25ms
        // and is untouched; a turnaround gets its stale wrong-direction
        // velocity drained during the coast instead of holding it 80ms.
        s_det_wd += (0.0f - s_det_wd) * fminf(dt / 0.05f, 0.25f);
        s_rev_ewma += (0.0f - s_rev_ewma) * fminf(dt / 0.3f, 0.02f);
      }
    }
    th_det = s_det_hold;
    w_det = s_det_wd;
  }
  if (g_knob.mode == KNOB_DETENT)
    detent_track(th_det, w_det);

  // (the spring no longer uses a P field at all - see KNOB_SPRING below)

  // rotation trajectory overrides any mode until it arrives or is aborted
  if (g_spin.active) {
    float ref_rate = 0.0f;                 // signed reference rate [mech rad/s]
    if (!g_spin.hold) {
      float remain = g_spin.goal - g_spin.target;
      float v = g_spin.speed;
      float vmax = 3.0f * fabsf(remain);   // exponential landing ramp
      if (vmax < v) v = vmax;
      float step = v * dt;
      // snap below 0.005 rad: the exponential tail's last steps (~2e-7 rad)
      // are below the float32 ULP at 2pi (~5e-7), the reference would stall
      // a few mrad short of the goal forever and the arrival never fired
      if (fabsf(remain) <= step || fabsf(remain) < 0.005f) {
        g_spin.target = g_spin.goal;
      } else {
        ref_rate = g_spin.dir * v;
        g_spin.target += ref_rate * dt;
      }
    }
    g_knob_target = g_spin.target;
    // Position handling, two regimes:
    //   in-band (|err| < 0.30 rad): kinematic reference rate + gentle trim.
    //   NOTE the band must be WIDER than one decode sector jump (0.1745 rad
    //   mech): the quantized decode swings err by that much at every sector
    //   crossing, and a narrower band makes the servo lunge on each crossing
    //   (hard field steps -> driver FAULT).
    //   out-of-band (rotor really stuck on a detent under the slow landing
    //   crawl, or overshot): park the crawl and servo the LOAD ANGLE
    //   x = th_ff - rotor to the max-torque point (x=0 pushes forward, x=pi
    //   pushes backward) so the full drag voltage breaks it free; the band
    //   resumes on re-entry. Servoing an integrator output cannot kick.
    float err = g_spin.target - th;
    float rate;
    static uint32_t s_oob_t = 0;           // out-of-band since [us]
    if (fabsf(err) <= 0.15f) {
      s_oob_t = 0;
      float tcap = 0.10f * g_spin.speed;
      rate = ref_rate + clampf(SPIN_TRIM_KP * err, -tcap, tcap);
    } else {
      if (s_oob_t == 0) s_oob_t = UTIL_GetUSec();
      // a decode sector jump swings err by 0.1745 rad for a moment - only
      // servo after the excursion has persisted 0.5s (a real stall)
      if ((uint32_t)(UTIL_GetUSec() - s_oob_t) < 500000u) {
        rate = ref_rate;                   // ride the swing with the reference
      } else {
        // stalled out of band: servo the LOAD ANGLE x = th_ff - rotor to the
        // max-torque point (x=0 pushes forward, x=pi pushes backward) so the
        // full drag voltage breaks the rotor loose; band resumes on re-entry
        float x = g_spin.th_ff - hall_electrical_angle();
        float dx = x - ((err > 0.0f) ? 0.0f : (float)M_PI);
        dx -= (float)(2.0 * M_PI) * floorf((dx + (float)M_PI) *
                                           (float)(1.0 / (2.0 * M_PI)));
        rate = clampf(-3.0f * dx / hall_get_pp(), -0.5f, 0.5f);
      }
    }
    g_spin.th_ff += rate * hall_get_pp() * dt;   // elec rad
    g_knob_th = g_spin.th_ff;              // THIS angle drives the field
    g_knob_th_valid = true;                // (foc_loop_irq must use it!)
    // drag voltage with breakaway margin: 2.5V sits exactly AT this motor's
    // static friction (the cal drag only works because the rotor is already
    // moving) -> from standstill it stick-slips; 3.0V keeps it riding
    uq = SPIN_UQ_CAP;
    g_knob_uq = uq;
    return uq;
  }

  switch (g_knob.mode) {
  case KNOB_FREE:
    uq = 0.0f;
    g_knob_target = th;
    break;

  case KNOB_DAMP: // viscous drag: oppose motion (truthful edge velocity)
    uq = -g_knob.k_damp * w_det;
    g_knob_target = th_det;
    break;

  case KNOB_INERTIA: // flywheel: assist motion (keep gains small!)
    // Positive velocity feedback: unbounded, fi*w crosses kinetic friction
    // at w = F_kin/fi (~6-10rad/s) and above that the assist out-runs
    // friction - a hard flick would spin the knob up to the decode rate
    // cap and keep it there. Cap the assist below kinetic friction so any
    // motion always decays; the flywheel feel survives at normal speeds.
    {
      float a = g_knob.k_inertia * w_det;
      if (a > 0.25f) a = 0.25f;
      if (a < -0.25f) a = -0.25f;
      uq = a;
    }
    g_knob_target = th_det;
    break;

  case KNOB_DETENT: { // SmartKnob discrete detent engine (tracking above)
    th = th_det;              // truthful raw staircase angle + edge velocity
    w = w_det;                // (see the block above - never the interpolation)
    float wid    = detent_width_eff();
    float angle  = th - g_det.center;      // +: past center, toward pos+1
    float sector = (float)(M_PI / 3.0) / hall_get_pp();
    int   num_pos = g_knob.pos_max - g_knob.pos_min + 1;
    // past a bound with no further detent to go to = endstop; note our sign:
    // angle < 0 pushes BELOW min, angle > 0 pushes ABOVE max (SmartKnob's
    // crossing convention is mirrored, so their oob test is flipped too)
    bool  oob = num_pos > 0 &&
                ((angle < 0.0f && g_det.position == g_knob.pos_min) ||
                 (angle > 0.0f && g_det.position == g_knob.pos_max));
    // idle re-center (SmartKnob IDLE_*): parked for 0.5s inside the detent -
    // or one sector short of it, which is where a too-weak detent settles -
    // and the center creeps to the rotor (tau 2s) so no standing torque and
    // no heat. Threshold is widened from SmartKnob's 5deg to one sector
    // because the decode cannot report anything finer at rest.
    g_det.vel_ewma += (w - g_det.vel_ewma) * fminf(dt / DET_VEL_TAU, 0.05f);
    // Parked = genuinely still OR boundary-jittering. A rotor resting
    // between two sub-breakaway walls glides wall-to-wall on the decode
    // staircase; the decode-phase pump sustains the bounce for seconds
    // (census v9, park +10: 22deg span, 8+ bounces) while vel_ewma looks
    // like real motion - only the ~50% reversal rate gives it away. Jitter
    // must count as parked so the idle re-center engages and creeps the
    // center into the bounce centroid (P -> 0, the bounce starves).
    if (fabsf(g_det.vel_ewma) > DET_IDLE_VEL && s_rev_ewma < 0.4f) {
      g_det.idle_since = 0;
    } else if (g_det.idle_since == 0) {
      g_det.idle_since = nowu;
    }
    if (g_det.idle_since != 0 &&
        (uint32_t)(nowu - g_det.idle_since) > DET_IDLE_DELAY_US &&
        !oob && fabsf(angle) < 2.2f * sector) {
      // window widened to 2.2 sectors: with sub-breakaway walls a released
      // rotor can legally park one FULL sector out (e2, angle +-20deg) -
      // the creep must reach it too, or that park keeps a standing pull.
      // A JITTER park (reversal-rate high) creeps 4x faster: the wall-to-
      // wall bounce needs the standing P gone in ~1s, not 3s.
      float rtau = (s_rev_ewma > 0.4f) ? 0.5f : DET_RECENTER_TAU;
      g_det.center += (th - g_det.center) * fminf(dt / rtau, 0.02f);
    }
    // runaway guard: a detent P loop on a quantized decode can burst into a
    // positive-feedback shake - above the cut-off, let go entirely
    if (fabsf(w) > DET_RUNAWAY_W) {
      uq = 0.0f;
    } else {
      // dead zone: SmartKnob's min(20% width, 1deg) is useless on a hall.
      // The decode only reports whole sectors, so with a 1deg dead zone a
      // ONE-SECTOR-OFF rest hits strength*4V/rad*10deg = the full rail (3V),
      // above the ~2.5V breakaway: the rotor breaks loose, flies the sector,
      // and the far wall re-launches it -> a sustained relay oscillator (the
      // reported "挡位档一直在抖", reproduced: p2p 40deg, 3V 57% of samples).
      // Widen the P dead zone to at least HALF A SECTOR: one sector off then
      // holds at strength*2V (1.74V @ ds 5 - below breakaway = silent), while
      // a 2-sector error still snaps at the full rail (the detent click).
      float dz  = fminf(DET_DZ_WIDTH_FRAC * wid, DET_DZ_RAD);
      float dzq = 0.5f * sector;
      if (dzq > dz) dz = dzq;
      float err = angle - clampf(angle, -dz, dz);
      // endstop positions pull with their own (separate) strength; with
      // min==max the knob becomes a return-to-center spring, exactly like
      // SmartKnob's "Return-to-center" demo config
      float P = (oob ? g_knob.end_strength : g_knob.det_strength) * DET_KP_BASE;
      // D sized for the QUANTIZED decode (diverges from SmartKnob here): the
      // P term is a 10deg staircase that pumps a fixed energy kick at every
      // sector crossing, and inside the center sector the rotor is invisible
      // (decode pinned at the center) so ONLY D can damp the through-sector
      // coast - without it the rotor hunts between the sector walls forever.
      // SmartKnob's width piecewise fades to ~0 at our widths; scale with
      // strength instead: 0.05 x strength (0.25 @ default 5), capped 0.4V.
      // The cap is a HARD safety bound: wall (<=2.0V) + |D| (<=0.4V) must
      // stay under the ~2.5V static breakaway, so a rotor arriving at a wall
      // with residual speed always STICKS at the turnaround. A stronger D
      // re-launched the bounce: the edge-interval velocity lags/opposes at
      // turnarounds even when honest between edges, and wall+D >= breakaway
      // sustained a 40deg pin-bounce for 29s ("松手一直抖", traced).
      float D = g_knob.det_strength * 0.05f;
      if (D > 0.4f) D = 0.4f;
      uq = -P * err - D * w;
    }
    g_knob_target = g_det.center;
  } break;

  case KNOB_BOUNDED: { // free inside +-bound, spring back outside
    // Wall P on the raw staircase (the interpolated angle swings +-5..15deg
    // during boundary dither and P fired on that phantom - same family as
    // the detent release-shake). D is the bang brake (see g_knob.kd note).
    float x = th_det - g_knob.center;
    float b = g_knob.bound_rad;
    float dsgn = fabsf(w_det) > 0.05f ? (float)s_det_dir : 0.0f;
    if (x > b) {
      g_knob_target = g_knob.center + b;
      uq = g_knob.kp * (b - x) - g_knob.kd * dsgn;
    } else if (x < -b) {
      g_knob_target = g_knob.center - b;
      uq = g_knob.kp * (-b - x) - g_knob.kd * dsgn;
    } else {
      g_knob_target = th_det;
      uq = -g_knob.k_free * w_det;   // no P field inside: continuous D is safe
    }
  } break;

  case KNOB_SPRING: { // rate-locked homing drag, NOT a P spring
    // Census v1..v7 (2026-10-01) killed every flavor of P spring on this
    // hardware: any force field over the 10deg staircase keeps a moving
    // rotor oscillating (the decode-phase error does net work per cycle),
    // and every velocity-derived brake - EWMA or bang - only fed the pump
    // (raising kd made it BIGGER). The rotor's real motion was +-1deg at a
    // hall boundary while the decode painted 30deg slingshots; even the
    // reported 7rad/s was phantom. The one actuator that is PROVEN smooth
    // on this motor+hall is the rate-locked drag (rot / cal scan): the
    // field angle integrates kinematically and the rotor follows in sync -
    // physically unable to kick. So the spring is a homing drag: engage
    // past the band, drag home at a capped crawl, release at touchdown.
    // ZERO torque at rest = nothing to shake and nothing to pump.
    static bool  s_home_act;
    static float s_home_ff;    // drag field electrical angle
    static uint32_t s_retry_at = 0;    // earliest next engage (backoff)
    static uint32_t s_backoff  = 2000000u;
    static float    s_prog_ref = 0.0f;
    static uint32_t s_prog_t   = 0;
    float err    = g_knob.center - th_det;   // +: rotor below center
    float sector = (float)(M_PI / 3.0) / hall_get_pp();
    if (s_home_act) {
      if (fabsf(err) < 0.6f * sector || fabsf(w_det) > 20.0f) {
        s_home_act = false;    // touchdown (crawl-speed) or user flew away
      }
    } else if (fabsf(err) > 1.0f * sector && fabsf(w_det) < 15.0f &&
               (int32_t)(nowu - s_retry_at) >= 0) {
      // field drops onto the rotor at the max-pull well for the pull
      // direction (xw = 0 forward, xw = pi reverse: the applied vector sits
      // at th_ff+90deg so the pull is uq*cos(xw) - xw=0 is FULL pull, and
      // starting anywhere past +-pi/4 is too weak to break static friction:
      // the sin-model "fix" engaged at 1.36V and the rotor never moved,
      // caught by the census as 3.00V standing on a parked rotor)
      s_home_ff  = hall_electrical_angle() +
                   ((err > 0.0f) ? 0.0f : (float)M_PI);
      s_home_act = true;
      s_prog_ref = err;
      s_prog_t   = nowu;
    }
    if (s_home_act) {
      float dir  = (err > 0.0f) ? 1.0f : -1.0f;
      float rate = 1.5f * fabsf(err);
      if (rate > 1.2f)  rate = 1.2f;    // homing cruise ~69deg/s
      if (rate < 0.10f) rate = 0.10f;   // crawl at touchdown
      s_home_ff += dir * rate * hall_get_pp() * dt;
      // Load-angle guard, COS model (pull = uq*cos(xw), xw = field-rotor
      // relative to the pull well): ASYMMETRIC clamp. Rotor lagging/stuck
      // (xw > 0.15): re-pin just shy of full pull (2.96V) - enough to break
      // loose, never reverses. Rotor LEADING (xw < -2.2): the cos pull has
      // reversed into a brake (up to 1.77V) - re-pin there so a launched
      // rotor is reined in instead of chased (the v8 symmetric +-0.6 clamp
      // kept 0.83x pull on a leading rotor and slingshot to 13rad/s).
      float xref = (err > 0.0f) ? 0.0f : (float)M_PI;
      float xw   = s_home_ff - hall_electrical_angle() - xref;
      xw -= (float)(2.0 * M_PI) * floorf((xw + (float)M_PI) *
                                         (float)(1.0 / (2.0 * M_PI)));
      bool repin = false;
      if (xw > 0.15f)  { xw = 0.15f;  repin = true; }
      if (xw < -2.2f)  { xw = -2.2f;  repin = true; }
      if (repin) s_home_ff = hall_electrical_angle() + xref + xw;
      g_knob_th       = s_home_ff;      // THIS angle drives the field
      g_knob_th_valid = true;           // (foc_loop_irq must use it!)
      uq = SPIN_UQ_CAP;
      // progress gate + backoff: no ground gained for 0.6s (local stiction
      // above the 3V rail, or the user holding the knob) -> let go instead
      // of standing at full pull; retry after a growing pause (2/4/8s) so
      // a loaded spring tugs politely instead of humming at 3V forever.
      if (fabsf(err) < fabsf(s_prog_ref) - 0.3f * sector) {
        s_prog_ref = err;
        s_prog_t   = nowu;
        s_backoff  = 2000000u;         // moving again: retry soon if stalled
      } else if ((uint32_t)(nowu - s_prog_t) > 600000u) {
        s_home_act = false;
        // Stalled NEAR center: give up for good instead of a corrective
        // tug - the decode phase can sit adverse to the pull well there
        // (actual pull 3*cos(xw+-0.52) can dip under the ~2.5V breakaway),
        // the rest inside the band is torque-free anyway, and a tug on an
        // otherwise-fine park reads as a hiccup. Real motion below clears
        // the give-up. Stalled FAR out (user holding the knob loaded):
        // keep the growing backoff (2/4/8s) so the spring reminds without
        // humming at 3V forever.
        if (fabsf(err) < 1.2f * sector) {
          s_retry_at = 0xFFFFFFFFu;
        } else {
          s_retry_at = nowu + s_backoff;
          if (s_backoff < 8000000u) s_backoff *= 2;
        }
      }
    } else {
      if (fabsf(w_det) > 1.0f && s_retry_at == 0xFFFFFFFFu) {
        s_retry_at = 0;        // the hand moved it: spring re-arms
      }
      uq = 0.0f;               // parked in the band: zero torque, silence
    }
    g_knob_target = g_knob.center;
  } break;

  default:
    uq = 0.0f;
    g_knob_target = th;
    break;
  }

  uq = clampf(uq, -g_knob.voltage_limit, g_knob.voltage_limit);
  g_knob_uq = uq;
  return uq;
}
