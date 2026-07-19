#!/bin/bash
set -e

CROSS_COMPILE=${CROSS_COMPILE:-arm-none-eabi-}
CC=${CROSS_COMPILE}gcc
LD=${CROSS_COMPILE}ld
OBJCOPY=${CROSS_COMPILE}objcopy
OBJDUMP=${CROSS_COMPILE}objdump

LOCAL_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

CFLAGS="-mcpu=cortex-m3 -mthumb -mlittle-endian -mfloat-abi=soft \
        -ffunction-sections -fdata-sections -fno-builtin -nostdlib \
        -g -ggdb3 -O0 \
        -I${LOCAL_DIR}"

BUILD_DIR=output/tmp
IMG_DIR=output/img
mkdir -p "$BUILD_DIR" "$IMG_DIR"

echo "Compiling STM32VLDISCOVERY for Cortex-M3..."

${CC} ${CFLAGS} -c ${LOCAL_DIR}/startup.S -o $BUILD_DIR/startup.o
${CC} ${CFLAGS} -c ${LOCAL_DIR}/main.c -o $BUILD_DIR/main.o

echo "Linking..."
${CC} ${CFLAGS} -T${LOCAL_DIR}/linker.ld -nostartfiles -nostdlib -Wl,--gc-sections \
    -o $IMG_DIR/test_firmware_stm32.elf \
    $BUILD_DIR/startup.o $BUILD_DIR/main.o

echo "Generating binary..."
${OBJCOPY} -O binary $IMG_DIR/test_firmware_stm32.elf $IMG_DIR/test_firmware_stm32.bin

echo "Generating dump..."
${OBJDUMP} -D $IMG_DIR/test_firmware_stm32.elf > $IMG_DIR/test_firmware_stm32.dump

echo "Build complete!"
ls -la $IMG_DIR/
