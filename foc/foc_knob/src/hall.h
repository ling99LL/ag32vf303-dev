#ifndef HALL_H
#define HALL_H
#include <stdint.h>
#include <stdbool.h>

// Motor hall sensors HU/HV/HW on GPIO0 bits 4..6 (pads 26/27/28, foc_knob.ve).
// Electrical angle = 60deg sector decoding + interpolation between hall edges
// (SimpleFOC HallSensor method). No absolute fine angle: worst-case constant
// torque-angle error is +/-30deg electrical, which is fine for a knob.

void hall_init(void);          // inputs + both-edge GPIO interrupts
void hall_isr(void);           // hall edge work, called from GPIO0_isr
void hall_update(float dt);    // interpolation + velocity estimate, from FOC loop

float hall_electrical_angle(void); // rotor electrical angle [rad, 0..2pi)
float hall_mech_angle(void);       // continuous mechanical angle [rad]
float hall_mech_angle_raw(void);   // staircase-only angle, no interpolation
float hall_mech_velocity(void);    // mechanical speed [rad/s]
int   hall_state(void);            // raw 3-bit hall state 0..7
bool  hall_state_valid(void);      // false for illegal 000/111 states
uint32_t hall_edges(void);

// calibration (called from main context while FOC irq is off)
void hall_begin_align(void);       // rotor is held at electrical 0: snapshot anchor
int  hall_sweep_net_dk(void);      // net sector steps accumulated since begin_align
void hall_finish_calib(bool flip); // latch direction flip, reset mech origin
void hall_set_flip(bool flip);     // manual flip override (re-anchors origin)
void hall_set_pp(float pp);        // pole pairs (mech angle scale + velocity)
float hall_get_pp(void);           // current pole pairs (open-loop rot scaling)
void hall_set_rate_cap(float cap); // hall noise filter: max accepted sectors/s
float hall_get_rate_cap(void);
void hall_reset_origin(void);      // zero the continuous mechanical angle here

// scan calibration: an open-loop drag records raw hall commits; main.c learns
// sector order, direction and anchor from the drag schedule itself (measured,
// not assumed like the align+sweep 'cal')
void hall_reset_decode(void);                          // fresh decode state
void hall_scan_begin(void);                            // record accepted commits
void hall_scan_note_step(uint32_t idx);                // main.c: current drag step
void hall_scan_end(void);
int  hall_scan_count(void);
bool hall_scan_get(int i, int *raw, uint32_t *idx);    // raw state, drag step no
void hall_scan_apply(const int8_t map[8], float pos0); // install learned map+anchor

#endif
