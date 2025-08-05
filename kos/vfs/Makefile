
CXX = g++
CXXFLAGS = -std=c++17 -fPIC -Wall -O2
LDFLAGS = -shared

SOURCES = vfs_api.cpp vfs_core.cpp
OBJECTS = $(SOURCES:.cpp=.o)
TARGET = libkosvfs.so

all: $(TARGET)

$(TARGET): $(OBJECTS)
	$(CXX) $(LDFLAGS) -o $@ $^

%.o: %.cpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

clean:
	rm -f $(OBJECTS) $(TARGET)

.PHONY: all clean
