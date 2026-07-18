#include <stdint.h>
#include "FreeRTOS.h"
#include "task.h"
#include "queue.h"
#include "semphr.h"
#include "event_groups.h"

volatile int g_system_status = 0;
volatile int g_rtos_started = 0;

#define NVIC_ST_CTRL_R          (*((volatile uint32_t *) 0xE000E010))
#define NVIC_ST_RELOAD_R        (*((volatile uint32_t *) 0xE000E014))
#define NVIC_ST_CURRENT_R       (*((volatile uint32_t *) 0xE000E018))
#define NVIC_ST_CTRL_COUNT      0x00010000
#define NVIC_ST_CTRL_CLK_SRC    0x00000004
#define NVIC_ST_CTRL_INTEN      0x00000002
#define NVIC_ST_CTRL_ENABLE     0x00000001

void vConfigureTickInterrupt( void ) {
    NVIC_ST_CTRL_R = 0;
    NVIC_ST_RELOAD_R = (configCPU_CLOCK_HZ / configTICK_RATE_HZ) - 1;
    NVIC_ST_CURRENT_R = 0;
    NVIC_ST_CTRL_R = NVIC_ST_CTRL_CLK_SRC | NVIC_ST_CTRL_INTEN | NVIC_ST_CTRL_ENABLE;
}

SemaphoreHandle_t xMutex1     = NULL;
SemaphoreHandle_t xMutex2     = NULL;
SemaphoreHandle_t xBinarySem  = NULL;
SemaphoreHandle_t xCountSem   = NULL;
QueueHandle_t     xQueue1     = NULL;
QueueHandle_t     xQueue2     = NULL;
EventGroupHandle_t xEventGrp1 = NULL;
EventGroupHandle_t xEventGrp2 = NULL;

TaskHandle_t xSenderTaskH   = NULL;
TaskHandle_t xRecvTaskH     = NULL;
TaskHandle_t xMutexTask1H   = NULL;
TaskHandle_t xMutexTask2H   = NULL;
TaskHandle_t xSemTask1H     = NULL;
TaskHandle_t xSemTask2H     = NULL;
TaskHandle_t xEventTask1H   = NULL;
TaskHandle_t xEventTask2H   = NULL;
TaskHandle_t xHighPriTaskH  = NULL;

volatile uint32_t g_shared_counter = 0;
volatile uint32_t g_queue2_counter = 0;

static void vSenderTask(void *pvParameters) {
    (void)pvParameters;
    uint32_t value = 0;
    while (1) {
        value++;
        xQueueSend(xQueue1, &value, portMAX_DELAY);
        xEventGroupSetBits(xEventGrp1, 0x01);
        vTaskDelay(pdMS_TO_TICKS(5));
    }
}

static void vRecvTask(void *pvParameters) {
    (void)pvParameters;
    uint32_t received = 0;
    while (1) {
        if (xQueueReceive(xQueue1, &received, portMAX_DELAY) == pdPASS) {
            (void)received;
        }
        xSemaphoreGive(xCountSem);
    }
}

static void vMutexTask1(void *pvParameters) {
    (void)pvParameters;
    while (1) {
        xSemaphoreTake(xMutex1, portMAX_DELAY);
        g_shared_counter++;
        vTaskDelay(pdMS_TO_TICKS(3));
        xSemaphoreGive(xMutex1);
        vTaskDelay(pdMS_TO_TICKS(2));
    }
}

static void vMutexTask2(void *pvParameters) {
    (void)pvParameters;
    while (1) {
        xSemaphoreTake(xMutex1, portMAX_DELAY);
        g_shared_counter++;
        vTaskDelay(pdMS_TO_TICKS(2));
        xSemaphoreGive(xMutex1);
        vTaskDelay(pdMS_TO_TICKS(3));
    }
}

static void vSemTask1(void *pvParameters) {
    (void)pvParameters;
    while (1) {
        xSemaphoreTake(xBinarySem, portMAX_DELAY);
        vTaskDelay(pdMS_TO_TICKS(5));
        xSemaphoreGive(xBinarySem);
        vTaskDelay(pdMS_TO_TICKS(10));
    }
}

