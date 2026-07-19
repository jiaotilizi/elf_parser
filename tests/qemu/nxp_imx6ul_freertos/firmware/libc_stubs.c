#include <stddef.h>

void *malloc(size_t size)
{
    (void)size;
    return NULL;
}

void free(void *ptr)
{
    (void)ptr;
}

void *calloc(size_t nmemb, size_t size)
{
    (void)nmemb;
    (void)size;
    return NULL;
}

void *realloc(void *ptr, size_t size)
{
    (void)ptr;
    (void)size;
    return NULL;
}

int abs(int j)
{
    return j < 0 ? -j : j;
}

long int labs(long int j)
{
    return j < 0 ? -j : j;
}

unsigned int rand(void)
{
    static unsigned int seed = 1;
    seed = seed * 1103515245 + 12345;
    return (unsigned int)(seed / 65536) % 32768;
}

void srand(unsigned int seed_val)
{
    (void)seed_val;
}

void *memcpy(void *dest, const void *src, size_t n)
{
    char *d = dest;
    const char *s = src;
    while (n--) *d++ = *s++;
    return dest;
}

void *memmove(void *dest, const void *src, size_t n)
{
    char *d = dest;
    const char *s = src;
    if (d < s) {
        while (n--) *d++ = *s++;
    } else if (d > s) {
        d += n;
        s += n;
        while (n--) *--d = *--s;
    }
    return dest;
}

void *memset(void *s, int c, size_t n)
{
    char *p = s;
    while (n--) *p++ = (char)c;
    return s;
}

int memcmp(const void *s1, const void *s2, size_t n)
{
    const char *a = s1;
    const char *b = s2;
    while (n--) {
        if (*a != *b) return *a - *b;
        a++;
        b++;
    }
    return 0;
}

char *strcpy(char *dest, const char *src)
{
    char *d = dest;
    while ((*d++ = *src++));
    return dest;
}

char *strncpy(char *dest, const char *src, size_t n)
{
    char *d = dest;
    while (n-- && (*d++ = *src++));
    return dest;
}

char *strcat(char *dest, const char *src)
{
    char *d = dest;
    while (*d) d++;
    while ((*d++ = *src++));
    return dest;
}

char *strncat(char *dest, const char *src, size_t n)
{
    char *d = dest;
    while (*d) d++;
    while (n-- && (*d++ = *src++));
    *d = '\0';
    return dest;
}

int strcmp(const char *s1, const char *s2)
{
    while (*s1 && *s2 && *s1 == *s2) {
        s1++;
        s2++;
    }
    return *s1 - *s2;
}

int strncmp(const char *s1, const char *s2, size_t n)
{
    while (n-- && *s1 && *s2 && *s1 == *s2) {
        s1++;
        s2++;
    }
    return *s1 - *s2;
}

size_t strlen(const char *s)
{
    const char *p = s;
    while (*p) p++;
    return p - s;
}

char *strchr(const char *s, int c)
{
    while (*s && *s != (char)c) s++;
    return (*s == (char)c) ? (char *)s : NULL;
}

char *strrchr(const char *s, int c)
{
    const char *last = NULL;
    while (*s) {
        if (*s == (char)c) last = s;
        s++;
    }
    return (char *)last;
}

void *memchr(const void *s, int c, size_t n)
{
    const char *p = s;
    while (n--) {
        if (*p == (char)c) return (void *)p;
        p++;
    }
    return NULL;
}
