#include <stdint.h>

#define ASSERT_MAX_COUNT    8
#define ASSERT_INFO_COUNT   4
#define TEST_POINT_COUNT    8
#define TRACE_BUFFER_SIZE   32
#define STRING_POOL_SIZE    512

typedef struct {
    const char *file_name;
    uint32_t line_number;
    const char *function_name;
    const char *assert_condition;
    uint32_t timestamp;
    uint32_t task_id;
    uint32_t error_code;
    uint32_t reserved[2];
} assert_record_t;

typedef struct {
    uint32_t count;
    uint32_t max_count;
    assert_record_t records[ASSERT_MAX_COUNT];
} assert_info_t;

typedef struct {
    uint32_t id;
    const char *name;
    uint32_t count;
    uint32_t timestamp_first;
    uint32_t timestamp_last;
    uint32_t min_duration;
    uint32_t max_duration;
    uint32_t avg_duration;
} test_point_t;

typedef struct {
    uint32_t timestamp;
    uint32_t point_id;
    uint32_t task_id;
    uint32_t event_type;
    uint32_t data;
} trace_record_t;

/* ===== 以下变量全部在 BSS 段（未初始化），运行时动态赋值 ===== */

assert_info_t g_assert_infos[ASSERT_INFO_COUNT];
test_point_t g_test_points[TEST_POINT_COUNT];
trace_record_t g_trace_buffer[TRACE_BUFFER_SIZE];
uint32_t g_trace_write_idx;

uint32_t g_system_ticks;
uint32_t g_error_count;
uint8_t  g_system_status;
uint32_t g_active_assert_idx;

char g_string_pool[STRING_POOL_SIZE];
uint32_t g_string_pool_used;

/* ===== 运行时赋值函数（模拟固件启动后填充数据） ===== */

static const char *str_pool_put(const char *s)
{
    uint32_t len = 0;
    while (s[len] != '\0') {
        len++;
    }
    if (g_string_pool_used + len + 1 > STRING_POOL_SIZE) {
        return "(overflow)";
    }
    char *dst = &g_string_pool[g_string_pool_used];
    uint32_t i;
    for (i = 0; i <= len; i++) {
        dst[i] = s[i];
    }
    g_string_pool_used += len + 1;
    return dst;
}

void firmware_init(void)
{
    g_system_ticks = 0;
    g_error_count = 0;
    g_system_status = 0x01;
    g_trace_write_idx = 0;
    g_string_pool_used = 0;
    g_active_assert_idx = 0;

    uint32_t i, j;
    for (i = 0; i < ASSERT_INFO_COUNT; i++) {
        g_assert_infos[i].count = 0;
        g_assert_infos[i].max_count = ASSERT_MAX_COUNT;
        for (j = 0; j < ASSERT_MAX_COUNT; j++) {
            g_assert_infos[i].records[j].file_name = 0;
            g_assert_infos[i].records[j].line_number = 0;
            g_assert_infos[i].records[j].function_name = 0;
            g_assert_infos[i].records[j].assert_condition = 0;
            g_assert_infos[i].records[j].timestamp = 0;
            g_assert_infos[i].records[j].task_id = 0;
            g_assert_infos[i].records[j].error_code = 0;
        }
    }

    for (i = 0; i < TEST_POINT_COUNT; i++) {
        g_test_points[i].id = 0;
        g_test_points[i].name = 0;
        g_test_points[i].count = 0;
        g_test_points[i].timestamp_first = 0;
        g_test_points[i].timestamp_last = 0;
        g_test_points[i].min_duration = 0;
        g_test_points[i].max_duration = 0;
        g_test_points[i].avg_duration = 0;
    }

    for (i = 0; i < TRACE_BUFFER_SIZE; i++) {
        g_trace_buffer[i].timestamp = 0;
        g_trace_buffer[i].point_id = 0;
        g_trace_buffer[i].task_id = 0;
        g_trace_buffer[i].event_type = 0;
        g_trace_buffer[i].data = 0;
    }
}

