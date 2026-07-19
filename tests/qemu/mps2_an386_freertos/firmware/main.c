/*
 * main.c for QEMU Cortex-M4 + FreeRTOS V11.3.0
 *
 * Validation goals:
 *   1. Real FreeRTOS TCB_t / QueueDefinition structs in DWARF
 *   2. pxCurrentTCB is non-null after scheduler start
 *   3. Plugin can enumerate tasks via pxReadyTasksLists + suspended/delayed lists
 *   4. Plugin can enumerate queues/mutex/sem via xQueueRegistry
 *   5. Bare-metal assert_info / test_point / trace data still intact
 *   6. Comprehensive thread synchronization patterns
 *
 * Strategy:
 *   - Include shared test_firmware_bss.c (rename its main to avoid conflict)
 *   - In main(): call simulate_runtime() to fill bare-metal data
 *   - Create multiple tasks + mutex + counting sem + queue + event group
 *   - Start scheduler; tasks do complex take/give/send/recv loops with synchronization
 */

/* Rename shared main() so it doesn't conflict with our FreeRTOS main() */
#define main firmware_bss_main

#include "../../../_common/test_firmware_bss.c"

#undef main

/* FreeRTOS headers */
#include "FreeRTOS.h"
#include "task.h"
#include "queue.h"
#include "semphr.h"
#include "event_groups.h"
#include "timers.h"

/* ── RTOS-started flag for dump verification ────────── */
volatile int g_rtos_started = 0;

/* ── Global sync primitives (so they appear in ELF symbol table) ── */
SemaphoreHandle_t xMutex1     = NULL;
SemaphoreHandle_t xMutex2     = NULL;
SemaphoreHandle_t xBinarySem  = NULL;
SemaphoreHandle_t xCountSem   = NULL;
QueueHandle_t     xQueue1     = NULL;
QueueHandle_t     xQueue2     = NULL;
EventGroupHandle_t xEventGrp1 = NULL;
EventGroupHandle_t xEventGrp2 = NULL;
TimerHandle_t     xTimer1     = NULL;
TimerHandle_t     xTimer2     = NULL;

/* ── Task handles (so plugin can find them via xQueueRegistry) ── */
TaskHandle_t xSenderTaskH   = NULL;
TaskHandle_t xRecvTaskH     = NULL;
TaskHandle_t xMutexTask1H   = NULL;
TaskHandle_t xMutexTask2H   = NULL;
TaskHandle_t xSemTask1H     = NULL;
TaskHandle_t xSemTask2H     = NULL;
TaskHandle_t xEventTask1H   = NULL;
TaskHandle_t xEventTask2H   = NULL;
TaskHandle_t xTimerTaskH    = NULL;
TaskHandle_t xHighPriTaskH  = NULL;

/* Shared data */
volatile uint32_t g_shared_counter = 0;
volatile uint32_t g_queue2_counter = 0;

/* ── Task bodies ─────────────────────────────────────── */

/* Sender/Receiver pair via xQueue1 */
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

/* Mutex competition - both tasks compete for xMutex1 */
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

static void vMutexTask2(void *pvParameters)
{
    (void)pvParameters;
    while (1) {
        xSemaphoreTake(xMutex1, portMAX_DELAY);
        g_shared_counter++;
        vTaskDelay(pdMS_TO_TICKS(2));
        xSemaphoreGive(xMutex1);
        vTaskDelay(pdMS_TO_TICKS(3));
    }
}

/* Semaphore competition - binary semaphore */
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

static void vSemTask2(void *pvParameters)
{
    (void)pvParameters;
    while (1) {
        xSemaphoreTake(xBinarySem, portMAX_DELAY);
        vTaskDelay(pdMS_TO_TICKS(3));
        xSemaphoreGive(xBinarySem);
        vTaskDelay(pdMS_TO_TICKS(15));
    }
}

/* Event group synchronization */
static void vEventTask1(void *pvParameters)
{
    (void)pvParameters;
    EventBits_t uxBits;
    while (1) {
        uxBits = xEventGroupWaitBits(xEventGrp1, 0x03, pdTRUE, pdFALSE, portMAX_DELAY);
        if ((uxBits & 0x03) == 0x03) {
            xQueueSend(xQueue2, &g_queue2_counter, 0);
            g_queue2_counter++;
        }
    }
}

static void vEventTask2(void *pvParameters)
{
    (void)pvParameters;
    while (1) {
        xEventGroupSetBits(xEventGrp1, 0x02);
        vTaskDelay(pdMS_TO_TICKS(10));
    }
}

