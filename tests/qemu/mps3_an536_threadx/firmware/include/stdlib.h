#ifndef STDLIB_H
#define STDLIB_H

#include <stddef.h>

static inline void *malloc(size_t size) { (void)size; return NULL; }
static inline void free(void *ptr) { (void)ptr; }
static inline void *calloc(size_t nmemb, size_t size) { (void)nmemb; (void)size; return NULL; }
static inline void *realloc(void *ptr, size_t size) { (void)ptr; (void)size; return NULL; }

#endif