static void vSemTask2(void *pvParameters) {
    (void)pvParameters;
    while (1) {
        xSemaphoreTake(xBinarySem, portMAX_DELAY);
        vTaskDelay(pdMS_TO_TICKS(3));
        xSemaphoreGive(xBinarySem);
        vTaskDelay(pdMS_TO_TICKS(15));
    }
}

static void vEventTask1(void *pvParameters) {
    (void)pvParameters;
    EventBits_t uxBits;
    while (1) {
        uxBits = xEventGroupWaitBits(xEventGrp1, 0x03, pdTRUE, pdFALSE, portMAX_DELAY);
        if ((uxBits & 0x03) == 0x03) {
            uint32_t count = g_queue2_counter;
            xQueueSend(xQueue2, &count, 0);
            g_queue2_counter++;
        }
    }
}

static void vEventTask2(void *pvParameters) {
    (void)pvParameters;
    while (1) {
        xEventGroupSetBits(xEventGrp1, 0x02);
        vTaskDelay(pdMS_TO_TICKS(10));
    }
}

static void vHighPriTask(void *pvParameters) {
    (void)pvParameters;
    while (1) {
        xSemaphoreTake(xMutex2, portMAX_DELAY);
        g_shared_counter += 10;
        vTaskDelay(pdMS_TO_TICKS(10));
        xSemaphoreGive(xMutex2);
        vTaskDelay(pdMS_TO_TICKS(50));
    }
}

void vApplicationStackOverflowHook(TaskHandle_t pxTask, char *pcTaskName) {
    (void)pxTask;
    (void)pcTaskName;
    while (1);
}

void vApplicationMallocFailedHook(void) {
    while (1);
}

void vApplicationIdleHook(void) {
}

void vApplicationTickHook(void) {
}

void vAssertCalled(const char *pcFile, unsigned long ulLine) {
    (void)pcFile;
    (void)ulLine;
    taskDISABLE_INTERRUPTS();
    while (1);
}

void vApplicationGetIdleTaskMemory(StaticTask_t **ppxIdleTaskTCBBuffer, StackType_t **ppxIdleTaskStackBuffer, uint32_t *pulIdleTaskStackSize) {
    (void)ppxIdleTaskTCBBuffer;
    (void)ppxIdleTaskStackBuffer;
    (void)pulIdleTaskStackSize;
}

int main(void) {
    g_system_status = 0xFF;

    xMutex1     = xSemaphoreCreateMutex();
    xMutex2     = xSemaphoreCreateMutex();
    xBinarySem  = xSemaphoreCreateBinary();
    xCountSem   = xSemaphoreCreateCounting(10, 0);
    xQueue1     = xQueueCreate(8, sizeof(uint32_t));
    xQueue2     = xQueueCreate(5, sizeof(uint32_t));
    xEventGrp1  = xEventGroupCreate();
    xEventGrp2  = xEventGroupCreate();

    vQueueAddToRegistry(xQueue1,   "Queue1");
    vQueueAddToRegistry(xQueue2,   "Queue2");
    vQueueAddToRegistry(xMutex1,   "Mutex1");
    vQueueAddToRegistry(xMutex2,   "Mutex2");
    vQueueAddToRegistry(xBinarySem,"BinSem");
    vQueueAddToRegistry(xCountSem, "CntSem");

    xTaskCreate(vSenderTask,    "Sender",  256, NULL, 2, &xSenderTaskH);
    xTaskCreate(vRecvTask,      "Recv",    256, NULL, 3, &xRecvTaskH);
    xTaskCreate(vMutexTask1,    "Mutex1",  256, NULL, 1, &xMutexTask1H);
    xTaskCreate(vMutexTask2,    "Mutex2",  256, NULL, 1, &xMutexTask2H);
    xTaskCreate(vSemTask1,      "Sem1",    256, NULL, 4, &xSemTask1H);
    xTaskCreate(vSemTask2,      "Sem2",    256, NULL, 4, &xSemTask2H);
    xTaskCreate(vEventTask1,    "Event1",  256, NULL, 5, &xEventTask1H);
    xTaskCreate(vEventTask2,    "Event2",  256, NULL, 5, &xEventTask2H);
    xTaskCreate(vHighPriTask,   "HighPri", 256, NULL, 0, &xHighPriTaskH);

    xSemaphoreGive(xBinarySem);

    g_rtos_started = 1;

    vTaskStartScheduler();

    return 0;
}