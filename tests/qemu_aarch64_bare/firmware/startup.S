/*
 * AArch64 (Cortex-A53) startup for QEMU virt
 *
 * 内存映射（virt 默认 RAM）：
 *   RAM 0x40000000 - 0x43ffffff (64MB)
 *
 * AArch64 Linux-style boot：QEMU `-kernel elf.elf` 加载 ELF 段到 VMA，
 * 各 CPU core 跳转到 ELF entry（仅 CPU 0 启动，其他 hold-off）。
 *
 * 复位流程：
 *   1. _start 设 SP（_estack 在 RAM 顶）
 *   2. 清 .bss（8 字节步进）
 *   3. bl main → 死循环
 */

    .section .text.startup, "ax"
    .align 2
    .global _start
_start:
    /* 设置 SP */
    ldr     x0, =_estack
    mov     sp, x0

    /* 清零 .bss 段：_sbss.._ebss（8 字节步进） */
    ldr     x0, =_sbss
    ldr     x1, =_ebss
    mov     x2, #0
.Lzero_bss_loop:
    cmp     x0, x1
    b.cc    .Lzero_bss_fill
    b       .Lcall_main
.Lzero_bss_fill:
    str     x2, [x0], #8
    b       .Lzero_bss_loop

    /* 调用 main() */
.Lcall_main:
    bl      main

    /* main 返回后死循环 */
.Lhang:
    wfi
    b       .Lhang

    .end
