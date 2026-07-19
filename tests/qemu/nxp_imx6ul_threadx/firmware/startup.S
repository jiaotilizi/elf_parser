    .arm

    .global _start

    .text
    .global __vectors
__vectors:
    LDR     pc, STARTUP
    LDR     pc, UNDEFINED
    LDR     pc, SWI
    LDR     pc, PREFETCH
    LDR     pc, ABORT
    LDR     pc, RESERVED
    LDR     pc, IRQ
    LDR     pc, FIQ

STARTUP:      .word  _start
UNDEFINED:    .word  __tx_undefined
SWI:          .word  __tx_swi_interrupt
PREFETCH:     .word  __tx_prefetch_handler
ABORT:        .word  __tx_abort_handler
RESERVED:     .word  __tx_reserved_handler
IRQ:          .word  __tx_irq_handler
FIQ:          .word  __tx_fiq_handler

_start:
    ldr     sp, =_stack_top

    ldr     r0, =_sbss
    ldr     r1, =_ebss
    mov     r2, #0
.Lzero_bss_loop:
    cmp     r0, r1
    bcc     .Lzero_bss_fill
    b       .Lcall_tx_kernel

.Lzero_bss_fill:
    str     r2, [r0], #4
    b       .Lzero_bss_loop

.Lcall_tx_kernel:
    bl      _tx_initialize_kernel_enter

.Lhang:
    b       .Lhang
