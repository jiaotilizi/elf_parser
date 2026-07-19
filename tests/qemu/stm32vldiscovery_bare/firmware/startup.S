.syntax unified
.cpu cortex-m3
.fpu softvfp
.thumb

.global Reset_Handler
.global _start

.word _estack
.word Reset_Handler
.word NMI_Handler
.word HardFault_Handler
.word MemManage_Handler
.word BusFault_Handler
.word UsageFault_Handler
.word 0
.word 0
.word 0
.word 0
.word SVC_Handler
.word DebugMon_Handler
.word 0
.word PendSV_Handler
.word SysTick_Handler

.thumb_func
Reset_Handler:
    ldr r0, =_estack
    mov sp, r0

    ldr r0, =_sdata
    ldr r1, =_edata
    ldr r2, =_etext
    movs r3, #0
    b LoopCopyDataInit

CopyDataInit:
    ldr r4, [r2, r3]
    str r4, [r0, r3]
    adds r3, r3, #4

LoopCopyDataInit:
    adds r4, r0, r3
    cmp r4, r1
    bcc CopyDataInit

    ldr r2, =_sbss
    ldr r4, =_ebss
    movs r3, #0
    b LoopFillZerobss

FillZerobss:
    str  r3, [r2]
    adds r2, r2, #4

LoopFillZerobss:
    cmp r2, r4
    bcc FillZerobss

    bl main

    b .

.thumb_func
NMI_Handler:
    b NMI_Handler

.thumb_func
HardFault_Handler:
    b HardFault_Handler

.thumb_func
MemManage_Handler:
    b MemManage_Handler

.thumb_func
BusFault_Handler:
    b BusFault_Handler

.thumb_func
UsageFault_Handler:
    b UsageFault_Handler

.thumb_func
SVC_Handler:
    b SVC_Handler

.thumb_func
DebugMon_Handler:
    b DebugMon_Handler

.thumb_func
PendSV_Handler:
    b PendSV_Handler

.thumb_func
SysTick_Handler:
    b SysTick_Handler
