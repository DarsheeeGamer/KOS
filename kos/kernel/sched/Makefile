# KOS Kernel Scheduler Makefile

CC = gcc
CFLAGS = -fPIC -O2 -g -Wall -Wextra -std=c99
LDFLAGS = -shared -lpthread -lm
TARGET = libkos_sched.so
TEST_TARGET = test_scheduler
SOURCES = core.c cfs.c rt.c fair.c
OBJECTS = $(SOURCES:.c=.o)
HEADERS = sched.h
TEST_SOURCES = test_scheduler.c

.PHONY: all clean test install

all: $(TARGET) $(TEST_TARGET)

$(TARGET): $(OBJECTS)
	$(CC) $(LDFLAGS) -o $@ $^

$(TEST_TARGET): $(TEST_SOURCES) $(OBJECTS)
	$(CC) $(CFLAGS) -o $@ $^ -lpthread -lm

%.o: %.c $(HEADERS)
	$(CC) $(CFLAGS) -c $< -o $@

clean:
	rm -f $(OBJECTS) $(TARGET) $(TEST_TARGET)

test: $(TARGET)
	python3 sched_wrapper.py

test-c: $(TEST_TARGET)
	./$(TEST_TARGET)

install: $(TARGET)
	cp $(TARGET) /usr/local/lib/
	cp $(HEADERS) /usr/local/include/

# Debug build
debug: CFLAGS += -DDEBUG -fsanitize=address
debug: LDFLAGS += -fsanitize=address
debug: $(TARGET)

# Static analysis
analyze:
	cppcheck --enable=all --std=c99 $(SOURCES)

# Documentation
docs:
	doxygen Doxyfile

.SUFFIXES: .c .o