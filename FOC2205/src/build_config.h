// Build-time safety gates for FOC2205.
// A broken CPLD bridge can stall the hart on a load from 0x6000xxxx before a
// software timeout runs, so the default image must not touch that window.
#ifndef FOC2205_BUILD_CONFIG_H
#define FOC2205_BUILD_CONFIG_H
#ifndef FOC_CPLD_BRINGUP
#define FOC_CPLD_BRINGUP 0
#endif
#endif
