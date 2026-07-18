/*
 * main.c for QEMU Cortex-M4 + FreeRTOS V11.3.0
 *
 * Validation goals:
 *   1. Real FreeRTOS TCB_t / QueueDefinition structs in DWARF
 *   2. pxCurrentTCB is non-null after scheduler start
 *   3. Plugin can enumerate tasks via pxReadyTasksLists + suspended/delayed lists
 *   4. Plugin can enumerate queues/mutex/sem via xQueueRegistry
 *   5. Bare-metal assert_info / test_point / trace data still intact
 *
 * Strategy:
 *   - Include shared test_firmware_bss.c (rename its main to avoid conflict)
 *   - In main(): call simulate_runtime() to fill bare-metal data
 *   - Create 4 tasks + mutex + counting sem + queue + event group
 *   - Start scheduler; tasks do simple take/give/send/recv loops
 */

/* Rename shared main() so it doesn't conflict with our FreeRTOS main() */
#define main firmware_bss_main

#include "../../_common/test_firmware_bss.c"

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
SemaphoreHandle_t xMutex      = NULL;
SemaphoreHandle_t xCountSem   = NULL;
QueueHandle_t      xQueue      = NULL;
EventGroupHandle_t xEventGrp  = NULL;
TimerHandle_t      xTimer      = NULL;

/* ── Task handles (so plugin can find them via xQueueRegistry) ── */
TaskHandle_t xLedTaskH    = NULL;
TaskHandle_t xSenderTaskH  = NULL;
TaskHandle_t xRecvTaskH    = NULL;
TaskHandle_t xIdleTaskH   = NULL;

/* Shared counter that tasks increment under mutex */
volatile uint32_t g_shared_counter = 0;

/* ── Task bodies ─────────────────────────────────────── */
static void vLedTask(void *pvParameters)
{
    (void)pvParameters;
    uint32_t loop = 0;
    while (1) {
        xSemaphoreTake(xMutex, portMAX_DELAY);
        g_shared_counter++;
        xSemaphoreGive(xMutex);

        if ((loop++ % 100) == 0) {
            xSemaphoreGive(xCountSem);
        }
        vTaskDelay(pdMS_TO_TICKS(10));
    }
}

static void vSenderTask(void *pvParameters)
{
    (void)pvParameters;
    uint32_t value = 0;
    while (1) {
        value++;
        xQueueSend(xQueue, &value, 0);
        xEventGroupSetBits(xEventGrp, 0x01);
        vTaskDelay(pdMS_TO_TICKS(5));
    }
}

static void vRecvTask(void *pvParameters)
{
    (void)pvParameters;
    uint32_t received = 0;
    while (1) {
        if (xQueueReceive(xQueue, &received, portMAX_DELAY) == pdPASS) {
            (void)received;
        }
        xSemaphoreTake(xCountSem, portMAX_DELAY);
    }
}

static void vIdleTask(void *pvParameters)
{
    (void)pvParameters;
    while (1) {
        vTaskDelay(pdMS_TO_TICKS(100));
    }
}

/* ── Timer callback (just keeps timer alive) ─────────── */
static void vTimerCallback(TimerHandle_t xTimerHandle)
{
    (void)xTimerHandle;
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
    xMutex     = xSemaphoreCreateMutex();
    xCountSem  = xSemaphoreCreateCounting(10, 0);
    xQueue     = xQueueCreate(8, sizeof(uint32_t));
    xEventGrp  = xEventGroupCreate();
    xTimer     = xTimerCreate("Timer", pdMS_TO_TICKS(100), pdTRUE, NULL, vTimerCallback);

    /* Register queue/mutex/sem in queue registry so plugin can enumerate */
    vQueueAddToRegistry(xQueue,   "Queue");
    vQueueAddToRegistry(xMutex,   "Mutex");
    vQueueAddToRegistry(xCountSem,"CountSem");

    /* Step 3: create tasks (priorities 0-3; configMAX_PRIORITIES=5) */
    xTaskCreate(vLedTask,    "Led",     256, NULL, 1, &xLedTaskH);
    xTaskCreate(vSenderTask, "Sender",  256, NULL, 2, &xSenderTaskH);
    xTaskCreate(vRecvTask,   "Recv",    256, NULL, 3, &xRecvTaskH);
    xTaskCreate(vIdleTask,   "IdleX",   128, NULL, 0, &xIdleTaskH);

    /* Step 4: start timer */
    xTimerStart(xTimer, 0);

    /* Step 5: mark RTOS as started (for dump verification) */
    g_rtos_started = 1;

    /* Step 6: start scheduler (never returns) */
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
