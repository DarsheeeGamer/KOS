# KOS Network Stack Makefile

CC = gcc
CFLAGS = -Wall -Wextra -std=c99 -fPIC -O2 -g -D_POSIX_C_SOURCE=199309L
INCLUDES = -I. -I../
LIBS = -lpthread -lm

# Source files (only the core network stack I implemented)
SOURCES = netstack.c socket.c tcp.c udp.c ip.c
OBJECTS = $(SOURCES:.c=.o)
HEADERS = netstack.h

# Targets
TARGET = libkos_netstack.so
TEST_TARGET = test_netstack

.PHONY: all clean test install

all: $(TARGET) $(TEST_TARGET)

$(TARGET): $(OBJECTS)
	$(CC) -shared -o $@ $^ $(LIBS)

$(TEST_TARGET): test_netstack.c $(TARGET)
	$(CC) $(CFLAGS) $(INCLUDES) -o $@ $< -L. -lkos_netstack $(LIBS)

%.o: %.c $(HEADERS)
	$(CC) $(CFLAGS) $(INCLUDES) -c $< -o $@

test: $(TEST_TARGET)
	LD_LIBRARY_PATH=. ./$(TEST_TARGET)

clean:
	rm -f $(OBJECTS) $(TARGET) $(TEST_TARGET)

install: $(TARGET)
	cp $(TARGET) /usr/local/lib/
	cp $(HEADERS) /usr/local/include/
	ldconfig

# Dependencies
netstack.o: netstack.c netstack.h
socket.o: socket.c netstack.h  
tcp.o: tcp.c netstack.h
udp.o: udp.c netstack.h
ip.o: ip.c netstack.h

# Debug build
debug: CFLAGS += -DDEBUG -g
debug: $(TARGET)

# Static library
static: libkos_netstack.a

libkos_netstack.a: $(OBJECTS)
	ar rcs $@ $^

.SECONDARY: $(OBJECTS)