// main.c - AG32VF303KCU6 (QFN32) FOC force-feedback knob.
//
// Build:  pio run -e foc -t buildlogic   (after changing foc_knob.ve)
//         pio run -e foc -t logic        (flash logic bitstream)
//         pio run -e foc -t upload       (flash firmware)
// Serial: UART0 115200 (DAPLink CDC), commands with 'h'.
#include "alta.h"
#include "board.h"
#include "util.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

#include "foc_knob.h"
#include "pwm3ph.h"
#include "driver.h"
#include "hall.h"
#include "foc.h"

static char s_line[64];
static int  s_idx = 0;
static bool s_auto_status = true;
static float s_align_v = UQ_ALIGN_VOLT;   // calibration alignment voltage
static float s_rot_speed = 120.0f * (float)(M_PI / 180.0);  // rot slew [rad/s]
static float s_rot_cap = 0.0f;            // >0 after scan: rs may not exceed the
                                          // pace the halls were calibrated at
static uint32_t s_rot_t0 = 0;             // closed-loop rot start (timeout watch)
static int   s_tel_hz = 0;                // machine telemetry rate, 0 = off
static uint32_t s_next_tel = 0;
static uint32_t s_next_status = 0;
static uint32_t s_next_helz = 0;
static uint32_t s_loop_cnt_1s = 0;
static uint32_t s_loop_hz = 0;

static const char *mode_name(int m)
{
  static const char *names[KNOB_MODE_COUNT] = {
    "FREE", "DAMP", "INERTIA", "DETENT", "BOUNDED", "SPRING"
  };
  return (m >= 0 && m < KNOB_MODE_COUNT) ? names[m] : "?";
}

static void tel_emit(void);   // $T frame, also pumped inside the scan drag loop

static float wrap2pi(float x)
{
  return x - (float)(2.0 * M_PI) * floorf(x * (float)(1.0 / (2.0 * M_PI)));
}

static void print_help(void)
{
  printf("\n== AG32 FOC knob commands ==\n"
         " m0..m5   mode: 0 free 1 damp 2 inertia 3 detent 4 bounded 5 spring\n"
         " p        status once | s auto status on/off | st full state\n"
         " cal      hall calibration (motor will move, keep knob free!)\n"
         " scan     BETTER cal: open-loop drag 1 rev, measures halls (~8s)\n"
         " pp       measure pole pairs by hand (turn ONE full turn)\n"
         " ppset<f> set pole pairs (now %.1f)\n"
         " ua<f>    calib alignment voltage V (%.2f)\n"
         " rot[<deg>] rotate (default 360, neg=reverse; closed-loop if cal'd,\n"
         "          open-loop stepping otherwise; send 'rot' again to abort)\n"
         " rs<f>    rot speed deg/s (%.0f)\n"
         " kp<f> kd<f>  position P/D gains (%.2f / %.3f)\n"
         " df<f> fi<f> kf<f> damp/inertia/free-zone gains (%.3f/%.3f/%.3f)\n"
         " vl<f>    voltage limit V (%.2f)\n"
         " m3 detents (SmartKnob engine): dw<f> width deg (%.0f), n<f> = per rev\n"
         "   ds<f>/es<f> detent/endstop strength (%.1f/%.1f) | sp<f> snap pt (%.2f)\n"
         "   sb<f> home bias (%.2f) | pn<f>/px<f> bounds (%d/%d, px<pn = unbounded)\n"
         " br<f>    bound deg (%.1f) | cd set center here | z zero angle\n"
         " sl 0/1   driver sleep | en 0/1 driver enable | cl clear fault\n"
         " fl0/fl1  manual commutation flip (debug)\n"
         " hn<f>    hall noise filter cap, sectors/s (%.0f)\n"
         " tel<hz>  telemetry stream for host tool ($T CSV, 0=off, 50=charts)\n"
         "============================\n",
         MOTOR_POLE_PAIRS, s_align_v, s_rot_speed * (float)(180.0 / M_PI),
         hall_get_rate_cap(),
         g_knob.kp, g_knob.kd, g_knob.k_damp,
         g_knob.k_inertia, g_knob.k_free, g_knob.voltage_limit,
         g_knob.det_width * (float)(180.0 / M_PI),
         g_knob.det_strength, g_knob.end_strength,
         g_knob.snap_point, g_knob.snap_bias,
         g_knob.pos_min, g_knob.pos_max,
         g_knob.bound_rad * (float)(180.0 / M_PI));
}

