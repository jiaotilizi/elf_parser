/*
 * Cortex-M4 startup for QEMU mps2-an386 + FreeRTOS V11.3.0
 *
 * Memory map (MPS2-AN386):
 *   FLASH 0x00000000 - 0x003fffff (ssram1, 4MB)
 *   RAM   0x20000000 - 0x203fffff (ssram23, 4MB; we use 256K)
 *
 * Reset flow:
 *   1. CPU loads initial SP from 0x00000000, Reset_Handler from 0x00000004
 *   2. Reset_Handler copies .data to RAM, zeroes .bss, calls main
 *   3. main() calls firmware_init() + simulate_runtime() then vTaskStartScheduler()
 *
 * FreeRTOS port (ARM_CM4F) requires these handler aliases:
 *   SVC_Handler     -> vPortSVCHandler
 *   PendSV_Handler  -> xPortPendSVHandler
 *   SysTick_Handler -> xPortSysTickHandler
 */

    .syntax unified
    .cpu cortex-m4
    .thumb

/* ── Vector table ─────────────────────────────────────── */
    .section .isr_vector, "a", %progbits
    .align 2
    .global g_pfnVectors
g_pfnVectors:
    .word _estack                /* 0x00: Initial SP           */
    .word Reset_Handler          /* 0x04: Reset                */
    .word NMI_Handler            /* 0x08: NMI                  */
    .word HardFault_Handler      /* 0x0C: HardFault            */
    .word MemManage_Handler      /* 0x10: MemManage            */
    .word BusFault_Handler       /* 0x14: BusFault             */
    .word UsageFault_Handler     /* 0x18: UsageFault           */
    .word 0                       /* 0x1C: Reserved              */
    .word 0                       /* 0x20: Reserved              */
    .word 0                       /* 0x24: Reserved              */
    .word 0                       /* 0x28: Reserved              */
    .word SVC_Handler            /* 0x2C: SVC -> vPortSVCHandler */
    .word DebugMon_Handler       /* 0x30: Debug Monitor        */
    .word 0                       /* 0x34: Reserved              */
    .word PendSV_Handler         /* 0x38: PendSV -> xPortPendSVHandler */
    .word SysTick_Handler        /* 0x3C: SysTick -> xPortSysTickHandler */

/* ── Reset_Handler ────────────────────────────────────── */
    .section .text.Reset_Handler, "ax", %progbits
    .align 2
    .global Reset_Handler
    .thumb_func
Reset_Handler:
    /* SP loaded by hardware from vector table[0] */

    /* Copy .data: _sidata (Flash LMA) -> _sdata.._edata (RAM VMA) */
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

    /* Zero .bss: _sbss.._ebss */
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

    /* Call main() */
.Lcall_main:
    bl      main

    /* If main returns, loop forever (should not happen with RTOS) */
.Lhang:
    b       .Lhang

/* ── Default handler (weak) ──────────────────────────── */
    .section .text.Default_Handler, "ax", %progbits
    .align 2
    .global Default_Handler
    .thumb_func
Default_Handler:
    b       Default_Handler

/* ── FreeRTOS handler aliases (from ARM_CM4F/port.c) ──── */
    .weak NMI_Handler
    .thumb_set NMI_Handler, Default_Handler
    .weak HardFault_Handler
    .thumb_set HardFault_Handler, Default_Handler
    .weak MemManage_Handler
    .thumb_set MemManage_Handler, Default_Handler
    .weak BusFault_Handler
    .thumb_set BusFault_Handler, Default_Handler
    .weak UsageFault_Handler
    .thumb_set UsageFault_Handler, Default_Handler
    .weak DebugMon_Handler
    .thumb_set DebugMon_Handler, Default_Handler

    /* FreeRTOS port-supplied handlers */
    .weak SVC_Handler
    .thumb_set SVC_Handler, vPortSVCHandler
    .weak PendSV_Handler
    .thumb_set PendSV_Handler, xPortPendSVHandler
    .weak SysTick_Handler
    .thumb_set SysTick_Handler, xPortSysTickHandler

    .end
