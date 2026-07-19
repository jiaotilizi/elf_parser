#!/bin/bash

set -e

SCENARIO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCENARIO_DIR"

CC=arm-none-eabi-gcc
LD=arm-none-eabi-ld
OBJCOPY=arm-none-eabi-objcopy
OBJDUMP=arm-none-eabi-objdump

THREADX_DIR=../../../../rtos/threadx_v6p5p1
COMMON_DIR=$THREADX_DIR/common
PORT_DIR=$THREADX_DIR/ports/cortex_a7/gnu

CFLAGS="-march=armv7-a -mcpu=cortex-a7 -mfpu=vfpv4 -mfloat-abi=softfp \
         -ffreestanding -nostartfiles \
         -g3 -gdwarf-4 -O0 \
         -ffunction-sections -fdata-sections -fno-builtin \
         -I $COMMON_DIR/inc \
         -I $PORT_DIR/inc \
         -I ."

LDFLAGS="-T linker.ld -nostartfiles -nostdlib -Wl,--gc-sections \
         -march=armv7-a -mcpu=cortex-a7 -mfpu=vfpv4 -mfloat-abi=softfp"

BUILD_DIR=output/tmp
IMG_DIR=output/img
mkdir -p "$BUILD_DIR" "$IMG_DIR"

echo "[build] CC=$CC"
echo "[build] Compiling ThreadX for Cortex-A7..."

$CC $CFLAGS -c startup.S -o $BUILD_DIR/startup.o
$CC $CFLAGS -c low_level_stub.S -o $BUILD_DIR/low_level.o
$CC $CFLAGS -c sample_threadx.c -o $BUILD_DIR/sample.o
$CC $CFLAGS -c libc_stubs.c -o $BUILD_DIR/libc_stubs.o

for src in $(find $COMMON_DIR/src -name "*.c" | sort); do
    obj="$BUILD_DIR/$(basename ${src%.*}).o"
    echo "  CC  $(basename $src)"
    $CC $CFLAGS -c "$src" -o "$obj"
done

for src in $(find $PORT_DIR/src -name "*.S" | sort); do
    obj="$BUILD_DIR/$(basename ${src%.*}).o"
    echo "  CC  $(basename $src)"
    $CC $CFLAGS -c "$src" -o "$obj"
done

echo "[build] Linking..."
OBJS="$BUILD_DIR/startup.o $BUILD_DIR/low_level.o \
      $BUILD_DIR/sample.o $BUILD_DIR/libc_stubs.o \
      $(find $BUILD_DIR -name "tx_*.o") $(find $BUILD_DIR -name "txe_*.o") $(find $BUILD_DIR -name "_tx_*.o")"

$CC $LDFLAGS $OBJS -o $IMG_DIR/test_firmware_nxp_imx6ul_threadx.elf -lgcc

echo "[build] Done: $IMG_DIR/test_firmware_nxp_imx6ul_threadx.elf"
arm-none-eabi-size $IMG_DIR/test_firmware_nxp_imx6ul_threadx.elf
