.syntax unified
.cpu cortex-m4
.fpu fpv4-sp-d16
.thumb

.global _start
.extern main
.extern __data_load_start__
.extern __data_start__
.extern __data_end__
.extern __bss_start__
.extern __bss_end__
.extern __stack_end__

.section .vectors
__vectors_start:
    .word __stack_end__
    .word reset_handler
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0

.section .text
.thumb_func
reset_handler:
    ldr r0, =__stack_end__
    mov sp, r0

    ldr r0, =__data_load_start__
    ldr r1, =__data_start__
    ldr r2, =__data_end__
    bl memcopy

    ldr r0, =__bss_start__
    ldr r1, =__bss_end__
    mov r2, #0
    bl memset

    mov r0, #0
    bl main

loop_forever:
    b loop_forever

.thumb_func
memcopy:
    cmp r0, r1
    beq memcopy_done
memcopy_loop:
    ldrb r3, [r0], #1
    strb r3, [r1], #1
    cmp r1, r2
    bne memcopy_loop
memcopy_done:
    bx lr

.thumb_func
memset:
    cmp r0, r1
    beq memset_done
    strb r2, [r0], #1
    b memset
memset_done:
    bx lr