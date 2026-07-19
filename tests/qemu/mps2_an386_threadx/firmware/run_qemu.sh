#!/bin/bash
set -e

ELF_FILE="output/img/sample_threadx.elf"
DUMP_FILE="output/img/threadx_ram_dump.bin"
QEMU_SOCK="/tmp/qemu_threadx.sock"

rm -f ${QEMU_SOCK}

qemu-system-arm -cpu cortex-m4 -machine mps2-an386 \
    -kernel ${ELF_FILE} \
    -nographic \
    -monitor unix:${QEMU_SOCK},server,nowait \
    -semihosting \
    -d guest_errors \
    -serial null \
    -parallel null &

QEMU_PID=$!
echo "QEMU started with PID ${QEMU_PID}"

sleep 3

echo "pmemsave 0x20000000 0x800000 ${DUMP_FILE}" | nc -q 1 -U ${QEMU_SOCK} > /dev/null 2>&1

echo "Dump saved to ${DUMP_FILE}"

kill ${QEMU_PID} 2>/dev/null || true
wait ${QEMU_PID} 2>/dev/null || true

echo "QEMU stopped"