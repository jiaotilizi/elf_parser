#!/usr/bin/env bash
# Build qemu_aarch64_bare firmware: startup.S + main.c -> output/img/test_firmware_aarch64.elf
#
# Toolchain: aarch64-elf-gcc 16.x
# Arch: AArch64 (ARMv8-A + Cortex-A53)
# Goal: validate 64-bit pointer DWARF parsing path
set -e

SCENARIO_DIR="$(cd "$(dirname "$0")" && pwd)"
COMMON_DIR="$SCENARIO_DIR/../../_common"

CC=aarch64-elf-gcc

CFLAGS=(
    -march=armv8-a
    -mcpu=cortex-a53
    -ffreestanding -nostdlib -nostartfiles
    -g3 -gdwarf-4 -O0
    -fno-pic -fno-pie
    -fdata-sections -ffunction-sections
    -I "$COMMON_DIR"
)
LDFLAGS=(
    -T "$SCENARIO_DIR/linker.ld"
    -Wl,--gc-sections
    -Wl,-Map,"$SCENARIO_DIR/output/img/test_firmware_aarch64.map"
)

mkdir -p "$SCENARIO_DIR/output/tmp" "$SCENARIO_DIR/output/img"

echo "=== compile startup.S ==="
$CC "${CFLAGS[@]}" -c "$SCENARIO_DIR/startup.S" -o "$SCENARIO_DIR/output/tmp/startup.o"

echo "=== compile main.c ==="
$CC "${CFLAGS[@]}" -c "$SCENARIO_DIR/main.c" -o "$SCENARIO_DIR/output/tmp/main.o"

echo "=== link test_firmware_aarch64.elf ==="
$CC "${CFLAGS[@]}" "${LDFLAGS[@]}" \
    "$SCENARIO_DIR/output/tmp/startup.o" \
    "$SCENARIO_DIR/output/tmp/main.o" \
    -o "$SCENARIO_DIR/output/img/test_firmware_aarch64.elf"

echo ""
echo "OK: $SCENARIO_DIR/output/img/test_firmware_aarch64.elf"
echo "  Next: python3 $SCENARIO_DIR/run_qemu.py"
aarch64-elf-size "$SCENARIO_DIR/output/img/test_firmware_aarch64.elf"