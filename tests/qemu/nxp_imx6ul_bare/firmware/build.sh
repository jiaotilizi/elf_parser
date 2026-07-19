#!/usr/bin/env bash
# Build NXP i.MX6UL (Cortex-A7, ARMv7-A) bare-metal firmware
#
# Toolchain: arm-none-eabi-gcc
# Arch: ARMv7-A (Cortex-A7)
# Goal: validate 32-bit pointer DWARF parsing path

set -e

SCENARIO_DIR="$(cd "$(dirname "$0")" && pwd)"
COMMON_DIR="$SCENARIO_DIR/../../_common"

CC=arm-none-eabi-gcc

CFLAGS=(
    -march=armv7-a
    -mcpu=cortex-a7
    -mthumb
    -ffreestanding -nostdlib -nostartfiles
    -g3 -gdwarf-4 -O0
    -fno-pic -fno-pie
    -fdata-sections -ffunction-sections
    -I "$COMMON_DIR"
)
LDFLAGS=(
    -T "$SCENARIO_DIR/linker.ld"
    -Wl,--gc-sections
    -Wl,-Map,"$SCENARIO_DIR/output/img/test_firmware_nxp_imx6ul.map"
)

mkdir -p "$SCENARIO_DIR/output/tmp" "$SCENARIO_DIR/output/img"

echo "=== compile startup.S ==="
$CC "${CFLAGS[@]}" -c "$SCENARIO_DIR/startup.S" -o "$SCENARIO_DIR/output/tmp/startup.o"

echo "=== compile main.c ==="
$CC "${CFLAGS[@]}" -c "$SCENARIO_DIR/main.c" -o "$SCENARIO_DIR/output/tmp/main.o"

echo "=== link test_firmware_nxp_imx6ul.elf ==="
$CC "${CFLAGS[@]}" "${LDFLAGS[@]}" \
    "$SCENARIO_DIR/output/tmp/startup.o" \
    "$SCENARIO_DIR/output/tmp/main.o" \
    -o "$SCENARIO_DIR/output/img/test_firmware_nxp_imx6ul.elf"

echo ""
echo "OK: $SCENARIO_DIR/output/img/test_firmware_nxp_imx6ul.elf"
echo "  Next: python3 $SCENARIO_DIR/run_qemu.py"
arm-none-eabi-size "$SCENARIO_DIR/output/img/test_firmware_nxp_imx6ul.elf"
