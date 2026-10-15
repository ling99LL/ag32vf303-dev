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
  int32_t id_ref_q;             // d-axis current target, Q12 amps
  int32_t iq_ref_q;             // q-axis target (torque), Q12 amps
  int32_t v_limit_q;            // voltage limit, Q12 volts
  int32_t kp_q, ki_q;           // current loop gains (voltage mode uses feedforward)
  uint16_t pole_pairs;
  float zero_electric_angle;    // P1-1 修复：标定的电角度初相偏置 (rad)
  int8_t sensor_direction;      // 传感器与电机旋转方向 (+1 或 -1)
  float angle_filt_alpha;       // 换向角低通系数 (0,1]；1.0 = 不滤波
                                // 见 foc_step_isr 里的说明：闭环抖动的直接成因
                                // 就是编码器噪声 x 极对数 直接调制了电压矢量。
  // --- 混合换向钩子（motion 层用，默认关闭）---
  // comm_override = 1 时 foc_step_isr 直接用 comm_angle_e 做换向，不再从
  // 编码器算。这是 motion.c 里"混合换向"的落点：换向角由指令前馈推进
  // （转速被钉死，转矩扰动只变成看不见的负载角摆动），编码器只做慢速滑差
  // 校正。关闭（=0）时 foc.c 行为与从前完全一致。
  uint8_t comm_override;
  float   comm_angle_e;
  // hand-feel layer outputs (filled by the knob logic, consumed here)
  int32_t torque_q;             // external torque command, Q12
  uint8_t brake;                // 1 = short phases (parking brake)
} foc_params_t;

extern foc_params_t g_foc;

// 对齐探测：施加 +90 度电矢量前后读到的 raw 电角度差（rad，已 wrap 到 [0,2pi)）。
// 正向应 ≈ 1.571 (+90 度)，反向应 ≈ 4.712 (270 度 = -90 度)。诊断方向判定用。
extern float g_align_delta;

void foc_init(uint16_t pole_pairs);
void foc_align_sensor(void);    // P1-1 修复：开环对齐转子 d 轴并标定零位电角度
// Called from the PWM update ISR
void foc_step_isr(void);
// Read-only status for diagnostics
int32_t foc_last_angle(void);
int32_t foc_last_iq(void);
uint32_t foc_crc_errors(void);
// 只读 accessor（纯读取，不触碰任何控制逻辑）——上位机要显示三相电流
void foc_last_currents(int16_t *a, int16_t *b, int16_t *c);

#endif
