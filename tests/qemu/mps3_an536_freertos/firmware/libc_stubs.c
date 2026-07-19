#include <stddef.h>

void *__dso_handle = NULL;

void __attribute__((weak)) __aeabi_unwind_cpp_pr0(void) {}
void __attribute__((weak)) __aeabi_unwind_cpp_pr1(void) {}

void __attribute__((weak)) _exit(int status) {
    (void)status;
    while (1);
}

void __attribute__((weak)) abort(void) {
    while (1);
}

int __attribute__((weak)) __cxa_guard_acquire(void *guard) {
    (void)guard;
    return 1;
}

void __attribute__((weak)) __cxa_guard_release(void *guard) {
    (void)guard;
}

void __attribute__((weak)) __cxa_pure_virtual(void) {
    while (1);
}