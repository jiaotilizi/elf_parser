unsigned int g_system_ticks = 1234567;

struct TestPoint {
    int id;
    char name[16];
    unsigned int timestamp;
};

struct TestPoint test_points[5] = {
    {1, "init", 1000000},
    {2, "config", 2000000},
    {3, "ready", 3000000},
    {4, "run", 4000000},
    {5, "done", 5000000},
};

struct TraceRecord {
    unsigned int timestamp;
    int event_id;
    char message[32];
};

struct TraceRecord trace_buffer[10];
int trace_index = 0;

static inline void trace_log(int event_id, const char* msg) {
    if (trace_index < 10) {
        trace_buffer[trace_index].timestamp = g_system_ticks;
        trace_buffer[trace_index].event_id = event_id;
        int i = 0;
        while (msg[i] && i < 31) {
            trace_buffer[trace_index].message[i] = msg[i];
            i++;
        }
        trace_buffer[trace_index].message[i] = '\0';
        trace_index++;
    }
}

void assert_failed(const char* file, int line) {
    (void)file;
    (void)line;
    while (1);
}

int main(void) {
    g_system_ticks = 1234567;
    
    trace_log(1, "STM32 init started");
    g_system_ticks += 1000;
    
    trace_log(2, "Peripherals configured");
    g_system_ticks += 2000;
    
    trace_log(3, "System ready");
    g_system_ticks += 3000;
    
    while (1) {
        g_system_ticks++;
    }
}
