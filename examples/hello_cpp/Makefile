# Makefile for hello_cpp

CC = g++
CFLAGS = -Wall -Wextra -O2 -std=c++17 -Iinclude
TARGET = hello_cpp
SOURCES = src/main.cpp
OBJECTS = $(SOURCES:.cpp=.o)

all: $(TARGET)

$(TARGET): $(OBJECTS)
	$(CC) $(CFLAGS) -o $@ $^

clean:
	rm -f $(OBJECTS) $(TARGET)

.PHONY: all clean
