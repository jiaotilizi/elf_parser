#ifndef STDLIB_H
#define STDLIB_H

#include <stddef.h>
#include <stdint.h>

static inline void *malloc(size_t size) { (void)size; return NULL; }
static inline void free(void *ptr) { (void)ptr; }
static inline void *calloc(size_t nmemb, size_t size) { (void)nmemb; (void)size; return NULL; }
static inline void *realloc(void *ptr, size_t size) { (void)ptr; (void)size; return NULL; }

static inline int abs(int x) { return x < 0 ? -x : x; }
static inline long labs(long x) { return x < 0 ? -x : x; }
static inline long long llabs(long long x) { return x < 0 ? -x : x; }

static inline int rand(void) { return 0; }
static inline void srand(unsigned int seed) { (void)seed; }

#endif