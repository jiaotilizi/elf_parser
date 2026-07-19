#include <stddef.h>

void atexit(void (*func)(void))
{
    (void)func;
}

void exit(int status)
{
    (void)status;
    while (1);
}

void *memcpy(void *dest, const void *src, size_t n)
{
    char *d = dest;
    const char *s = src;
    while (n--) *d++ = *s++;
    return dest;
}

void *memset(void *s, int c, size_t n)
{
    char *p = s;
    while (n--) *p++ = (char)c;
    return s;
}

void *malloc(size_t size)
{
    (void)size;
    return NULL;
}

void free(void *ptr)
{
    (void)ptr;
}
