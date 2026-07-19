/*
 * NXP i.MX6UL (Cortex-A7, ARMv7-A) bare-metal main: thin wrapper that includes shared firmware source.
 *
 * Shared source ../_common/test_firmware_bss.c defines:
 *   - assert_info_t / test_point_t / trace_record_t structs
 *   - g_assert_infos / g_test_points / g_trace_buffer global variables
 *   - simulate_runtime() runtime data fill
 *
 * Validation goals:
 *   1. Parser works on ARMv7-A ELF
 *   2. char* fields have byte_size == 4 in DWARF
 *   3. parse_struct_auto uses read_uint32 to deref char*, returns str
 */
#include "../../../_common/test_firmware_bss.c"
