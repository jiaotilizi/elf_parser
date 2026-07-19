#!/usr/bin/env bash
# Build qemu_riscv_bare firmware: startup.S + main.c -> output/img/test_firmware_riscv.elf
#
# Toolchain: riscv64-elf-gcc 16.x (multilib for rv32)
# Arch: RV32IMAC + Zicsr
# Goal: validate multi-region dump (flash + RAM) and RISC-V DWARF parsing
set -e

SCENARIO_DIR="$(cd "$(dirname "$0")" && pwd)"
COMMON_DIR="$SCENARIO_DIR/../../_common"

CC=riscv64-elf-gcc

CFLAGS=(
    -march=rv32imac_zicsr
    -mabi=ilp32
    -ffreestanding -nostdlib -nostartfiles
    -g3 -gdwarf-4 -O0
    -fdata-sections -ffunction-sections
    -I "$COMMON_DIR"
)
LDFLAGS=(
    -T "$SCENARIO_DIR/linker.ld"
    -Wl,--gc-sections
    -Wl,-Map,"$SCENARIO_DIR/output/img/test_firmware_riscv.map"
)

mkdir -p "$SCENARIO_DIR/output/tmp" "$SCENARIO_DIR/output/img"

echo "=== compile startup.S ==="
$CC "${CFLAGS[@]}" -c "$SCENARIO_DIR/startup.S" -o "$SCENARIO_DIR/output/tmp/startup.o"

echo "=== compile main.c ==="
$CC "${CFLAGS[@]}" -c "$SCENARIO_DIR/main.c" -o "$SCENARIO_DIR/output/tmp/main.o"

echo "=== link test_firmware_riscv.elf ==="
$CC "${CFLAGS[@]}" "${LDFLAGS[@]}" \
    "$SCENARIO_DIR/output/tmp/startup.o" \
    "$SCENARIO_DIR/output/tmp/main.o" \
    -o "$SCENARIO_DIR/output/img/test_firmware_riscv.elf"

echo ""
echo "OK: $SCENARIO_DIR/output/img/test_firmware_riscv.elf"
echo "  Next: python3 $SCENARIO_DIR/run_qemu.py"
riscv64-elf-size "$SCENARIO_DIR/output/img/test_firmware_riscv.elf"