static void print_status(void)
{
  float th = hall_mech_angle();
  float th_disp = fmodf(th, (float)(2.0 * M_PI));
  if (th_disp > (float)M_PI) th_disp -= (float)(2.0 * M_PI);
  if (th_disp < -(float)M_PI) th_disp += (float)(2.0 * M_PI);
  printf("[%s] ang=%6.1fdeg vel=%6.2frad/s hall=%d edges=%lu%s%s\n",
         mode_name(g_knob.mode), th_disp * (float)(180.0 / M_PI),
         hall_mech_velocity(), hall_state(),
         (unsigned long)hall_edges(),
         driver_fault() ? " FAULT" : "",
         foc_fault_latched() ? " FAULT_LATCH" : "");
}

// full hall calibration: align rotor at electrical 0, then open-loop sweep
// +120deg elec to detect hall sequence direction. Blocks ~1.5s.
static void do_calibrate(void)
{
  printf("cal: keep knob FREE, motor will move...\n");
  foc_ol_abort();                            // never resume a pending open-loop rot
  INT_DisableIRQ(GPTIMER0_IRQn);
  pwm3ph_outputs_enable(false);
  foc_set_enabled(false);
  driver_set_sleep(false);
  driver_enable(true);
  UTIL_IdleMs(50);

  printf("cal: align (rotating drag)\n");
  // Rotate the field a full electrical rev down to elec-0 and anchor on the
  // fly. A STATIC hold cannot break the rotor loose from cogging/static
  // friction, which left a random +-90deg error in the anchor (and therefore
  // random torque or a total lock) on every calibration.
  pwm3ph_outputs_enable(true);
  const int asteps = 180;                        // -450deg -> -90deg cmd: the
  const float a0cmd = -2.5f * (float)M_PI;       // field turns -360..0 elec
  for (int i = 0; i <= asteps; i++) {
    foc_apply(a0cmd + 2.0f * (float)M_PI * i / asteps, s_align_v);
    UTIL_IdleMs(6);
  }
  hall_begin_align();                            // field at 0, rotor dragged here

  printf("cal: sweep\n");
  const int steps = 90;
  const float sweep = (float)M_PI;                 // +180 deg elec = 3 sectors:
                                                   // direction unambiguous mod 6
  const float sweep0 = -(float)M_PI / 2.0f;        // continue from the align end
  for (int i = 1; i <= steps; i++) {
    foc_apply(sweep0 + sweep * (float)i / (float)steps, s_align_v);
    UTIL_IdleMs(6);
  }
  UTIL_IdleMs(200);
  pwm3ph_outputs_enable(false);
  foc_zero();

  int net = hall_sweep_net_dk();
  if (net == 0) {
    printf("cal FAILED: halls did not move. Check hall 3.3V/5V supply,\n"
           "pull-ups (4.7-10k to 3.3V) and HU/HV/HW wiring (pads 26/29/28).\n");
    GPIO_EnableInt(HALL_GPIO, HALL_BITS);
    INT_EnableIRQ(GPTIMER0_IRQn, IRQ_PRIO_FOC);   // keep rot/telemetry alive
    driver_enable(false);
    return;
  }
  if (net > 4 || net < -4) {
    printf("cal FAILED: noisy halls (net=%d). Add 4.7-10k pull-ups to 3.3V\n"
           "and keep hall wires away from phase wires, then retry.\n", net);
    GPIO_EnableInt(HALL_GPIO, HALL_BITS);
    INT_EnableIRQ(GPTIMER0_IRQn, IRQ_PRIO_FOC);
    driver_enable(false);
    return;
  }
  // NOTE: flip polarity verified empirically on the target motor: forward
  // drag with raw net counting DOWN needs flip=false (2026-09-30 bench test)
  bool flip = net > 0;
  hall_finish_calib(flip);
  printf("cal ok: sequence %s (net=%d steps)\n", flip ? "INVERTED" : "normal", net);

  // go live: FOC loop + outputs
  foc_init();   // reset loop dt baseline
  // post-cal the FOC loop decodes the hall pins synchronously (glimmune to
  // PWM-coupled glitches); kill the async edge ISR so it can't snap position
  GPIO_DisableInt(HALL_GPIO, HALL_BITS);
  GPTIMER_EnableIntUpdate(GPTIMER0);
  INT_EnableIRQ(GPTIMER0_IRQn, IRQ_PRIO_FOC);
  foc_set_enabled(true);
  pwm3ph_outputs_enable(true);
  printf("FOC live (mode %s). Motor is limp in FREE mode.\n",
         mode_name(g_knob.mode));
}