static void record_assert(uint32_t idx, const char *file, uint32_t line,
                          const char *func, const char *cond,
                          uint32_t ts, uint32_t task, uint32_t err)
{
    if (idx >= ASSERT_INFO_COUNT) return;
    assert_info_t *ai = &g_assert_infos[idx];
    if (ai->count >= ai->max_count) return;

    assert_record_t *r = &ai->records[ai->count];
    r->file_name = str_pool_put(file);
    r->line_number = line;
    r->function_name = str_pool_put(func);
    r->assert_condition = str_pool_put(cond);
    r->timestamp = ts;
    r->task_id = task;
    r->error_code = err;
    ai->count++;
    g_error_count++;
}

static void record_test_point(uint32_t idx, uint32_t id, const char *name,
                              uint32_t count, uint32_t ts_first,
                              uint32_t ts_last, uint32_t min_d,
                              uint32_t max_d, uint32_t avg_d)
{
    if (idx >= TEST_POINT_COUNT) return;
    test_point_t *tp = &g_test_points[idx];
    tp->id = id;
    tp->name = str_pool_put(name);
    tp->count = count;
    tp->timestamp_first = ts_first;
    tp->timestamp_last = ts_last;
    tp->min_duration = min_d;
    tp->max_duration = max_d;
    tp->avg_duration = avg_d;
}

static void record_trace(uint32_t ts, uint32_t point_id, uint32_t task_id,
                         uint32_t event_type, uint32_t data)
{
    trace_record_t *tr = &g_trace_buffer[g_trace_write_idx];
    tr->timestamp = ts;
    tr->point_id = point_id;
    tr->task_id = task_id;
    tr->event_type = event_type;
    tr->data = data;
    g_trace_write_idx = (g_trace_write_idx + 1) % TRACE_BUFFER_SIZE;
}

void simulate_runtime(void)
{
    firmware_init();

    record_assert(0, "main.c",       128, "main",         "(ptr != NULL)",     1000100, 1, 0x00010001);
    record_assert(0, "utils.c",      256, "process_data", "(len <= MAX_LEN)",  1000200, 2, 0x00020002);
    record_assert(0, "driver.c",      64, "init_hw",      "(status == OK)",    1000050, 0, 0x00030003);

    record_assert(1, "network.c",    512, "net_send",     "(buf != NULL)",    2000300, 3, 0x01010001);
    record_assert(1, "network.c",    620, "net_recv",     "(size > 0)",       2000400, 3, 0x01020002);

    record_assert(2, "storage.c",    128, "flash_write",  "(addr < end)",     3000100, 4, 0x02010001);
    record_assert(2, "storage.c",    256, "flash_read",   "(len <= bufsize)", 3000200, 4, 0x02020002);
    record_assert(2, "storage.c",    384, "flash_erase",  "(page < MAX)",     3000300, 4, 0x02030003);

    record_assert(3, "audio.c",      512, "audio_mix",    "(ch < MAX_CH)",    4000500, 5, 0x03010001);

    record_test_point(0, 1,  "TaskIdle",     15000, 1000000, 5000000, 10,    500,   50);
    record_test_point(1, 2,  "TaskMain",     8500,  1000100, 5000200, 50,   2000,  300);
    record_test_point(2, 3,  "TaskNet",      3200,  1000200, 5000400, 100,  5000,  800);
    record_test_point(3, 4,  "TaskStorage",  1200,  1000500, 5000800, 200,  8000, 1500);
    record_test_point(4, 5,  "ISR_Timer",   25000, 1000000, 4999999,  1,     50,    5);
    record_test_point(5, 6,  "ISR_UART",    12500, 1000000, 4999000,  5,    100,   20);
    record_test_point(6, 7,  "TaskAudio",    6000, 2000000, 5000100, 500,  3000, 1200);
    record_test_point(7, 8,  "TaskDisplay",  4500, 2500000, 4800000, 800,  6000, 2000);

    uint32_t i;
    for (i = 0; i < 20; i++) {
        record_trace(1000000 + i * 500, (i % 8) + 1, (i % 6), i % 2, i * 10);
    }

    g_system_ticks = 5234567;
    g_active_assert_idx = 2;
    g_system_status = 0x03;
}

void trigger_crash_assert(void)
{
    simulate_runtime();
    g_system_status = 0xFF;
    while (1);
}

int main(void)
{
    trigger_crash_assert();
    return 0;
}
