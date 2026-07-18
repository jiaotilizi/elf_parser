.syntax unified
.cpu cortex-m4
.fpu fpv4-sp-d16
.thumb

.global _vectors
.global Reset_Handler
.extern main

.section .isr_vector, "a", %progbits
.align 2
_vectors:
g_pfnVectors:
    .word _estack
    .word Reset_Handler
    .word __tx_NMIHandler
    .word __tx_HardfaultHandler
    .word __tx_BadHandler
    .word __tx_BadHandler
    .word __tx_BadHandler
    .word __tx_BadHandler
    .word __tx_BadHandler
    .word __tx_BadHandler
    .word __tx_BadHandler
    .word __tx_SVCallHandler
    .word __tx_DBGHandler
    .word __tx_BadHandler
    .word __tx_PendSVHandler
    .word __tx_SysTickHandler

.section .text.Reset_Handler, "ax", %progbits
.align 2
.thumb_func
Reset_Handler:
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
    movs    r2, #0
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