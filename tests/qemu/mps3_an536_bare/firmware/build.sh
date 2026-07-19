#!/usr/bin/env bash
# 编译 qemu_r52_bare 固件：startup.S + main.c → output/img/test_firmware_r52.elf
#
# 工具链：arm-none-eabi-gcc 16.x（同时支持 M4 和 R52）
# 架构：ARMv7-R + Thumb-2
set -e

SCENARIO_DIR="$(cd "$(dirname "$0")" && pwd)"
COMMON_DIR="$SCENARIO_DIR/../../_common"

CC=arm-none-eabi-gcc
OBJCOPY=arm-none-eabi-objcopy

CFLAGS=(
    -mcpu=cortex-r52
    -mthumb
    -ffreestanding -nostdlib -nostartfiles
    -g3 -gdwarf-4 -O0
    -fdata-sections -ffunction-sections
    -I "$COMMON_DIR"
)
LDFLAGS=(
    -T "$SCENARIO_DIR/linker.ld"
    -Wl,--gc-sections
    -Wl,-Map,"$SCENARIO_DIR/output/img/test_firmware_r52.map"
)

mkdir -p "$SCENARIO_DIR/output/tmp" "$SCENARIO_DIR/output/img"

echo "=== 编译 startup.S ==="
$CC "${CFLAGS[@]}" -c "$SCENARIO_DIR/startup.S" -o "$SCENARIO_DIR/output/tmp/startup.o"

echo "=== 编译 main.c ==="
$CC "${CFLAGS[@]}" -c "$SCENARIO_DIR/main.c" -o "$SCENARIO_DIR/output/tmp/main.o"

echo "=== 链接 test_firmware_r52.elf ==="
$CC "${CFLAGS[@]}" "${LDFLAGS[@]}" \
    "$SCENARIO_DIR/output/tmp/startup.o" \
    "$SCENARIO_DIR/output/tmp/main.o" \
    -o "$SCENARIO_DIR/output/img/test_firmware_r52.elf"

echo ""
echo "✓ 编译完成：$SCENARIO_DIR/output/img/test_firmware_r52.elf"
echo "  ★ 运行 python3 $SCENARIO_DIR/run_qemu.py 生成 dump"
arm-none-eabi-size "$SCENARIO_DIR/output/img/test_firmware_r52.elf"