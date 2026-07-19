/*
 * RISC-V bare-metal main: thin wrapper that includes shared firmware source.
 *
 * Validation goals:
 *   1. Parser works on RISC-V RV32 ELF
 *   2. Multi-region dump (flash + RAM) is loaded correctly
 *   3. char* points into FLASH region, deref returns str across regions
 */
#include "../../_common/test_firmware_bss.c"
