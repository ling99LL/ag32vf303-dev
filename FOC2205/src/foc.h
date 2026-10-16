// foc.h — FOC voltage-mode loop skeleton + hand-feel parameter hooks
//
// The knob's feel (手感) is tuned through the params below; the electrical loop
// runs in the GPTIMER0 update ISR: sample currents (quasi-simultaneous) and
// angle (SSI) at the PWM valley, then update the three CCRs.
#ifndef FOC_H
#define FOC_H

#include <stdint.h>

typedef struct
{
  // electrical
  int32_t voltage_d_q;          // d-axis modulation command; normally zero
  int32_t v_limit_q;            // normalization reference (8192); not measured volts
  uint16_t pole_pairs;
  float zero_electric_angle;    // P1-1 修复：标定的电角度初相偏置 (rad)
  int8_t sensor_direction;      // 传感器与电机旋转方向 (+1 或 -1)
  float angle_filt_alpha;       // 换向角低通系数 (0,1]；1.0 = 不滤波
  // Direct electrical-angle hook for hybrid and open-loop commutation.
  uint8_t comm_override;
  float   comm_angle_e;
  // hand-feel layer outputs (filled by the knob logic, consumed here)
  int32_t torque_q;             // q-axis modulation command, Q12
  uint8_t brake;                // 1 = short phases (parking brake)
  // inner current loop (voltage mode is the fallback while disabled)
  uint8_t current_loop;         // 1 = PI closes on measured id/iq
  float   cur_kp;               // proportional: modulation LSB per current LSB
  float   cur_ki;               // integral gain per second (mod LSB / (LSB*s))
  int32_t cur_ref_div;          // iq_ref = torque_q / cur_ref_div (Q12 -> LSB)
  float   cur_filt_alpha;       // LPF on id/iq feedback; (0,1], 1 = raw
  int32_t cur_v_cap;            // PI output clamp in modulation LSB (4096 = 100%)
} foc_params_t;

extern foc_params_t g_foc;

// 对齐探测：施加 +90 度电矢量前后读到的 raw 电角度差（rad，已 wrap 到 [0,2pi)）。
// 正向应 ≈ 1.571 (+90 度)，反向应 ≈ 4.712 (270 度 = -90 度)。诊断方向判定用。
extern float g_align_delta;

// ---- over-current telemetry: real over-current vs sampling glitch ----
// Trip only after FOC_OC_TRIP_COUNT consecutive full-rate (20 kHz) samples stay
// over CURRENT_TRIP_LSB. Isolated over-threshold samples are counted and their
// pre-trip window frozen instead of aborting the move on one corrupted read.
#ifndef FOC_OC_TRIP_COUNT
#define FOC_OC_TRIP_COUNT 3
#endif
#define FOC_OC_SNAP 8

typedef struct
{
  int16_t  pk_a, pk_b, pk_c;     // signed extreme by |i| since reset (LSB)
  uint32_t events;               // over-threshold samples since reset
  uint32_t max_run;              // longest consecutive over-threshold run
  uint32_t glitches;             // runs of exactly one sample (isolated)
  int16_t  last_a, last_b, last_c; // newest sample
  uint8_t  snap_kind;            // 0 none, 1 glitch, 2 consecutive trip
  uint8_t  snap_mask;            // over phases in the frozen sample (bit0..2 = A..C)
  uint8_t  snap_run;             // consecutive count at freeze
  uint8_t  snap_n;               // valid samples in snap (FOC_OC_SNAP when filled)
  int16_t  snap[FOC_OC_SNAP][3]; // pre/freeze samples, oldest first
} foc_oc_t;

void foc_oc_reset(void);
void foc_oc_get(foc_oc_t *out);

// ---- inner current loop ----
void foc_current_loop_enable(int on); // switch only from standby with outputs off
int  foc_current_loop_enabled(void);
void foc_last_dq(int16_t *d, int16_t *q); // filtered id/iq, LSB
int32_t foc_last_iq_ref(void);            // latest iq reference (0 in voltage mode)

void foc_init(uint16_t pole_pairs);
int  foc_align_sensor(void);    // 1 only after valid angle and direction calibration
// Called from the PWM update ISR
void foc_step_isr(void);
// Read-only status for diagnostics
int32_t foc_last_angle(void);
uint32_t foc_crc_errors(void);
uint32_t foc_crc_consecutive(void);
uint32_t foc_adc_errors(void);
uint32_t foc_adc_consecutive(void);
int foc_angle_valid(void);      // latest frame, not just a historical good sample
int foc_current_valid(void);    // ADC completion only; calibration is separate
uint8_t foc_sensor_status(void);// meaningful only when foc_angle_valid()
// Only call after a fresh, valid encoder frame and ADC calibration with PWM off.
void foc_clear_sensor_faults(void);
// 只读 accessor（纯读取，不触碰任何控制逻辑）——上位机要显示三相电流
void foc_last_currents(int16_t *a, int16_t *b, int16_t *c);

#endif