// scan calibration: open-loop drag one full mechanical revolution while
// recording raw hall transitions. The drag schedule IS the electrical-angle
// ground truth, so sector order, direction and anchor are all MEASURED, not
// assumed - the align+sweep 'cal' guessed the anchor from one holding point
// (cogging broke the hold -> random +-90deg error) and needed a flip heuristic.
static void do_scan_cal(void)
{
  const float D60 = (float)(M_PI / 3.0);   // one hall sector, electrical rad
  if (driver_fault()) { printf("scan: driver FAULT, 'cl' first\n"); return; }
  printf("scan: keep knob FREE, open-loop drag 1 rev (~7s)...\n");
  foc_ol_abort();                            // never resume a pending open-loop rot
  INT_DisableIRQ(GPTIMER0_IRQn);
  pwm3ph_outputs_enable(false);
  foc_set_enabled(false);
  driver_set_sleep(false);
  driver_enable(true);
  UTIL_IdleMs(50);
  // THE fix vs the first scan attempt: the drag needs the phase outputs ON.
  // Without this the CCRs rotated but MOE stayed off, the rotor never moved
  // and the scan "found" a frozen motor (misread back then as a dead 12V).
  pwm3ph_outputs_enable(true);
  GPIO_DisableInt(HALL_GPIO, HALL_BITS);   // poll decode only: glitch immune
  hall_reset_decode();
  hall_scan_begin();

  const float step = (float)(2.0 * M_PI) / 180.0f;          // 2 deg elec/tick
  const float th_start = -(float)M_PI / 2.0f;               // pick up from behind
  const float th_end = 2.0f * (float)M_PI * hall_get_pp();  // = 1 mech rev
  const int ticks = (int)((th_end - th_start) / step);
  uint32_t t_next = UTIL_GetUSec();
  float th = th_start;
  for (int i = 0; i < ticks; i++) {
    foc_apply(th, s_align_v);
    th += step;
    hall_scan_note_step((uint32_t)i);      // commits map to THIS field angle
    hall_update(0.006f);
    if ((i % 10) == 0) tel_emit();         // host stays live during calibration
    if ((i % 375) == 0) printf("scan: %d%%\n", i * 100 / ticks);
    t_next += 6000u;                       // exact 6ms ticks: the drag schedule
    while ((int32_t)(UTIL_GetUSec() - t_next) < 0) { }  // doubles as the clock
  }
  UTIL_IdleMs(200);                        // settle: rotor locked at elec -load
  int k_now_raw = hall_state();            // read while the field still holds
  hall_scan_end();
  const float th_last = th_start + step * (float)(ticks - 1);

  // scan-failure exit: outputs off, limp, and give the hall/GPTIMER irqs back
  // so 'cal' and the non-blocking 'rot' keep working afterwards
#define SCAN_FAIL(msg...) do {                     \
    GPIO_EnableInt(HALL_GPIO, HALL_BITS);          \
    INT_EnableIRQ(GPTIMER0_IRQn, IRQ_PRIO_FOC);    \
    pwm3ph_outputs_enable(false);                  \
    driver_enable(false);                          \
    printf(msg);                                   \
    return;                                        \
  } while (0)

  // ---- direction: votes along the unique 3-bit gray cycle 1,3,2,6,4,5 ----
  static const int8_t cyc[6] = {1, 3, 2, 6, 4, 5};
  int idx8[8];
  for (int j = 0; j < 8; j++) idx8[j] = -1;
  for (int j = 0; j < 6; j++) idx8[cyc[j]] = j;
  int n = hall_scan_count();
  int fwd = 0, bwd = 0, odd = 0, prev = -1;
  for (int i = 0; i < n; i++) {
    int r; uint32_t idx;
    hall_scan_get(i, &r, &idx);
    if (prev >= 0 && idx8[r] >= 0 && idx8[prev] >= 0) {
      int dd = (idx8[r] - idx8[prev] + 6) % 6;
      if (dd == 1) fwd++;
      else if (dd == 5) bwd++;
      else odd++;
    }
    prev = r;
  }
  printf("scan: %d commits, fwd=%d bwd=%d odd=%d net=%d (~37 = 1 rev + lead-in)\n",
         n, fwd, bwd, odd, fwd - bwd);
  int8_t map[8];
  for (int j = 0; j < 8; j++) map[j] = -1;
  if (fwd + bwd < 20 || odd > (fwd + bwd) / 3 || fwd == bwd) {
    SCAN_FAIL("scan FAILED: inconsistent hall sequence (fwd=%d bwd=%d odd=%d).\n"
              "Add 4.7-10k pull-ups to 3.3V, keep hall wires off phase wires.\n",
              fwd, bwd, odd);
  }
  if (fwd > bwd) { for (int j = 0; j < 6; j++) map[cyc[j]] = j; }
  else           { for (int j = 0; j < 6; j++) map[cyc[5 - j]] = j; }

  // ---- load angle: theta_cmd minus rotor theta at clean forward crossings ----
  float offs[96];
  int no = 0;
  int prev_k = -1;
  for (int i = 0; i < n; i++) {
    int r; uint32_t idx;
    hall_scan_get(i, &r, &idx);
    int k = map[r];
    if (k < 0) continue;
    if (prev_k >= 0 && i >= 2 && ((k - prev_k + 6) % 6) == 1) {
      float th_cmd = th_start + step * (float)idx;   // field angle at that tick
      float o = th_cmd - (float)k * D60;         // = load angle mod 60deg
      o -= D60 * floorf(o / D60);
      if (no < 96) offs[no++] = o;
    }
    prev_k = k;
  }
  if (no < 15) {
    SCAN_FAIL("scan FAILED: only %d clean forward steps\n", no);
  }
  // modal 5deg bin + circular mean within +-5deg: rejects slipped commits
  int bin[12] = {0};
  for (int i = 0; i < no; i++) {
    int b = (int)(offs[i] * (12.0f / D60));
    if (b < 0) b = 0;
    if (b > 11) b = 11;
    bin[b]++;
  }
  int bmax = 0;
  for (int b = 1; b < 12; b++) if (bin[b] > bin[bmax]) bmax = b;
  float sx = 0.0f, sy = 0.0f;
  int used = 0;
  for (int i = 0; i < no; i++) {
    float d = offs[i] - (float)(bmax + 0.5) * (D60 / 12.0f);
    d -= D60 * floorf(d / D60 + 0.5f);
    if (fabsf(d) <= D60 / 6.0f) { sx += cosf(offs[i]); sy += sinf(offs[i]); used++; }
  }
  float delta = atan2f(sy, sx);                  // load angle mod 60, [0,60)
  if (delta < 0.0f) delta += D60;
  float quality = (used > 0) ? sqrtf(sx * sx + sy * sy) / used : 0.0f;

  // Anchor: trust the PINS for the sector (always reliable, even after the
  // rotor relaxed across an edge when the field stopped - static friction <
  // dynamic, cogging pulls it to a new detent) and let the sector-centered
  // decode convention in hall_scan_apply bound the residual error to
  // +/-30deg elec. The delta-based estimate is only cross-checked: more than
  // one sector off = the rotor was really disturbed -> fail.
  int k_pin = map[k_now_raw];
  if (k_pin < 0) {
    SCAN_FAIL("scan FAILED: illegal hall state %d at drag end\n", k_now_raw);
  }
  float rot_e = wrap2pi(th_last - delta);
  int k_est = (int)(rot_e / D60);
  int kdiff = k_pin - k_est;
  if (kdiff > 3) kdiff -= 6; else if (kdiff < -3) kdiff += 6;
  if (kdiff < -1 || kdiff > 1) {
    SCAN_FAIL("scan FAILED: anchor inconsistent (field says k=%d, pins say k=%d)\n",
              k_est, k_pin);
  }
  float pos0 = (float)k_pin;               // entry convention, decode is centered
  hall_scan_apply(map, pos0);

  printf("scan ok: fwd order ");
  for (int j = 0; j < 6; j++)
    for (int r = 0; r < 8; r++) if (map[r] == j) printf("%d", r);
  printf(" net=%d load=%.1fdeg anchor k=%d(est %d) pos0=%.2f q=%.2f\n",
         fwd - bwd, delta * (float)(180.0 / M_PI), k_pin, k_est, pos0, quality);
  if (fwd - bwd < 34 || fwd - bwd > 39)
    printf("scan NOTE: net=%d, expected ~37 for 1 rev at pp=%.1f (the drag\n"
           "sweeps 90deg elec of lead-in, so 36-38 is normal; gross mismatch\n"
           "= wrong pp, rescan after 'ppset <n>').\n", fwd - bwd, hall_get_pp());

  // go live, same handover as 'cal'
  foc_init();
  GPTIMER_EnableIntUpdate(GPTIMER0);
  INT_EnableIRQ(GPTIMER0_IRQn, IRQ_PRIO_FOC);
  foc_set_enabled(true);
  pwm3ph_outputs_enable(true);
  // closed-loop rot must never outrun the open-loop drag the halls were
  // calibrated at (user requirement): cap the rot slew at the drag pace
  s_rot_speed = 50.0f * (float)(M_PI / 180.0f);
  s_rot_cap = 50.0f;
  printf("FOC live (mode %s). rot speed capped to 50 deg/s (drag pace).\n",
         mode_name(g_knob.mode));
}

