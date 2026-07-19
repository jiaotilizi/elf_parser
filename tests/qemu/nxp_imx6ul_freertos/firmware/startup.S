/*
 * NXP i.MX6UL (Cortex-A7, ARMv7-A) startup for FreeRTOS
 */

    .section .text.startup, "ax"
    .align 2
    .global _start
_start:
    ldr     sp, =_estack

    ldr     r0, =_sbss
    ldr     r1, =_ebss
    mov     r2, #0
.Lzero_bss_loop:
    cmp     r0, r1
    bge     .Lcall_main
    str     r2, [r0], #4
    b       .Lzero_bss_loop

.Lcall_main:
    bl      main

.Lhang:
    wfi
    b       .Lhang

    .end
