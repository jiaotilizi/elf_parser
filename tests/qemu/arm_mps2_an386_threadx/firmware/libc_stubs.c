void *memcpy(void *dest, const void *src, unsigned int n) {
    char *d = (char *)dest;
    const char *s = (const char *)src;
    while (n--) *d++ = *s++;
    return dest;
}

void *memset(void *ptr, int value, unsigned int n) {
    char *p = (char *)ptr;
    while (n--) *p++ = (char)value;
    return ptr;
}

void *memmove(void *dest, const void *src, unsigned int n) {
    char *d = (char *)dest;
    const char *s = (const char *)src;
    if (d < s) {
        while (n--) *d++ = *s++;
    } else {
        d += n;
        s += n;
        while (n--) *--d = *--s;
    }
    return dest;
}

int memcmp(const void *a, const void *b, unsigned int n) {
    const char *pa = (const char *)a;
    const char *pb = (const char *)b;
    while (n--) {
        if (*pa != *pb) return *pa - *pb;
        pa++;
        pb++;
    }
    return 0;
}

unsigned int strlen(const char *s) {
    unsigned int len = 0;
    while (*s++) len++;
    return len;
}

char *strcpy(char *dest, const char *src) {
    char *d = dest;
    while ((*d++ = *src++) != '\0');
    return dest;
}

int strcmp(const char *a, const char *b) {
    while (*a && *b && *a == *b) {
        a++;
        b++;
    }
    return *a - *b;
}

int strncmp(const char *a, const char *b, unsigned int n) {
    while (n && *a && *b && *a == *b) {
        a++;
        b++;
        n--;
    }
    return n ? *a - *b : 0;
}

void *malloc(unsigned int size) {
    (void)size;
    return 0;
}

void free(void *ptr) {
    (void)ptr;
}

void *calloc(unsigned int nmemb, unsigned int size) {
    (void)nmemb;
    (void)size;
    return 0;
}

void *realloc(void *ptr, unsigned int size) {
    (void)ptr;
    (void)size;
    return 0;
}

int abs(int x) {
    return x < 0 ? -x : x;
}

long labs(long x) {
    return x < 0 ? -x : x;
}

unsigned int rand(void) {
    static unsigned int seed = 1;
    seed = seed * 1103515245 + 12345;
    return seed;
}

void srand(unsigned int seed) {
    (void)seed;
}

void exit(int status) {
    (void)status;
    while (1);
}

int atexit(void (*func)(void)) {
    (void)func;
    return 0;
}