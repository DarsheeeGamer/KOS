# Makefile for KOS Distributed GPU System
# This builds the REAL implementation with CUDA, NCCL, and MPI

# Compiler settings
CXX = g++
NVCC = nvcc
MPICXX = mpic++

# CUDA settings (adjust path if needed)
CUDA_PATH ?= /usr/local/cuda
CUDA_INC = -I$(CUDA_PATH)/include
CUDA_LIB = -L$(CUDA_PATH)/lib64

# NCCL settings (adjust if needed)
NCCL_INC = -I/usr/include
NCCL_LIB = -L/usr/lib/x86_64-linux-gnu

# Compiler flags
CXXFLAGS = -std=c++14 -O3 -Wall -fopenmp
NVCCFLAGS = -std=c++14 -O3 -arch=sm_75 -Xcompiler -fopenmp
LDFLAGS = $(CUDA_LIB) $(NCCL_LIB) -lcudart -lcublas -lcudnn -lnccl -lmpi -lgomp

# Include directories
INCLUDES = $(CUDA_INC) $(NCCL_INC)

# Source files
SOURCES = distributed_training.cpp
CUDA_SOURCES = 

# Object files
OBJECTS = $(SOURCES:.cpp=.o) $(CUDA_SOURCES:.cu=.o)

# Target executable
TARGET = kos_distributed_gpu

# Python binding library
PYTHON_LIB = kos_gpu.so

# Default target
all: $(TARGET)

# Build executable
$(TARGET): $(OBJECTS)
	$(MPICXX) $(OBJECTS) -o $@ $(LDFLAGS)

# Compile C++ files
%.o: %.cpp
	$(MPICXX) $(CXXFLAGS) $(INCLUDES) -c $< -o $@

# Compile CUDA files
%.o: %.cu
	$(NVCC) $(NVCCFLAGS) $(INCLUDES) -c $< -o $@

# Build Python bindings
python: $(PYTHON_LIB)

$(PYTHON_LIB): python_bindings.cpp gpu_manager.cpp
	$(CXX) -shared -fPIC $(CXXFLAGS) $(INCLUDES) \
		-I/usr/include/python3.8 \
		python_bindings.cpp \
		-o $@ $(LDFLAGS) -lpython3.8

# Run single node test
test: $(TARGET)
	./$(TARGET)

# Run multi-node test (2 nodes on same machine for testing)
test-multi: $(TARGET)
	mpirun -np 2 ./$(TARGET)

# Run on actual cluster (example for SLURM)
run-cluster: $(TARGET)
	sbatch --nodes=2 --gres=gpu:4 --ntasks-per-node=1 ./run_distributed.sh

# Benchmark
benchmark: $(TARGET)
	@echo "Running benchmark on single node..."
	./$(TARGET) --benchmark
	@echo "\nRunning benchmark on 2 nodes..."
	mpirun -np 2 ./$(TARGET) --benchmark

# Clean
clean:
	rm -f *.o $(TARGET) $(PYTHON_LIB)

# Check CUDA installation
check-cuda:
	@echo "CUDA Path: $(CUDA_PATH)"
	@echo "NVCC Version:"
	@$(NVCC) --version
	@echo "\nGPU Info:"
	@nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv

# Check NCCL installation
check-nccl:
	@echo "Checking NCCL..."
	@ldconfig -p | grep nccl || echo "NCCL not found in ldconfig"
	@ls -la /usr/lib/x86_64-linux-gnu/libnccl* 2>/dev/null || echo "NCCL libs not found"

# Check MPI installation
check-mpi:
	@echo "MPI Version:"
	@mpirun --version

# Install dependencies (Ubuntu/Debian)
install-deps:
	@echo "Installing CUDA, NCCL, and MPI dependencies..."
	@echo "Run these commands:"
	@echo "  sudo apt-get update"
	@echo "  sudo apt-get install -y cuda-toolkit-11-8"
	@echo "  sudo apt-get install -y libnccl2 libnccl-dev"
	@echo "  sudo apt-get install -y openmpi-bin openmpi-common libopenmpi-dev"
	@echo "  sudo apt-get install -y python3-dev python3-pip"
	@echo "  pip3 install pybind11 numpy"

.PHONY: all clean test test-multi run-cluster benchmark check-cuda check-nccl check-mpi install-deps python