// pole pairs: count hall electrical revolutions while user turns one mech rev
static void measure_pp(void)
{
  printf("pp: turn the knob ONE full turn (either direction), 6s window...\n");
  int dk0 = hall_sweep_net_dk();
  UTIL_IdleMs(6000);
  int dk1 = hall_sweep_net_dk();
  int steps = dk1 - dk0;
  float elec_revs = fabsf((float)steps) / 6.0f;
  printf("pp: steps=%d -> %.2f electrical revs -> pole pairs ~ %.1f\n",
         steps, elec_revs, elec_revs);
  printf("pp: if this equals 6.0 keep default; else 'ppset <value>'\n");
}

// one-shot rotation by deg mechanical degrees ('rot' command).
// Closed-loop speed-ramped trajectory when FOC is live; otherwise the
// GPTIMER0 irq steps the electrical angle open-loop. Both are NON-BLOCKING:
// the main loop keeps polling UART and streaming $T telemetry, so hall states
// stay visible in the host tool for the whole rotation.
static void do_rotate(float deg)
{
  if (knob_spin_active()) { knob_spin_stop(); printf("rot aborted\n"); return; }
  if (foc_ol_active()) {
    foc_ol_abort();
    pwm3ph_outputs_enable(false);
    driver_enable(false);
    printf("rot aborted\n");
    return;
  }
  if (driver_fault()) { printf("rot: driver FAULT, 'cl' first\n"); return; }

  if (foc_enabled() && hall_state_valid()) {
    if (driver_sleeping()) { printf("rot: driver asleep, 'sl0' first\n"); return; }
    float th0 = hall_mech_angle();
    s_rot_t0 = board_millis();
    knob_spin_start(th0, th0 + deg * (float)(M_PI / 180.0), s_rot_speed);
    printf("rot: %.0f deg @ %.0f deg/s closed-loop ('rot' aborts)\n",
           deg, s_rot_speed * (float)(180.0 / M_PI));
    return;
  }

  // open-loop fallback: pp is only known as a setting, sweep at cal voltage
  if (driver_sleeping()) { printf("rot: driver asleep, 'sl0' first\n"); return; }
  driver_set_sleep(false);
  driver_enable(true);
  UTIL_IdleMs(50);
  pwm3ph_outputs_enable(true);
  float dir = (deg >= 0.0f) ? 1.0f : -1.0f;
  float total_e = fabsf(deg) * (float)(M_PI / 180.0) * hall_get_pp();
  float rate_e  = dir * s_rot_speed * hall_get_pp();  // mech -> electrical rad/s
  foc_ol_start(total_e, rate_e, s_align_v);
  printf("rot: %.0f deg OPEN-LOOP @ %.0f deg/s, %.1fs (non-blocking, 'rot' aborts)\n",
         deg, s_rot_speed * (float)(180.0 / M_PI),
         fabsf(deg) * (float)(M_PI / 180.0) / s_rot_speed);
}

