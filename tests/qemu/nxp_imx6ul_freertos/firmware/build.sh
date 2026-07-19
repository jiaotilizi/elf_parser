#!/bin/bash
# Build script for NXP i.MX6UL (Cortex-A7, ARMv7-A) + FreeRTOS V11.3.0

set -e

SCENARIO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCENARIO_DIR"

CC=arm-none-eabi-gcc
OBJCOPY=arm-none-eabi-objcopy

BUILD_DIR=output/tmp
IMG_DIR=output/img
mkdir -p "$BUILD_DIR" "$IMG_DIR"

RTOS_DIR=../../../../rtos/freertos_v11p3p0
PORT_DIR=$RTOS_DIR/portable/GCC/ARM_CA9
MEMMANG_DIR=$RTOS_DIR/portable/MemMang

CFLAGS="-march=armv7-a -mcpu=cortex-a7 -mfpu=vfpv4 -mfloat-abi=softfp \
         -ffreestanding -nostartfiles \
         -g3 -gdwarf-4 -O0 \
         -fdata-sections -ffunction-sections \
         -I . \
         -I $RTOS_DIR/include \
         -I $PORT_DIR \
         -I ../../../_common"

LDFLAGS="-T linker.ld -Wl,--gc-sections -Wl,-Map,$IMG_DIR/test_firmware_nxp_imx6ul_freertos.map \
         -nostdlib -nostartfiles -march=armv7-a -mcpu=cortex-a7 -mfpu=vfpv4 -mfloat-abi=softfp"

SOURCES="startup.S main.c libc_stubs.c \
         $RTOS_DIR/tasks.c \
         $RTOS_DIR/queue.c \
         $RTOS_DIR/list.c \
         $RTOS_DIR/timers.c \
         $RTOS_DIR/event_groups.c \
         $RTOS_DIR/stream_buffer.c \
         $PORT_DIR/port.c \
         $PORT_DIR/portASM.S \
         $MEMMANG_DIR/heap_4.c"

echo "[build] CC=$CC"
echo "[build] CFLAGS=$CFLAGS"
echo "[build] Compiling..."
for src in $SOURCES; do
    obj="$BUILD_DIR/$(basename ${src%.*}).o"
    echo "  CC  $src -> $obj"
    $CC $CFLAGS -c "$src" -o "$obj"
done

echo "[build] Linking..."
OBJS="$BUILD_DIR/startup.o $BUILD_DIR/main.o $BUILD_DIR/libc_stubs.o \
      $BUILD_DIR/tasks.o $BUILD_DIR/queue.o $BUILD_DIR/list.o \
      $BUILD_DIR/timers.o $BUILD_DIR/event_groups.o $BUILD_DIR/stream_buffer.o \
      $BUILD_DIR/port.o $BUILD_DIR/portASM.o $BUILD_DIR/heap_4.o"

$CC $LDFLAGS $OBJS -o $IMG_DIR/test_firmware_nxp_imx6ul_freertos.elf -lgcc

echo "[build] Done: $IMG_DIR/test_firmware_nxp_imx6ul_freertos.elf"
arm-none-eabi-size $IMG_DIR/test_firmware_nxp_imx6ul_freertos.elf
