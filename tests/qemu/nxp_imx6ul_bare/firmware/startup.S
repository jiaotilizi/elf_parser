/*
 * NXP i.MX6UL (Cortex-A7, ARMv7-A) startup for QEMU
 *
 * Memory map (QEMU virt default RAM):
 *   RAM 0x40000000 - 0x43ffffff (64MB)
 *
 * ARMv7-A boot: QEMU `-kernel elf.elf` loads ELF segments to VMA,
 * CPU 0 jumps to ELF entry.
 *
 * Reset flow:
 *   1. _start set SP (_estack at top of RAM)
 *   2. Clear .bss (4 byte steps)
 *   3. bl main -> dead loop
 */

    .section .text.startup, "ax"
    .align 2
    .global _start
_start:
    /* Set SP */
    ldr     sp, =_estack

    /* Zero .bss section: _sbss.._ebss (4 byte steps) */
    ldr     r0, =_sbss
    ldr     r1, =_ebss
    mov     r2, #0
.Lzero_bss_loop:
    cmp     r0, r1
    bge     .Lcall_main
    str     r2, [r0], #4
    b       .Lzero_bss_loop

    /* Call main() */
.Lcall_main:
    bl      main

    /* Hang after main returns */
.Lhang:
    wfi
    b       .Lhang

    .end
