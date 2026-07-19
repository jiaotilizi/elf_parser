/*
 * Cortex-M4 startup for QEMU mps2-an386
 *
 * 内存映射：
 *   FLASH 0x00000000 - 0x003fffff (MPS2 ssram1, 4MB)
 *   RAM   0x20000000 - 0x203fffff (MPS2 ssram23, 4MB)
 *
 * 复位流程：
 *   1. CPU 从 0x00000000 读初始 SP，从 0x00000004 读 Reset_Handler
 *   2. Reset_Handler 复制 .data 到 RAM，清零 .bss，调用 main
 *   3. main 返回后死循环
 */

    .syntax unified
    .cpu cortex-m4
    .thumb

/* ── 向量表 ────────────────────────────────────────────── */
    .section .isr_vector, "a", %progbits
    .align 2
    .global g_pfnVectors
g_pfnVectors:
    .word _estack                /* 0x00: Initial SP           */
    .word Reset_Handler          /* 0x04: Reset                */
    .word NMI_Handler            /* 0x08: NMI                  */
    .word HardFault_Handler      /* 0x0C: HardFault             */
    .word MemManage_Handler      /* 0x10: MemManage             */
    .word BusFault_Handler       /* 0x14: BusFault              */
    .word UsageFault_Handler     /* 0x18: UsageFault            */
    .word 0                       /* 0x1C: Reserved              */
    .word 0                       /* 0x20: Reserved              */
    .word 0                       /* 0x24: Reserved              */
    .word 0                       /* 0x28: Reserved              */
    .word SVC_Handler            /* 0x2C: SVC                   */
    .word DebugMon_Handler       /* 0x30: Debug Monitor         */
    .word 0                       /* 0x34: Reserved              */
    .word PendSV_Handler         /* 0x38: PendSV                */
    .word SysTick_Handler        /* 0x3C: SysTick               */

/* ── Reset_Handler ─────────────────────────────────────── */
    .section .text.Reset_Handler, "ax", %progbits
    .align 2
    .global Reset_Handler
    .thumb_func
Reset_Handler:
    /* SP 已由硬件从向量表第一个 word 加载，无需手动设置 */

    /* 复制 .data 段：_sidata (Flash LMA) → _sdata.._edata (RAM VMA) */
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

    /* 清零 .bss 段：_sbss.._ebss */
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

    /* 调用 main() */
.Lcall_main:
    bl      main

    /* main 返回后死循环 */
.Lhang:
    b       .Lhang

/* ── 默认异常处理（弱定义）────────────────────────────── */
    .section .text.Default_Handler, "ax", %progbits
    .align 2
    .global Default_Handler
    .thumb_func
Default_Handler:
    b       Default_Handler

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
    .weak SVC_Handler
    .thumb_set SVC_Handler, Default_Handler
    .weak DebugMon_Handler
    .thumb_set DebugMon_Handler, Default_Handler
    .weak PendSV_Handler
    .thumb_set PendSV_Handler, Default_Handler
    .weak SysTick_Handler
    .thumb_set SysTick_Handler, Default_Handler

    .end
