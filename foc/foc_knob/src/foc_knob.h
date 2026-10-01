// foc_knob.h - shared configuration for the AG32VF303 FOC force-feedback knob.
// Wiring is defined in foc_knob.ve (pad -> function); the GPIO port/bit pairs
// below must match it.
#ifndef FOC_KNOB_H
#define FOC_KNOB_H

#include <stdint.h>
#include <stdbool.h>

// ---------------- driver board pins (GPIO0, see foc_knob.ve) ----------------
#define DRV_GPIO          GPIO0
#define DRV_GPIO_MASK     APB_MASK_GPIO0
#define DRV_BIT_EN        GPIO_BIT0   // pad 10, active high
#define DRV_BIT_RESET     GPIO_BIT1   // pad 11, active low, idle high
#define DRV_BIT_SLEEP     GPIO_BIT2   // pad 12, active low, idle high
#define DRV_BIT_FAULT     GPIO_BIT3   // pad 13, input, active low

// ---------------- motor hall pins (GPIO0 bits 4..6 = pads 26/29/28) ---------
// (HV was on pad 27 = JTDO, owned by the debug TAP on AG32VFxxxK: input dead)
#define HALL_GPIO         GPIO0
#define HALL_BIT_U        GPIO_BIT4
#define HALL_BIT_V        GPIO_BIT5
#define HALL_BIT_W        GPIO_BIT6
#define HALL_BITS         (HALL_BIT_U | HALL_BIT_V | HALL_BIT_W)

// ---------------- power / motor parameters (tune here or via serial) --------
#define MOTOR_POLE_PAIRS  6.0f   // 9-slot gimbal motors are commonly 9N12P -> 6 pp;
                                 // wrong value only skews mechanical angle scale,
                                 // measure with the 'pp' serial command
#define VBUS_VOLTAGE      12.0f  // DC link voltage, used to normalise SVPWM

#define PWM_FREQ_HZ       20000u // 3-phase PWM frequency (center-aligned)

#define UQ_ALIGN_VOLT     2.5f   // open-loop alignment/drag voltage (1.5 was
                                 // marginal on the user's motor)
#define SPIN_UQ_CAP       3.0f   // closed-loop 'rot' torque cap [V]: must exceed
                                 // this motor's breakaway even with the worst
                                 // +/-30deg elec hall anchor error (0.87*3.0 >
                                 // the ~2.5V the open-loop drag needed)
#define SPIN_TRIM_KP      1.0f   // 'rot' position trim [1/s]: the field advances
                                 // kinematically (like the smooth cal drag) and
                                 // the hall position error only BENDS ITS RATE,
                                 // clamped to +-10% - a P loop on the 60deg-
                                 // quantized decode stick-slips violently, an
                                 // integrator-driven rate cannot kick the rotor
#define VOLT_LIMIT_DEFAULT 3.0f  // default |Uq| clamp [V] - keep small for gimbal motors

// IRQ priorities (PLIC, larger = more urgent)
#define IRQ_PRIO_GPIO     2
#define IRQ_PRIO_FOC      3

// ---------------- knob modes ----------------
enum {
  KNOB_FREE = 0,   // no torque
  KNOB_DAMP,       // viscous damping:        Uq = -kdamp * w
  KNOB_INERTIA,    // flywheel / slick feel:  Uq = +kiner * w
  KNOB_DETENT,     // ratchet detents: PD to nearest detent angle
  KNOB_BOUNDED,    // free inside range, springs back beyond the bounds
  KNOB_SPRING,     // spring back to center
  KNOB_MODE_COUNT
};

typedef struct {
  volatile int   mode;
  volatile float voltage_limit; // |Uq| clamp [V]
  // position modes (detent / bounded / spring)
  volatile float kp;            // [V/rad]
  volatile float kd;            // damping inside PD [V/(rad/s)]
  // velocity modes
  volatile float k_damp;        // damping gain  [V/(rad/s)]
  volatile float k_inertia;     // inertia gain  [V/(rad/s)]
  volatile float k_free;        // light damping inside bounded-mode free zone
  // geometry
  volatile float detents;       // legacy detent count/rev ('n' cmd) -> width
  volatile float bound_rad;     // bounded mode half-range [rad]
  volatile float center;        // center/zero position [rad, continuous]
  // SmartKnob-style detent engine (mode 3), port of scottbez1/smartknob
  // firmware/src/motor_task.cpp - parameters mirror PB_SmartKnobConfig
  volatile float det_width;     // position_width_radians [rad mech]; snapped
                                // to whole hall sectors inside the engine
  volatile float det_strength;  // detent_strength_unit, P = this * 4 V/rad
  volatile float end_strength;  // endstop_strength_unit, applied past bounds
  volatile float snap_point;    // crossing threshold x width [0.5..1.5],
                                // >0.5 required so adjacent detents cannot
                                // oscillate (SmartKnob validity rule)
  volatile float snap_bias;     // shifts the snap point away from position 0
  volatile int   pos_min;       // detent index bounds; pos_max < pos_min =
  volatile int   pos_max;       // unbounded (SmartKnob convention)
} KnobParams;

extern KnobParams g_knob;

// last knob decision, for telemetry / host-side debugging
extern volatile float g_knob_uq;     // commanded Uq after clamp [V]
extern volatile float g_knob_target; // position reference this pass [rad mech]
// rot drag field-angle override: while valid, foc_loop_irq applies THIS
// electrical angle instead of the hall decode (rate-locked drag, see knob.c)
extern volatile float g_knob_th;
extern volatile bool  g_knob_th_valid;

float knob_compute_uq(float mech_angle, float mech_vel, float dt);

// SmartKnob detent engine state, for telemetry: integer detent index and the
// fractional position inside the current detent (roughly -snap..+snap)
int32_t knob_detent_position(void);
float   knob_detent_subpos(void);
// re-arm the detent grid anchor - call after any command that teleports the
// hall decode ('z' angle zero, 'fl' commutation flip)
void    knob_detent_reanchor(void);

// one-shot rotation trajectory: while active it overrides all modes with a
// speed-ramped PD position move (closed-loop, uses hall). Host 'rot' command.
// Landing: arrival holds torque on the goal until the rotor stops moving
// (knob_spin_hold/settling/release), so it cannot coast past the target.
void  knob_spin_start(float from_rad, float goal_rad, float speed_rads);
void  knob_spin_stop(void);
bool  knob_spin_active(void);
bool  knob_spin_settling(void);   // arrived at goal, holding before release
void  knob_spin_hold(void);       // freeze reference, keep PD torque on goal
void  knob_spin_release(void);    // hand back to the knob mode
float knob_spin_goal(void);

#endif // FOC_KNOB_H
