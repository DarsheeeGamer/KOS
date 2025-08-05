# Makefile for hello_c

CC = gcc
CFLAGS = -Wall -Wextra -O2 std=c11 -Iinclude
TARGET = hello_c
SOURCES = src/main.c
OBJECTS = $(SOURCES:.c=.o)

all: $(TARGET)

$(TARGET): $(OBJECTS)
	$(CC) $(CFLAGS) -o $@ $^

clean:
	rm -f $(OBJECTS) $(TARGET)

.PHONY: all clean
