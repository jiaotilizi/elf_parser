#include "tx_api.h"

#define DEMO_STACK_SIZE         1024
#define DEMO_QUEUE_SIZE         100
#define DEMO_BLOCK_POOL_SIZE    100
#define DEMO_BYTE_POOL_SIZE     9120

TX_THREAD               thread_0;
TX_THREAD               thread_1;
TX_THREAD               thread_2;
TX_THREAD               thread_3;
TX_THREAD               thread_4;
TX_THREAD               thread_5;
TX_THREAD               thread_6;
TX_THREAD               thread_7;
TX_THREAD               thread_8;
TX_THREAD               thread_9;
TX_QUEUE                queue_0;
TX_QUEUE                queue_1;
TX_SEMAPHORE            semaphore_0;
TX_SEMAPHORE            semaphore_1;
TX_MUTEX                mutex_0;
TX_MUTEX                mutex_1;
TX_EVENT_FLAGS_GROUP    event_flags_0;
TX_EVENT_FLAGS_GROUP    event_flags_1;
TX_BYTE_POOL            byte_pool_0;
TX_BLOCK_POOL           block_pool_0;
TX_TIMER                timer_0;
TX_TIMER                timer_1;

CHAR                    thread_0_stack[DEMO_STACK_SIZE];
CHAR                    thread_1_stack[DEMO_STACK_SIZE];
CHAR                    thread_2_stack[DEMO_STACK_SIZE];
CHAR                    thread_3_stack[DEMO_STACK_SIZE];
CHAR                    thread_4_stack[DEMO_STACK_SIZE];
CHAR                    thread_5_stack[DEMO_STACK_SIZE];
CHAR                    thread_6_stack[DEMO_STACK_SIZE];
CHAR                    thread_7_stack[DEMO_STACK_SIZE];

ULONG                   thread_0_counter;
ULONG                   thread_1_counter;
ULONG                   thread_1_messages_sent;
ULONG                   thread_2_counter;
ULONG                   thread_2_messages_received;
ULONG                   thread_3_counter;
ULONG                   thread_4_counter;
ULONG                   thread_5_counter;
ULONG                   thread_6_counter;
ULONG                   thread_7_counter;
ULONG                   thread_8_counter;
ULONG                   thread_9_counter;
ULONG                   timer_0_expiration_count;
ULONG                   timer_1_expiration_count;

ULONG                   shared_counter;
ULONG                   queue_1_data[10];

volatile ULONG          dump_ready = 0;


void    thread_0_entry(ULONG thread_input);
void    thread_1_entry(ULONG thread_input);
void    thread_2_entry(ULONG thread_input);
void    thread_3_and_4_entry(ULONG thread_input);
void    thread_5_entry(ULONG thread_input);
void    thread_6_and_7_entry(ULONG thread_input);
void    thread_8_entry(ULONG thread_input);
void    thread_9_entry(ULONG thread_input);

void    timer_0_expiration_function(ULONG timer_input);
void    timer_1_expiration_function(ULONG timer_input);


int main()
{
    tx_kernel_enter();
    return 0;
}