static void process_line(char *line)
{
  char tok[16] = "";
  float val = 0.0f;
  int n = sscanf(line, "%15s %f", tok, &val);
  if (n < 1 || tok[0] == 0) return;

  if (tok[0] == 'm' && tok[1] >= '0' && tok[1] <= '9' && tok[2] == 0) {
    int m = tok[1] - '0';
    if (m < KNOB_MODE_COUNT) {
      g_knob.mode = m;
      printf("mode %d = %s\n", m, mode_name(m));
    }
    return;
  }
  if (!strcmp(tok, "h") || !strcmp(tok, "help")) { print_help(); return; }
  if (!strcmp(tok, "p"))  { print_status(); return; }
  if (!strcmp(tok, "s"))  { s_auto_status = !s_auto_status;
                            printf("auto status %s\n", s_auto_status ? "on" : "off"); return; }
  if (!strcmp(tok, "st")) {
    printf("mode=%s pp=%.1f loop=%luHz hallstate=%d edges=%lu fault=%d latch=%d sleep=%d\n",
           mode_name(g_knob.mode), MOTOR_POLE_PAIRS, (unsigned long)s_loop_hz,
           hall_state(), (unsigned long)hall_edges(), driver_fault(),
           foc_fault_latched(), driver_sleeping());
    printf("knob: kp=%.2f kd=%.3f df=%.3f fi=%.3f kf=%.3f vl=%.2f\n"
           "knob: dw=%.1fdeg ds=%.1f es=%.1f sp=%.2f sb=%.2f pn=%d px=%d br=%.1f ua=%.2f rs=%.0f\n",
           g_knob.kp, g_knob.kd, g_knob.k_damp, g_knob.k_inertia, g_knob.k_free,
           g_knob.voltage_limit,
           g_knob.det_width * (float)(180.0 / M_PI), g_knob.det_strength,
           g_knob.end_strength, g_knob.snap_point, g_knob.snap_bias,
           g_knob.pos_min, g_knob.pos_max,
           g_knob.bound_rad * (float)(180.0 / M_PI), s_align_v,
           s_rot_speed * (float)(180.0 / M_PI));
    return;
  }
  if (!strcmp(tok, "cal")) { do_calibrate(); return; }
  if (!strcmp(tok, "scan")) { do_scan_cal(); return; }
  if (!strcmp(tok, "pp"))  { measure_pp(); return; }
  if (!strcmp(tok, "cl"))  { foc_clear_fault();
                             if (!driver_fault()) pwm3ph_outputs_enable(true);
                             printf("fault cleared\n"); return; }
  if (!strcmp(tok, "fl"))  { bool f = val > 0.5f; hall_set_flip(f);
                             knob_detent_reanchor();
                             printf("flip=%d re-anchored (test 'rot 60')\n", f); return; }
  if (!strcmp(tok, "z"))   { hall_reset_origin(); g_knob.center = 0.0f;
                             knob_detent_reanchor();
                             printf("angle zeroed\n"); return; }
  if (!strcmp(tok, "cd"))  { g_knob.center = hall_mech_angle();
                             printf("center = %.2f rad\n", g_knob.center); return; }
  if (!strcmp(tok, "rot")) { do_rotate((n >= 2 && val != 0.0f) ? val : 360.0f);
                             return; }

  if (!strcmp(tok, "sl"))  { bool sl = val > 0.5f; driver_set_sleep(sl);
                             printf("sleep %d\n", sl); return; }
  if (!strcmp(tok, "en"))  { bool en = val > 0.5f; driver_enable(en);
                             if (!en) { foc_ol_abort(); pwm3ph_outputs_enable(false); }
                             printf("driver enable %d\n", en); return; }

  if (n >= 2) {
    if (!strcmp(tok, "tel")) {
      if (val < 0.0f) val = 0.0f;
      if (val > 200.0f) val = 200.0f;
      s_tel_hz = (int)val;
      printf("telemetry %d Hz\n", s_tel_hz);
      return;
    }
    if (!strcmp(tok, "ua")) {
      if (val < 0.3f) val = 0.3f;
      if (val > VBUS_VOLTAGE * 0.3f) val = VBUS_VOLTAGE * 0.3f;
      s_align_v = val; printf("align voltage=%.2fV\n", val); return;
    }
    if (!strcmp(tok, "rs")) {
      if (val < 10.0f) val = 10.0f;
      if (val > 720.0f) val = 720.0f;
      bool capped = (s_rot_cap > 0.0f && val > s_rot_cap);
      if (capped) val = s_rot_cap;   // closed-loop must not outrun the open-loop
      s_rot_speed = val * (float)(M_PI / 180.0);   // drag the halls were
      printf("rot speed=%.0f deg/s%s\n", val,    // calibrated at (user req.)
             capped ? " (scan cap)" : "");
      return;
    }
    if (!strcmp(tok, "hn")) {
      hall_set_rate_cap(val);
      printf("hall rate cap=%.0f sect/s (~%.1f rev/s max tracking)\n",
             val, val / (6.0f * MOTOR_POLE_PAIRS));
      return;
    }
    if (!strcmp(tok, "ppset")) { hall_set_pp(val); printf("pp=%.1f\n", val); return; }
    if (!strcmp(tok, "kp")) { g_knob.kp = val; printf("kp=%.3f\n", val); return; }
    if (!strcmp(tok, "kd")) { g_knob.kd = val; printf("kd=%.4f\n", val); return; }
    if (!strcmp(tok, "df")) { g_knob.k_damp = val; printf("k_damp=%.4f\n", val); return; }
    if (!strcmp(tok, "fi")) { g_knob.k_inertia = val; printf("k_inertia=%.4f\n", val); return; }
    if (!strcmp(tok, "kf")) { g_knob.k_free = val; printf("k_free=%.4f\n", val); return; }
    if (!strcmp(tok, "vl")) {
      if (val < 0.2f) val = 0.2f;
      if (val > VBUS_VOLTAGE * 0.57f) val = VBUS_VOLTAGE * 0.57f;
      g_knob.voltage_limit = val; printf("voltage_limit=%.2f\n", val); return;
    }
    if (!strcmp(tok, "n"))  { if (val < 1.0f) val = 1.0f;
                              g_knob.det_width = (float)(2.0 * M_PI) / val;
                              printf("detents=%.0f -> width %.1f deg\n", val,
                                     g_knob.det_width * (float)(180.0 / M_PI));
                              return; }
    if (!strcmp(tok, "dw")) { if (val < 2.0f) val = 2.0f;
                              if (val > 120.0f) val = 120.0f;
                              g_knob.det_width = val * (float)(M_PI / 180.0);
                              printf("detent width=%.0f deg (snapped to hall sectors)\n",
                                     val); return; }
    if (!strcmp(tok, "ds")) { if (val < 0.0f) val = 0.0f;
                              if (val > 6.0f) val = 6.0f;
                              g_knob.det_strength = val;
                              printf("detent strength=%.2f\n", val); return; }
    if (!strcmp(tok, "es")) { if (val < 0.0f) val = 0.0f;
                              if (val > 6.0f) val = 6.0f;
                              g_knob.end_strength = val;
                              printf("endstop strength=%.2f\n", val); return; }
    if (!strcmp(tok, "sp")) { if (val < 0.5f) val = 0.5f;
                              if (val > 1.5f) val = 1.5f;
                              g_knob.snap_point = val;
                              printf("snap point=%.2f\n", val); return; }
    if (!strcmp(tok, "sb")) { if (val < 0.0f) val = 0.0f;
                              if (val > 0.4f) val = 0.4f;
                              g_knob.snap_bias = val;
                              printf("snap bias=%.2f\n", val); return; }
    if (!strcmp(tok, "pn")) { if (val < -64.0f) val = -64.0f;
                              if (val > 64.0f) val = 64.0f;
                              g_knob.pos_min = (int)val;
                              printf("pos min=%d\n", (int)val); return; }
    if (!strcmp(tok, "px")) { if (val < -64.0f) val = -64.0f;
                              if (val > 64.0f) val = 64.0f;
                              g_knob.pos_max = (int)val;
                              printf("pos max=%d\n", (int)val); return; }
    if (!strcmp(tok, "br")) { g_knob.bound_rad = val * (float)(M_PI / 180.0);
                              printf("bound=%.1f deg\n", val); return; }
  }
  printf("unknown cmd ('h' for help)\n");
}