/* Timer-triggered task - receives from xQueue2 */
static void vTimerTask(void *pvParameters)
{
    (void)pvParameters;
    uint32_t data;
    while (1) {
        if (xQueueReceive(xQueue2, &data, portMAX_DELAY) == pdPASS) {
            (void)data;
        }
        xSemaphoreTake(xCountSem, portMAX_DELAY);
    }
}

/* High priority task - demonstrates priority inheritance with xMutex2 */
static void vHighPriTask(void *pvParameters)
{
    (void)pvParameters;
    while (1) {
        xSemaphoreTake(xMutex2, portMAX_DELAY);
        g_shared_counter += 10;
        vTaskDelay(pdMS_TO_TICKS(10));
        xSemaphoreGive(xMutex2);
        vTaskDelay(pdMS_TO_TICKS(50));
    }
}

/* ── Timer callbacks ─────────────────────────────────── */
static void vTimer1Callback(TimerHandle_t xTimerHandle)
{
    (void)xTimerHandle;
    xSemaphoreGive(xBinarySem);
}

static void vTimer2Callback(TimerHandle_t xTimerHandle)
{
    (void)xTimerHandle;
    xEventGroupSetBits(xEventGrp2, 0x08);
}

/* ── Real main ───────────────────────────────────────── */
int main(void)
{
    /* Step 1: fill bare-metal data structures (g_assert_infos etc.)
     * simulate_runtime() internally calls firmware_init() then fills data.
     * We override g_system_status to 0xFF to match test expectations
     * (the test expects CRASHED state, like the bare-metal scenarios). */
    simulate_runtime();
    g_system_status = 0xFF;

    /* Step 2: create sync primitives */
    xMutex1     = xSemaphoreCreateMutex();
    xMutex2     = xSemaphoreCreateMutex();
    xBinarySem  = xSemaphoreCreateBinary();
    xCountSem   = xSemaphoreCreateCounting(10, 0);
    xQueue1     = xQueueCreate(8, sizeof(uint32_t));
    xQueue2     = xQueueCreate(5, sizeof(uint32_t));
    xEventGrp1  = xEventGroupCreate();
    xEventGrp2  = xEventGroupCreate();
    xTimer1     = xTimerCreate("Timer1", pdMS_TO_TICKS(50), pdTRUE, NULL, vTimer1Callback);
    xTimer2     = xTimerCreate("Timer2", pdMS_TO_TICKS(100), pdTRUE, NULL, vTimer2Callback);

    /* Register sync primitives in queue registry so plugin can enumerate */
    vQueueAddToRegistry(xQueue1,   "Queue1");
    vQueueAddToRegistry(xQueue2,   "Queue2");
    vQueueAddToRegistry(xMutex1,   "Mutex1");
    vQueueAddToRegistry(xMutex2,   "Mutex2");
    vQueueAddToRegistry(xBinarySem,"BinSem");
    vQueueAddToRegistry(xCountSem, "CntSem");

    /* Step 3: create tasks with various priorities */
    xTaskCreate(vSenderTask,    "Sender",  256, NULL, 2, &xSenderTaskH);
    xTaskCreate(vRecvTask,      "Recv",    256, NULL, 3, &xRecvTaskH);
    xTaskCreate(vMutexTask1,    "Mutex1",  256, NULL, 1, &xMutexTask1H);
    xTaskCreate(vMutexTask2,    "Mutex2",  256, NULL, 1, &xMutexTask2H);
    xTaskCreate(vSemTask1,      "Sem1",    256, NULL, 4, &xSemTask1H);
    xTaskCreate(vSemTask2,      "Sem2",    256, NULL, 4, &xSemTask2H);
    xTaskCreate(vEventTask1,    "Event1",  256, NULL, 5, &xEventTask1H);
    xTaskCreate(vEventTask2,    "Event2",  256, NULL, 5, &xEventTask2H);
    xTaskCreate(vTimerTask,     "TimerT",  256, NULL, 6, &xTimerTaskH);
    xTaskCreate(vHighPriTask,   "HighPri", 256, NULL, 0, &xHighPriTaskH);

    /* Step 4: start timers */
    xTimerStart(xTimer1, 0);
    xTimerStart(xTimer2, 0);

    /* Step 5: initialize binary semaphore (give it once) */
    xSemaphoreGive(xBinarySem);

    /* Step 6: mark RTOS as started (for dump verification) */
    g_rtos_started = 1;

    /* Step 7: start scheduler (never returns) */
    vTaskStartScheduler();

    /* Should never reach here */
    while (1) {
    }
    return 0;
}

/* ── Hooks required by FreeRTOS config ───────────────── */
/* configCHECK_FOR_STACK_OVERFLOW=2 requires 2 arguments */
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

/* Provide required FreeRTOS helpers (some configs need these) */
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