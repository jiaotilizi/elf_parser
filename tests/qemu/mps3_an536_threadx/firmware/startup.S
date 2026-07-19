    .syntax unified
    .cpu cortex-r52
    .arm

    .section .text.startup, "ax", %progbits
    .align 2
    .global _start

_start:
    mrs     r0, cpsr
    and     r0, r0, #0x1F
    cmp     r0, #0x1A
    bne     .Lnot_hyp_mode

    adr     r0, .Lhyp_return
    msr     elr_hyp, r0
    mov     r0, #0x13
    msr     spsr_hyp, r0
    eret

.Lhyp_return:
    ldr     sp, =_estack
    b       .Lstart_main

.Lnot_hyp_mode:
    ldr     sp, =_estack

.Lstart_main:
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

.Lcall_main:
    bl      main

.Lhang:
    b       .Lhang

    .end
