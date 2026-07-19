#ifndef STDIO_H
#define STDIO_H

#include <stddef.h>

typedef struct __FILE FILE;

#define EOF (-1)
#define BUFSIZ 512
#define FILENAME_MAX 256

int fprintf(FILE *stream, const char *format, ...);
int printf(const char *format, ...);
int sprintf(char *str, const char *format, ...);

#endif
