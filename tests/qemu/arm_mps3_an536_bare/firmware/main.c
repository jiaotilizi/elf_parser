/*
 * Cortex-R52 裸机 main：薄包装，复用共享固件源码。
 *
 * 共享源码 ../_common/test_firmware_bss.c 定义了：
 *   - assert_info_t / test_point_t / trace_record_t 结构
 *   - g_assert_infos / g_test_points / g_trace_buffer 等全局变量
 *   - simulate_runtime() 运行时填充数据
 *   - trigger_crash_assert() 触发 crash
 *
 * 验证目标：解析器能在 R-profile ARMv7-R Thumb-2 ELF 上工作，
 * 与 M-profile ARMv7-E 输出一致。
 */
#include "../../_common/test_firmware_bss.c"
