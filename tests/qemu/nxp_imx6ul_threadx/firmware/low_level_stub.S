    .arm

    .global _tx_initialize_low_level
    .global _tx_thread_system_stack_ptr
    .global _tx_initialize_unused_memory
    .global _end
    .global _sp
    .global _stack_bottom
    .global __vectors
    .global __tx_undefined
    .global __tx_swi_interrupt
    .global __tx_prefetch_handler
    .global __tx_abort_handler
    .global __tx_reserved_handler
    .global __tx_irq_handler
    .global __tx_fiq_handler
    .global _tx_thread_context_save
    .global _tx_thread_context_restore
    .global _tx_timer_interrupt

    .text
    .align 2

_tx_initialize_low_level:
    LDR     r1, =_sp

    LDR     r2, =_stack_bottom
    SUB     r3, r1, #1024
    CMP     r3, r2
    BLT     _stack_error_loop

    LDR     r2, =_tx_thread_system_stack_ptr
    STR     r3, [r2]

    LDR     r1, =_end
    LDR     r2, =_tx_initialize_unused_memory
    ADD     r1, r1, #8
    STR     r1, [r2]

    PUSH    {lr}

    LDR     r0, =__vectors
    MCR     p15, 0, r0, c12, c0, 0

    POP     {lr}

    BX      lr

_stack_error_loop:
    B       _stack_error_loop

__tx_undefined:
    B       __tx_undefined

__tx_swi_interrupt:
    B       __tx_swi_interrupt

__tx_prefetch_handler:
    B       __tx_prefetch_handler

__tx_abort_handler:
    B       __tx_abort_handler

__tx_reserved_handler:
    B       __tx_reserved_handler

__tx_irq_handler:
    B       __tx_irq_handler

__tx_fiq_handler:
    B       __tx_fiq_handler
