/*
 * FreeRTOSConfig.h for QEMU mps2-an386 (Cortex-M4)
 *
 * Tuned for offline memory analysis validation:
 *   - 4 tasks + mutex + counting sem + queue + event group
 *   - heap_4 (32KB) for dynamic allocation
 *   - Queue registry enabled so plugin can enumerate queues/sem/mutex
 */
#ifndef FREERTOS_CONFIG_H
#define FREERTOS_CONFIG_H

/* ── CPU / Tick ───────────────────────────────────────── */
#define configCPU_CLOCK_HZ              ( 25000000UL )
#define configTICK_RATE_HZ              ( ( TickType_t ) 1000 )
#define configUSE_PREEMPTION             1
#define configUSE_TIME_SLICING           1
#define configUSE_PORT_OPTIMISED_TASK_SELECTION 1
#define configUSE_TICKLESS_IDLE          0
#define configMAX_PRIORITIES             ( 8 )
#define configMINIMAL_STACK_SIZE         ( ( uint16_t ) 128 )
#define configTOTAL_HEAP_SIZE            ( ( size_t ) 32768 )
#define configMAX_TASK_NAME_LEN          ( 16 )
#define configUSE_16_BIT_TICKS           0
#define configIDLE_SHOULD_YIELD           1
#define configUSE_TASK_NOTIFICATIONS     1
#define configTASK_NOTIFICATION_ARRAY_ENTRIES 3
#define configUSE_MUTEXES                1
#define configUSE_RECURSIVE_MUTEXES      1
#define configUSE_COUNTING_SEMAPHORES    1
#define configUSE_QUEUE_SETS             0
#define configUSE_QUEUE_REGISTRY         1
#define configUSE_NEWLIB_REENTRANT       0
#define configENABLE_BACKWARD_COMPATIBILITY 1
#define configNUM_THREAD_LOCAL_STORAGE_POINTERS 0
#define configSTACK_DEPTH_TYPE           uint16_t
#define configMESSAGE_BUFFER_LENGTH_TYPE size_t

/* ── Memory allocation ───────────────────────────────── */
#define configSUPPORT_STATIC_ALLOCATION  0
#define configSUPPORT_DYNAMIC_ALLOCATION   1
#define configENABLE_ALLOCATION_IN_ISR    1
#define configCHECK_FOR_STACK_OVERFLOW    2
#define configUSE_MALLOC_ON_HOOK_FAILURE  0
#define configUSE_IDLE_HOOK               0
#define configUSE_TICK_HOOK                0
#define configUSE_DAEMON_TASK_STARTUP_HOOK 0

/* ── Timers / events ────────────────────────────────── */
#define configUSE_TIMERS                  1
#define configTIMER_TASK_PRIORITY        ( configMAX_PRIORITIES - 1 )
#define configTIMER_QUEUE_LENGTH          10
#define configTIMER_TASK_STACK_DEPTH      ( configMINIMAL_STACK_SIZE * 2 )
#define configUSE_TRACE_FACILITY          1

/* ── Co-routines (unused, kept default) ──────────────── */
#define configUSE_CO_ROUTINES             0
#define configMAX_CO_ROUTINE_PRIORITIES   2

/* ── Cortex-M specifics ─────────────────────────────── */
#define configPRIO_BITS                   4
#define configLIBRARY_LOWEST_INTERRUPT_PRIORITY       15
#define configLIBRARY_MAX_SYSCALL_INTERRUPT_PRIORITY   5
#define configKERNEL_INTERRUPT_PRIORITY \
        ( configLIBRARY_LOWEST_INTERRUPT_PRIORITY << ( 8 - configPRIO_BITS ) )
#define configMAX_SYSCALL_INTERRUPT_PRIORITY \
        ( configLIBRARY_MAX_SYSCALL_INTERRUPT_PRIORITY << ( 8 - configPRIO_BITS ) )

/* ── Optional includes (none needed for QEMU) ──────── */
#define configINCLUDE_APPLICATION_DEFINED_PRIVILEGED_FUNCTIONS 0
#define configUSE_STATS_FORMATTING_FUNCTIONS 0
#define configRECORD_STACK_HIGH_ADDRESS    1
#define configGENERATE_RUN_TIME_STATS      0

/* ── Hooks (minimal) ────────────────────────────────── */
/* Hook implementations are provided in main.c, not as macros */
#define configUSE_APPLICATION_TASK_TAG     0

/* ── Optional API (disabled for minimal build) ──────── */
#define INCLUDE_vTaskPrioritySet          1
#define INCLUDE_uxTaskPriorityGet          1
#define INCLUDE_vTaskDelete               1
#define INCLUDE_vTaskSuspend              1
#define INCLUDE_vTaskDelayUntil           1
#define INCLUDE_vTaskDelay                1
#define INCLUDE_xTaskGetSchedulerState    1
#define INCLUDE_xTaskGetCurrentTaskHandle 1
#define INCLUDE_uxTaskGetStackHighWaterMark 1
#define INCLUDE_xTaskGetIdleTaskHandle    1
#define INCLUDE_eTaskGetState             1
#define INCLUDE_xEventGroupSetBitTaskHandle 1
#define INCLUDE_xTimerPendFunctionCall    1
#define INCLUDE_xTaskAbortDelay          1
#define INCLUDE_xTaskGetHandle             1
#define INCLUDE_xTaskResumeFromISR        1

#endif /* FREERTOS_CONFIG_H */
