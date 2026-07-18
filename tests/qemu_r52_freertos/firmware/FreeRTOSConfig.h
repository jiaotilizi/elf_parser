#ifndef FREERTOS_CONFIG_H
#define FREERTOS_CONFIG_H

#define configUSE_PREEMPTION            1
#define configUSE_IDLE_HOOK             0
#define configUSE_TICK_HOOK             0
#define configCPU_CLOCK_HZ              ( ( unsigned long ) 200000000 )
#define configTICK_RATE_HZ              ( ( TickType_t ) 1000 )
#define configMAX_PRIORITIES            ( 8 )
#define configMINIMAL_STACK_SIZE        ( ( uint16_t ) 128 )
#define configTOTAL_HEAP_SIZE           ( ( size_t ) 32768 )
#define configMAX_TASK_NAME_LEN         ( 16 )
#define configUSE_TRACE_FACILITY        1
#define configUSE_16_BIT_TICKS          0
#define configIDLE_SHOULD_YIELD         1
#define configUSE_MUTEXES               1
#define configUSE_RECURSIVE_MUTEXES     0
#define configUSE_COUNTING_SEMAPHORES   1
#define configUSE_ALTERNATIVE_API       0
#define configQUEUE_REGISTRY_SIZE       20
#define configUSE_QUEUE_SETS            0
#define configUSE_TIME_SLICING          1
#define configUSE_PORT_OPTIMISED_TASK_SELECTION 0
#define configUSE_TICKLESS_IDLE         0
#define configSUPPORT_STATIC_ALLOCATION 0
#define configSUPPORT_DYNAMIC_ALLOCATION 1
#define configUSE_APPLICATION_TASK_TAG  0
#define configUSE_TASK_FPU_SUPPORT      0
#define configUNIQUE_INTERRUPT_PRIORITIES 16
#define configMAX_API_CALL_INTERRUPT_PRIORITY 11

#define configINTERRUPT_CONTROLLER_BASE_ADDRESS ( 0x2C000000UL )
#define configINTERRUPT_CONTROLLER_CPU_INTERFACE_OFFSET ( 0x10000UL )

#define INCLUDE_vTaskPrioritySet        1
#define INCLUDE_uxTaskPriorityGet       1
#define INCLUDE_vTaskDelete             1
#define INCLUDE_vTaskCleanUpResources   0
#define INCLUDE_vTaskSuspend            1
#define INCLUDE_vTaskDelayUntil         1
#define INCLUDE_vTaskDelay              1
#define INCLUDE_eTaskGetState           1
#define INCLUDE_xEventGroupSetBitFromISR 1
#define INCLUDE_xTimerPendFunctionCall  0

#define configASSERT( x ) if( ( x ) == 0 ) { taskDISABLE_INTERRUPTS(); for( ;; ); }

extern void vConfigureTickInterrupt( void );
#define configSETUP_TICK_INTERRUPT() vConfigureTickInterrupt()

#endif