// one machine telemetry frame ($T CSV) for the host tool. Called from the main
// loop at the 'tel' rate AND from inside the scan drag loop, so the host keeps
// seeing live hall states even while calibration rotation is running.
static void tel_emit(void)
{
  float th = hall_mech_angle();
  int flags = (driver_fault() ? 1 : 0) | (foc_fault_latched() ? 2 : 0) |
              (driver_sleeping() ? 4 : 0) | (!hall_state_valid() ? 8 : 0) |
              (foc_enabled() ? 16 : 0);
  // $T,mode,ang(cdeg),vel(mrad/s),uq(mV),target(cdeg),hall,flags,loop_hz,
  //    pos,subpos(x100)   <- detent engine state (mode 3; 0 elsewhere)
  printf("$T,%d,%ld,%ld,%ld,%ld,%d,%d,%lu,%ld,%ld\n",
         g_knob.mode,
         (long)(th * 5729.57795f),
         (long)(hall_mech_velocity() * 1000.0f),
         (long)(g_knob_uq * 1000.0f),
         (long)(g_knob_target * 5729.57795f),
         hall_state(), flags, (unsigned long)s_loop_hz,
         (long)knob_detent_position(),
         (long)(knob_detent_subpos() * 100.0f));
}

static void poll_uart(void)
{
  while (!UART_IsRxFifoEmpty(UART0)) {
    char c = (char)UART_ReceiveData(UART0);
    if (c == '\r' || c == '\n') {
      if (s_idx > 0) {
        s_line[s_idx] = 0;
        putchar('\n');
        process_line(s_line);
        s_idx = 0;
      }
    } else if (c == 8 || c == 127) {          // backspace
      if (s_idx > 0) { s_idx--; printf("\b \b"); }
    } else if (s_idx < (int)sizeof(s_line) - 1) {
      s_line[s_idx++] = c;
      putchar(c);                              // echo
    }
  }
}

