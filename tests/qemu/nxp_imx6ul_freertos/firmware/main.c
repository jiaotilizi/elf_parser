/*
 * main.c for NXP i.MX6UL (Cortex-A7, ARMv7-A) + FreeRTOS V11.3.0
 *
 * Validation goals:
 *   1. Real FreeRTOS TCB_t / QueueDefinition structs in DWARF
 *   2. pxCurrentTCB is non-null after scheduler start
 *   3. Plugin can enumerate tasks via pxReadyTasksLists
 *   4. Plugin can enumerate queues/mutex/sem via xQueueRegistry
 *   5. Bare-metal assert_info / test_point / trace data still intact
 */

#define main firmware_bss_main
#include "../../../_common/test_firmware_bss.c"
#undef main

#include "FreeRTOS.h"
#include "task.h"
#include "queue.h"
#include "semphr.h"
#include "event_groups.h"
#include "timers.h"

volatile int g_rtos_started = 0;

SemaphoreHandle_t xMutex1     = NULL;
SemaphoreHandle_t xBinarySem  = NULL;
SemaphoreHandle_t xCountSem   = NULL;
QueueHandle_t     xQueue1     = NULL;
QueueHandle_t     xQueue2     = NULL;
EventGroupHandle_t xEventGrp1 = NULL;
TimerHandle_t     xTimer1     = NULL;

TaskHandle_t xSenderTaskH   = NULL;
TaskHandle_t xRecvTaskH     = NULL;
TaskHandle_t xMutexTask1H   = NULL;
TaskHandle_t xSemTask1H     = NULL;

volatile uint32_t g_shared_counter = 0;

static void vSenderTask(void *pvParameters)
{
    (void)pvParameters;
    uint32_t value = 0;
    while (1) {
        value++;
        xQueueSend(xQueue1, &value, portMAX_DELAY);
        xEventGroupSetBits(xEventGrp1, 0x01);
        vTaskDelay(pdMS_TO_TICKS(5));
    }
}

static void vRecvTask(void *pvParameters)
{
    (void)pvParameters;
    uint32_t received = 0;
    while (1) {
        if (xQueueReceive(xQueue1, &received, portMAX_DELAY) == pdPASS) {
            (void)received;
        }
        xSemaphoreGive(xCountSem);
    }
}

static void vMutexTask1(void *pvParameters)
{
    (void)pvParameters;
    while (1) {
        xSemaphoreTake(xMutex1, portMAX_DELAY);
        g_shared_counter++;
        vTaskDelay(pdMS_TO_TICKS(3));
        xSemaphoreGive(xMutex1);
        vTaskDelay(pdMS_TO_TICKS(2));
    }
}

static void vSemTask1(void *pvParameters)
{
    (void)pvParameters;
    while (1) {
        xSemaphoreTake(xBinarySem, portMAX_DELAY);
        vTaskDelay(pdMS_TO_TICKS(5));
        xSemaphoreGive(xBinarySem);
        vTaskDelay(pdMS_TO_TICKS(10));
    }
}

static void vTimer1Callback(TimerHandle_t xTimerHandle)
{
    (void)xTimerHandle;
    xSemaphoreGive(xBinarySem);
}

int main(void)
{
    simulate_runtime();
    g_system_status = 0xFF;

    xMutex1     = xSemaphoreCreateMutex();
    xBinarySem  = xSemaphoreCreateBinary();
    xCountSem   = xSemaphoreCreateCounting(10, 0);
    xQueue1     = xQueueCreate(8, sizeof(uint32_t));
    xQueue2     = xQueueCreate(5, sizeof(uint32_t));
    xEventGrp1  = xEventGroupCreate();
    xTimer1     = xTimerCreate("Timer1", pdMS_TO_TICKS(50), pdTRUE, NULL, vTimer1Callback);

    vQueueAddToRegistry(xQueue1,   "Queue1");
    vQueueAddToRegistry(xQueue2,   "Queue2");
    vQueueAddToRegistry(xMutex1,   "Mutex1");
    vQueueAddToRegistry(xBinarySem,"BinSem");
    vQueueAddToRegistry(xCountSem, "CntSem");

    xTaskCreate(vSenderTask,    "Sender",  256, NULL, 2, &xSenderTaskH);
    xTaskCreate(vRecvTask,      "Recv",    256, NULL, 3, &xRecvTaskH);
    xTaskCreate(vMutexTask1,    "Mutex1",  256, NULL, 1, &xMutexTask1H);
    xTaskCreate(vSemTask1,      "Sem1",    256, NULL, 4, &xSemTask1H);

    xTimerStart(xTimer1, 0);
    xSemaphoreGive(xBinarySem);
    g_rtos_started = 1;

    vTaskStartScheduler();

    while (1) {
    }
    return 0;
}

void vApplicationStackOverflowHook(TaskHandle_t xTask, char *pcTaskName)
{
    (void)xTask;
    (void)pcTaskName;
    while (1) {
    }
}

void vApplicationMallocFailedHook(void)
{
    while (1) {
    }
}

void vApplicationGetIdleTaskMemory(StaticTask_t **ppxIdleTaskTCBBuffer,
                                   StackType_t **ppxIdleTaskStackBuffer,
                                   uint32_t *pulIdleTaskStackSize)
{
    (void)ppxIdleTaskTCBBuffer;
    (void)ppxIdleTaskStackBuffer;
    (void)pulIdleTaskStackSize;
}

void vApplicationGetTimerTaskMemory(StaticTask_t **ppxTimerTaskTCBBuffer,
                                    StackType_t **ppxTimerTaskStackBuffer,
                                    uint32_t *pulTimerTaskStackSize)
{
    (void)ppxTimerTaskTCBBuffer;
    (void)ppxTimerTaskStackBuffer;
    (void)pulTimerTaskStackSize;
}
