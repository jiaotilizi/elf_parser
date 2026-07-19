#ifndef STDLIB_H
#define STDLIB_H

#include <stddef.h>

void *malloc(size_t size);
void free(void *ptr);
void *calloc(size_t nmemb, size_t size);
void *realloc(void *ptr, size_t size);
int abs(int j);
long int labs(long int j);
unsigned int rand(void);
void srand(unsigned int seed);

#endif
