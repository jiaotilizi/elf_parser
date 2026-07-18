/*
 * Cortex-R52 startup for QEMU mps3-an536
 *
 * 内存映射（MPS3-AN536）：
 *   SRAM  0x20000000 - 0x203fffff (4MB)
 *
 * R-profile 复位流程（无 M-profile 风格的向量表）：
 *   1. CPU 从 reset vector 启动（默认 ARM 模式）
 *   2. _start 设 SP → 清 .bss → 调 main → 死循环
 *
 * 入口点由 ELF entry point 指定（linker 里 ENTRY(_start)），
 * QEMU -kernel 会自动跳转到 ELF entry。
 */

    .syntax unified
    .cpu cortex-r52
    .arm

/* ── Reset entry ────────────────────────────────────────── */
    .section .text.startup, "ax", %progbits
    .align 2
    .global _start
_start:
    /* 设置 SP（R-profile 复位时 SP 未定义，需手动设置） */
    ldr     sp, =_estack

    /* 复制 .data 段：_sidata (Flash LMA) → _sdata.._edata (RAM VMA) */
    ldr     r0, =_sidata
    ldr     r1, =_sdata
    ldr     r2, =_edata
.Lcopy_data:
    cmp     r1, r2
    bcc     .Lcopy_data_loop
    b       .Lzero_bss
.Lcopy_data_loop:
    ldmia   r0!, {r3}
    stmia   r1!, {r3}
    b       .Lcopy_data

    /* 清零 .bss 段：_sbss.._ebss */
.Lzero_bss:
    ldr     r0, =_sbss
    ldr     r1, =_ebss
    mov     r2, #0
.Lzero_bss_loop:
    cmp     r0, r1
    bcc     .Lzero_bss_fill
    b       .Lcall_main
.Lzero_bss_fill:
    str     r2, [r0], #4
    b       .Lzero_bss_loop

    /* 调用 main() */
.Lcall_main:
    bl      main

    /* main 返回后死循环 */
.Lhang:
    b       .Lhang

    .end