void    tx_application_define(void *first_unused_memory)
{
CHAR    *pointer = TX_NULL;
UINT    status;

    dump_ready = 1;

    tx_byte_pool_create(&byte_pool_0, "byte pool 0", first_unused_memory, DEMO_BYTE_POOL_SIZE);

    tx_byte_allocate(&byte_pool_0, (VOID **) &pointer, DEMO_BLOCK_POOL_SIZE, TX_NO_WAIT);

    tx_block_pool_create(&block_pool_0, "block pool 0", sizeof(ULONG), pointer, DEMO_BLOCK_POOL_SIZE);

    tx_thread_create(&thread_0, "thread 0", thread_0_entry, 0,
            thread_0_stack, DEMO_STACK_SIZE,
            1, 1, TX_NO_TIME_SLICE, TX_AUTO_START);

    tx_thread_create(&thread_1, "thread 1", thread_1_entry, 1,
            thread_1_stack, DEMO_STACK_SIZE,
            16, 16, TX_NO_TIME_SLICE, TX_AUTO_START);

    tx_thread_create(&thread_2, "thread 2", thread_2_entry, 2,
            thread_2_stack, DEMO_STACK_SIZE,
            16, 16, TX_NO_TIME_SLICE, TX_AUTO_START);

    tx_thread_create(&thread_3, "thread 3", thread_3_and_4_entry, 3,
            thread_3_stack, DEMO_STACK_SIZE,
            8, 8, TX_NO_TIME_SLICE, TX_AUTO_START);

    tx_thread_create(&thread_4, "thread 4", thread_3_and_4_entry, 4,
            thread_4_stack, DEMO_STACK_SIZE,
            8, 8, TX_NO_TIME_SLICE, TX_AUTO_START);

    tx_thread_create(&thread_5, "thread 5", thread_5_entry, 5,
            thread_5_stack, DEMO_STACK_SIZE,
            4, 4, TX_NO_TIME_SLICE, TX_AUTO_START);

    tx_thread_create(&thread_6, "thread 6", thread_6_and_7_entry, 6,
            thread_6_stack, DEMO_STACK_SIZE,
            8, 8, TX_NO_TIME_SLICE, TX_AUTO_START);

    tx_thread_create(&thread_7, "thread 7", thread_6_and_7_entry, 7,
            thread_7_stack, DEMO_STACK_SIZE,
            8, 8, TX_NO_TIME_SLICE, TX_AUTO_START);

    tx_byte_allocate(&byte_pool_0, (VOID **) &pointer, DEMO_STACK_SIZE, TX_NO_WAIT);

    tx_thread_create(&thread_8, "thread 8", thread_8_entry, 8,
            pointer, DEMO_STACK_SIZE,
            2, 2, TX_NO_TIME_SLICE, TX_AUTO_START);

    tx_byte_allocate(&byte_pool_0, (VOID **) &pointer, DEMO_STACK_SIZE, TX_NO_WAIT);

    tx_thread_create(&thread_9, "thread 9", thread_9_entry, 9,
            pointer, DEMO_STACK_SIZE,
            3, 3, TX_NO_TIME_SLICE, TX_AUTO_START);

    tx_byte_allocate(&byte_pool_0, (VOID **) &pointer, DEMO_QUEUE_SIZE*sizeof(ULONG), TX_NO_WAIT);

    tx_queue_create(&queue_0, "queue 0", TX_1_ULONG, pointer, DEMO_QUEUE_SIZE*sizeof(ULONG));

    tx_byte_allocate(&byte_pool_0, (VOID **) &pointer, 10*sizeof(ULONG), TX_NO_WAIT);

    tx_queue_create(&queue_1, "queue 1", TX_1_ULONG, pointer, 10*sizeof(ULONG));

    tx_semaphore_create(&semaphore_0, "semaphore 0", 1);

    tx_semaphore_create(&semaphore_1, "semaphore 1", 0);

    tx_event_flags_create(&event_flags_0, "event flags 0");

    tx_event_flags_create(&event_flags_1, "event flags 1");

    tx_mutex_create(&mutex_0, "mutex 0", TX_NO_INHERIT);

    tx_mutex_create(&mutex_1, "mutex 1", TX_INHERIT);

    tx_byte_allocate(&byte_pool_0, (VOID **) &pointer, DEMO_BLOCK_POOL_SIZE, TX_NO_WAIT);

    tx_block_pool_create(&block_pool_0, "block pool 0", sizeof(ULONG), pointer, DEMO_BLOCK_POOL_SIZE);

    tx_timer_create(&timer_0, "timer 0", timer_0_expiration_function, 0,
            10, 10, TX_AUTO_ACTIVATE);

    tx_timer_create(&timer_1, "timer 1", timer_1_expiration_function, 1,
            100, 100, TX_AUTO_ACTIVATE);
}


