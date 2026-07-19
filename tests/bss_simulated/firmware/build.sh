#!/usr/bin/env bash
# Build bss_simulated firmware: _common/test_firmware_bss.c -> test_firmware_bss.elf
#
# 这个场景不运行 QEMU，只编译出 ELF 供 generate_bss_dump.py 读取符号表，
# 然后 generate_bss_dump.py 模拟填充 BSS 段并生成 dump。
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
    -T "$SCENARIO_DIR/linker.ld"
    -Wl,--gc-sections
    -Wl,-Map,"$SCENARIO_DIR/output/img/test_firmware_bss.map"
)

mkdir -p "$SCENARIO_DIR/output/tmp" "$SCENARIO_DIR/output/img"

echo "=== compile test_firmware_bss.c ==="
$CC "${CFLAGS[@]}" -c "$COMMON_DIR/test_firmware_bss.c" -o "$SCENARIO_DIR/output/tmp/test_firmware_bss.o"

echo "=== link test_firmware_bss.elf ==="
$CC "${CFLAGS[@]}" "${LDFLAGS[@]}" \
    "$SCENARIO_DIR/output/tmp/test_firmware_bss.o" \
    -o "$SCENARIO_DIR/test_firmware_bss.elf"

echo ""
echo "OK: $SCENARIO_DIR/test_firmware_bss.elf"
echo "  Next: python3 $SCENARIO_DIR/generate_bss_dump.py"
arm-none-eabi-size "$SCENARIO_DIR/test_firmware_bss.elf"
