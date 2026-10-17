#ifndef HAPTIC_H
#define HAPTIC_H

#include <stdint.h>

typedef enum
{
  HAPTIC_FREE = 0,
  HAPTIC_DAMP = 1,
  HAPTIC_INERTIA = 2,
  HAPTIC_DETENT = 3,
  HAPTIC_BOUNDED = 4,
  HAPTIC_MODE_COUNT
} haptic_mode_t;

typedef struct
{
  int     mode;
  float   k_damp;          /* damping command per rad/s */
  float   k_inertia;       /* flywheel command per rad/s */
  float   kp;              /* bounded-wall P per rad */
  float   kd;              /* bounded-wall D per rad/s */
  float   k_free;          /* free-zone damping per rad/s */
  float   det_width_rad;   /* native MT6701 detent width */
  float   det_strength;    /* dimensionless detent strength */
  float   end_strength;    /* dimensionless endstop strength */
  float   snap_point;      /* fraction of width, must be >= 0.5 */
  float   snap_bias;       /* home-side snap asymmetry */
  int32_t pos_min;
  int32_t pos_max;         /* pos_max < pos_min means unbounded */
  float   bound_rad;       /* bounded half-range */
  int32_t limit_pct;       /* percent of the global modulation vector */
} haptic_cfg_t;

extern haptic_cfg_t g_haptic_cfg;

void haptic_init(void);
void haptic_mode_enter(int mode, int64_t pos_raw);
void haptic_set_center(int64_t pos_raw);
void haptic_config_changed(int64_t pos_raw);
int  haptic_center_valid(void);
int64_t haptic_center_raw(void);

/* Pure control calculation. Position is the continuous 14-bit encoder count,
 * velocity is raw counts/s, and dt is the PWM ISR period in seconds. */
int32_t haptic_compute_q12(int64_t pos_raw, int32_t vel_rawps, float dt,
                           int32_t limit_q);
int32_t haptic_limit_q12(void);
float   haptic_target_rad(void);
float   haptic_relative_rad(int64_t pos_raw);
int32_t haptic_detent_position(void);
float   haptic_detent_subpos(void);
const char *haptic_mode_name(int mode);

#endif
