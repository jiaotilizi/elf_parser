/*
 * FreeRTOSConfig.h for NXP i.MX6UL (Cortex-A7, ARMv7-A)
 */
#ifndef FREERTOS_CONFIG_H
#define FREERTOS_CONFIG_H

#define configCPU_CLOCK_HZ              ( 696000000UL )
#define configTICK_RATE_HZ              ( ( TickType_t ) 1000 )
#define configUSE_PREEMPTION             1
#define configUSE_TIME_SLICING           1
#define configUSE_PORT_OPTIMISED_TASK_SELECTION 0
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

#define configSUPPORT_STATIC_ALLOCATION  0
#define configSUPPORT_DYNAMIC_ALLOCATION   1
#define configENABLE_ALLOCATION_IN_ISR    1
#define configCHECK_FOR_STACK_OVERFLOW    2
#define configUSE_MALLOC_ON_HOOK_FAILURE  0
#define configUSE_IDLE_HOOK               0
#define configUSE_TICK_HOOK                0
#define configUSE_DAEMON_TASK_STARTUP_HOOK 0

#define configUSE_TIMERS                  1
#define configTIMER_TASK_PRIORITY        ( configMAX_PRIORITIES - 1 )
#define configTIMER_QUEUE_LENGTH          10
#define configTIMER_TASK_STACK_DEPTH      ( configMINIMAL_STACK_SIZE * 2 )
#define configUSE_TRACE_FACILITY          1

#define configUSE_CO_ROUTINES             0
#define configMAX_CO_ROUTINE_PRIORITIES   2

#define configRECORD_STACK_HIGH_ADDRESS    1
#define configGENERATE_RUN_TIME_STATS      0

#define configINTERRUPT_CONTROLLER_BASE_ADDRESS          0x80000000
#define configINTERRUPT_CONTROLLER_CPU_INTERFACE_OFFSET 0x00010000
#define configUNIQUE_INTERRUPT_PRIORITIES               32
#define configMAX_API_CALL_INTERRUPT_PRIORITY           20

extern void FreeRTOS_Tick_Handler(void);

#define configSETUP_TICK_INTERRUPT() \
    do { \
        *(volatile uint32_t*)(0x80000100) = (1 << 1); \
    } while(0)

#define configCLEAR_TICK_INTERRUPT() \
    do { \
        *(volatile uint32_t*)(0x80000100) = (1 << 1); \
    } while(0)

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
