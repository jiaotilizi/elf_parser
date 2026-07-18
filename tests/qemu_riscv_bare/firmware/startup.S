/*
 * RISC-V (SiFive E) startup for QEMU sifive_e
 *
 * Memory map (sifive_e):
 *   FLASH 0x20000000 - 0x200fffff (1MB)  - mask ROM jumps here after reset
 *   RAM   0x80000000 - 0x80003fff (16KB) - SRAM, BSS lives here
 *
 * Boot flow:
 *   1. QEMU mask ROM (at 0x10000) does basic init, jumps to 0x20000000
 *   2. _start at 0x20000000 sets SP from _estack (top of RAM)
 *   3. Zero .bss in RAM
 *   4. Call main, loop forever
 *
 * Use .option norvc to ensure initial instructions are 32-bit (not compressed).
 */

    .section .text.startup, "ax"
    .align 2
    .global _start
_start:
    .option push
    .option norvc
    /* Set SP to top of RAM (_estack = 0x80004000) */
    la      sp, _estack

    /* Zero .bss (4-byte step for simplicity, RISC-V word is 4 bytes) */
    la      t0, _sbss
    la      t1, _ebss
    li      t2, 0
.Lzero_bss_loop:
    bgeu    t0, t1, .Lcall_main
    sw      t2, 0(t0)
    addi    t0, t0, 4
    j       .Lzero_bss_loop

.Lcall_main:
    /* Call main() */
    call    main

    /* main returns, loop forever */
.Lhang:
    wfi
    j       .Lhang
    .option pop

    .end