int main(void)
{
  board_init();
  INT_SetIRQThreshold(1);                      // PLIC_MIN_PRIORITY

  driver_init();
  foc_init();
  hall_init();
  pwm3ph_init(PWM_FREQ_HZ);
  // FOC update irq runs from boot (foc disabled = zero vector): it drives the
  // non-blocking open-loop 'rot' and keeps hall decode + telemetry live even
  // before any calibration. cal/scan toggle it around their blocking drags.
  GPTIMER_EnableIntUpdate(GPTIMER0);
  INT_EnableIRQ(GPTIMER0_IRQn, IRQ_PRIO_FOC);

  printf("\n=== AG32VF303 FOC force-feedback knob ===\n");
  printf("pclk=%uHz pwm=%uHz arr=%u\n", (unsigned)SYS_GetPclkFreq(),
         (unsigned)PWM_FREQ_HZ, (unsigned)pwm3ph_arr());
  printf("wiring: IN1/2/3=pad7/8/9 EN=10 RST=11 SLP=12 FAULT=13 halls=26/29/28\n");
  printf("type 'cal' to calibrate, 'h' for commands.\n");
  print_help();

  s_next_helz = board_millis();
  while (1) {
    poll_uart();

    uint32_t now = board_millis();
    if ((int32_t)(now - s_next_helz) >= 0) {   // once per second
      s_next_helz = now + 1000;
      s_loop_hz = foc_loop_count() - s_loop_cnt_1s;
      s_loop_cnt_1s = foc_loop_count();
    }
    if (foc_ol_pop_done()) {                   // open-loop rot finished
      pwm3ph_outputs_enable(false);
      foc_zero();
      driver_enable(false);                    // un-calibrated: leave it limp
      printf("rot done\n");
    }
    if (knob_spin_active()) {                  // closed-loop rot tracking/landing
      static uint32_t s_stall_t = 0;           // ms window without progress
      static float    s_stall_th = 0.0f;
      static uint32_t s_settle_t = 0;
      static uint32_t s_ref_goal_t = 0;        // since the ramp reference arrived
      float remain = knob_spin_goal() - hall_mech_angle();
      if (knob_spin_settling()) {
        // hold phase: knob.c keeps torque on the goal; release only once
        // the rotor is truly stopped (releasing instantly = coast overshoot),
        // or after a grace period if it will not fully settle
        if (fabsf(hall_mech_velocity()) < 0.05f ||
            (int32_t)(now - s_settle_t) > 800) {
          knob_spin_release();
          if (g_knob.mode == KNOB_SPRING || g_knob.mode == KNOB_BOUNDED)
            g_knob.center = hall_mech_angle(); // don't let spring unwind the turn
          printf("rot done\n");
        }
      } else {
        if (foc_fault_latched()) {             // ISR stopped steering the drag
          knob_spin_stop();
          printf("rot ABORT: driver fault latched, 'cl' + recal\n");
        } else {
        // the hall decode is quantized to one 10deg-mech sector at crawl
        // speed (no edge interpolation), so "arrived" means the goal's SECTOR
        // near standstill. Fallback: reference at the goal for 2s AND the
        // rotor within two sectors - the reference ALWAYS arrives (it is
        // kinematic), so an unconditional fallback would declare victory
        // wherever the rotor happens to be stuck.
        float half_sec = (float)M_PI / (6.0f * hall_get_pp());
        bool ref_at_goal = fabsf(knob_spin_goal() - g_knob_target) < 0.01f;
        if (ref_at_goal) {
          if (s_ref_goal_t == 0) s_ref_goal_t = now;
        } else {
          s_ref_goal_t = 0;
        }
        bool close = fabsf(remain) < half_sec &&
                     fabsf(hall_mech_velocity()) < 0.15f;
        if ((close && ref_at_goal) ||
            (ref_at_goal && fabsf(remain) < 2.0f * half_sec &&
             (int32_t)(now - s_ref_goal_t) > 2000)) {
          knob_spin_hold();                    // keep torque on, no coasting
          s_settle_t = now;
          s_ref_goal_t = 0;
          s_stall_t = 0;
        } else {
          // stall guard only MID-RUN: once the ramp reference is within a
          // half sector of the goal the crawl is intentionally slow and the
          // rotor legitimately barely moves - aborting there killed runs that
          // were already sitting on the target. The landing is covered by the
          // arrival check, the 2s ref-at-goal fallback and the 30s timeout.
          bool landing = fabsf(knob_spin_goal() - g_knob_target) < 0.09f;
          if (!landing && fabsf(g_knob_uq) > 1.0f) {
            if (s_stall_t == 0 || fabsf(hall_mech_angle() - s_stall_th) > 0.10f) {
              s_stall_t = now;                  // progress: restart the window
              s_stall_th = hall_mech_angle();
            } else if ((int32_t)(now - s_stall_t) > 3000) {
              knob_spin_stop();
              printf("rot ABORT: pushing but rotor stuck (hall noise?) -\n"
                     "check pull-ups 4.7-10k + hall wiring, 'cl', recal\n");
              s_stall_t = 0;
            }
          } else {
            s_stall_t = 0;
          }
          if ((int32_t)(now - s_rot_t0) > 30000) {
            knob_spin_stop();                    // stalled: stop pushing
            printf("rot timeout, stopped\n");
            s_stall_t = 0;
          }
        }
        }
      }
    }
    if (s_tel_hz > 0 && (int32_t)(now - s_next_tel) >= 0) {
      s_next_tel = now + (uint32_t)(1000 / s_tel_hz);
      tel_emit();
    }
    if (s_auto_status && (int32_t)(now - s_next_status) >= 0) {
      s_next_status = now + 400;
      print_status();
    }
  }
  return 0;
}
