#!/usr/bin/env bash
# Build qemu_m4_bare firmware: startup_qemu.s + _common/test_firmware_bss.c
# Output: output/img/test_firmware_qemu.elf
#
# Toolchain: arm-none-eabi-gcc
# Arch: Cortex-M4 (ARMv7E-M)
# Target: QEMU mps2-an386
set -e

SCENARIO_DIR="$(cd "$(dirname "$0")" && pwd)"
COMMON_DIR="$SCENARIO_DIR/../../_common"

CC=arm-none-eabi-gcc

CFLAGS=(
    -mcpu=cortex-m4 -mthumb -mlittle-endian -mfloat-abi=soft
    -ffreestanding -nostdlib -nostartfiles
    -g3 -gdwarf-4 -O0
    -fdata-sections -ffunction-sections
    -I "$COMMON_DIR"
)
LDFLAGS=(
    -T "$SCENARIO_DIR/linker_qemu.ld"
    -Wl,--gc-sections
    -Wl,-Map,"$SCENARIO_DIR/output/img/test_firmware_qemu.map"
)

mkdir -p "$SCENARIO_DIR/output/tmp" "$SCENARIO_DIR/output/img"

echo "=== compile startup_qemu.s ==="
$CC "${CFLAGS[@]}" -c "$SCENARIO_DIR/startup_qemu.s" -o "$SCENARIO_DIR/output/tmp/startup_qemu.o"

echo "=== compile test_firmware_bss.c ==="
$CC "${CFLAGS[@]}" -c "$COMMON_DIR/test_firmware_bss.c" -o "$SCENARIO_DIR/output/tmp/test_firmware_bss.o"

echo "=== link test_firmware_qemu.elf ==="
$CC "${CFLAGS[@]}" "${LDFLAGS[@]}" \
    "$SCENARIO_DIR/output/tmp/startup_qemu.o" \
    "$SCENARIO_DIR/output/tmp/test_firmware_bss.o" \
    -o "$SCENARIO_DIR/output/img/test_firmware_qemu.elf"

echo ""
echo "OK: $SCENARIO_DIR/output/img/test_firmware_qemu.elf"
echo "  Next: python3 $SCENARIO_DIR/run_qemu_dump.py"
arm-none-eabi-size "$SCENARIO_DIR/output/img/test_firmware_qemu.elf"