void    thread_0_entry(ULONG thread_input)
{

UINT    status;


    dump_ready = 1;

    while(1)
    {

        thread_0_counter++;

        status =  tx_event_flags_set(&event_flags_0, 0x1, TX_OR);

        if (status != TX_SUCCESS)
            break;

        status =  tx_event_flags_set(&event_flags_1, 0x2, TX_OR);

        if (status != TX_SUCCESS)
            break;

        tx_thread_sleep(10);
    }
}


void    thread_1_entry(ULONG thread_input)
{

UINT    status;


    thread_1_messages_sent = 0;
    while(1)
    {

        thread_1_counter++;

        status = tx_queue_send(&queue_0, &thread_1_messages_sent, TX_WAIT_FOREVER);

        if (status != TX_SUCCESS)
            break;

        thread_1_messages_sent++;

        status = tx_semaphore_put(&semaphore_0);
        if (status != TX_SUCCESS)
            break;

        tx_thread_sleep(1);
    }
}


void    thread_2_entry(ULONG thread_input)
{

UINT    status;
ULONG   received_message;


    thread_2_messages_received = 0;
    while(1)
    {

        thread_2_counter++;

        status = tx_queue_receive(&queue_0, &received_message, TX_WAIT_FOREVER);

        if (status != TX_SUCCESS)
            break;

        thread_2_messages_received++;

        status = tx_semaphore_put(&semaphore_1);
        if (status != TX_SUCCESS)
            break;
    }
}


void    thread_3_and_4_entry(ULONG thread_input)
{

UINT    status;


    while(1)
    {

        if (thread_input == 3)
            thread_3_counter++;
        else
            thread_4_counter++;

        status = tx_semaphore_get(&semaphore_0, TX_WAIT_FOREVER);

        if (status != TX_SUCCESS)
            break;

        status = tx_semaphore_put(&semaphore_0);
        if (status != TX_SUCCESS)
            break;

        tx_thread_sleep(5);
    }
}


void    thread_5_entry(ULONG thread_input)
{
    while(1)
    {
        thread_5_counter++;
    }
}


void    thread_6_and_7_entry(ULONG thread_input)
{

UINT    status;


    while(1)
    {

        if (thread_input == 6)
            thread_6_counter++;
        else
            thread_7_counter++;

        status = tx_mutex_get(&mutex_0, TX_WAIT_FOREVER);

        if (status != TX_SUCCESS)
            break;

        tx_thread_sleep(5);

        status = tx_mutex_put(&mutex_0);

        if (status != TX_SUCCESS)
            break;
    }
}


void    thread_8_entry(ULONG thread_input)
{

UINT    status;
ULONG   actual_flags;
ULONG   received_data;


    while(1)
    {

        thread_8_counter++;

        status = tx_event_flags_get(&event_flags_1, 0x2, TX_OR_CLEAR,
                                                &actual_flags, TX_WAIT_FOREVER);
        if (status != TX_SUCCESS)
            break;

        status = tx_mutex_get(&mutex_1, TX_WAIT_FOREVER);
        if (status != TX_SUCCESS)
            break;

        shared_counter++;

        tx_thread_sleep(5);

        status = tx_mutex_put(&mutex_1);
        if (status != TX_SUCCESS)
            break;

        status = tx_queue_receive(&queue_1, &received_data, TX_WAIT_FOREVER);
        if (status != TX_SUCCESS)
            break;

        status = tx_event_flags_set(&event_flags_1, 0x4, TX_OR);
        if (status != TX_SUCCESS)
            break;
    }
}


void    thread_9_entry(ULONG thread_input)
{

UINT    status;
ULONG   send_data;


    send_data = 0;
    while(1)
    {

        thread_9_counter++;

        status = tx_queue_send(&queue_1, &send_data, TX_WAIT_FOREVER);
        if (status != TX_SUCCESS)
            break;

        send_data++;

        tx_thread_sleep(3);
    }
}


void    timer_0_expiration_function(ULONG timer_input)
{
    (void)timer_input;
    timer_0_expiration_count++;
}

void    timer_1_expiration_function(ULONG timer_input)
{
    (void)timer_input;
    timer_1_expiration_count++;
}
