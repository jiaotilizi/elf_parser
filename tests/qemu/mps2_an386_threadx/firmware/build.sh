#!/bin/bash
set -e

CROSS_COMPILE=${CROSS_COMPILE:-arm-none-eabi-}
CC=${CROSS_COMPILE}gcc
LD=${CROSS_COMPILE}ld
OBJCOPY=${CROSS_COMPILE}objcopy
OBJDUMP=${CROSS_COMPILE}objdump

THREADX_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && cd ../../../../rtos/threadx_v6p5p1 && pwd)
COMMON_DIR=${THREADX_DIR}/common
PORT_DIR=${THREADX_DIR}/ports/cortex_m4/gnu
EXAMPLE_DIR=${PORT_DIR}/example_build
LOCAL_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

CFLAGS_DEBUG="-mcpu=cortex-m4 -mthumb -mlittle-endian -mfloat-abi=soft -Wall -Wextra \
        -ffunction-sections -fdata-sections -fno-builtin -nostdlib \
        -g -ggdb3 -O0"

# ThreadX 内核源码也带 DWARF 调试信息，否则 _tx_thread_current_ptr 等
# 内核全局变量无法通过 parse_struct_auto 解析类型
CFLAGS_NODEBUG="${CFLAGS_DEBUG}"

INCLUDES="-I${COMMON_DIR}/inc \
          -I${PORT_DIR}/inc \
          -I${EXAMPLE_DIR} \
          -I${LOCAL_DIR}/include"

BUILD_DIR=output/tmp
IMG_DIR=output/img
mkdir -p "$BUILD_DIR" "$IMG_DIR"

echo "Compiling ThreadX for Cortex-M4..."

${CC} ${CFLAGS_DEBUG} ${INCLUDES} -c ${LOCAL_DIR}/startup.S -o $BUILD_DIR/startup.o
${CC} ${CFLAGS_DEBUG} ${INCLUDES} -c ${EXAMPLE_DIR}/tx_initialize_low_level.S -o $BUILD_DIR/low_level.o
${CC} ${CFLAGS_DEBUG} ${INCLUDES} -c ${LOCAL_DIR}/sample_threadx.c -o $BUILD_DIR/sample.o
${CC} ${CFLAGS_NODEBUG} ${INCLUDES} -c ${LOCAL_DIR}/libc_stubs.c -o $BUILD_DIR/libc_stubs.o

for src in $(find ${COMMON_DIR}/src -name "*.c" | sort); do
    obj=$(basename $src .c)
    ${CC} ${CFLAGS_NODEBUG} ${INCLUDES} -c $src -o $BUILD_DIR/${obj}.o
done

for src in $(find ${PORT_DIR}/src -name "*.S" | sort); do
    obj=$(basename $src .S)
    ${CC} ${CFLAGS_NODEBUG} ${INCLUDES} -c $src -o $BUILD_DIR/${obj}.o
done

echo "Linking..."
${CC} ${CFLAGS_DEBUG} -T${LOCAL_DIR}/linker.ld -nostartfiles -nostdlib -Wl,--gc-sections \
    -o $IMG_DIR/sample_threadx.elf \
    $BUILD_DIR/startup.o $BUILD_DIR/low_level.o $BUILD_DIR/sample.o $BUILD_DIR/libc_stubs.o \
    $(find $BUILD_DIR -name "tx_*.o") $(find $BUILD_DIR -name "txe_*.o") $(find $BUILD_DIR -name "_tx_*.o")

echo "Generating binary..."
${OBJCOPY} -O binary $IMG_DIR/sample_threadx.elf $IMG_DIR/sample_threadx.bin

echo "Generating dump..."
${OBJDUMP} -D $IMG_DIR/sample_threadx.elf > $IMG_DIR/sample_threadx.dump

echo "Build complete!"
ls -la $IMG_DIR/