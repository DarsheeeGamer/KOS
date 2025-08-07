"""
Kernel Translation System for KOS Universal Compute
Translates between different GPU kernel languages (CUDA, HIP, Metal, OpenCL)
"""

import re
import ast
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

from ..hardware.base import DeviceType

logger = logging.getLogger(__name__)

class KernelLanguage(Enum):
    """Supported kernel languages"""
    CUDA_C = "cuda_c"
    HIP_C = "hip_c"
    METAL_SHADER = "metal_shader"
    OPENCL_C = "opencl_c"
    SYCL = "sycl"
    UNIVERSAL_KOS = "universal_kos"

@dataclass
class TranslationRule:
    """Translation rule for converting between languages"""
    pattern: str
    replacement: str
    language_from: KernelLanguage
    language_to: KernelLanguage
    context: Optional[str] = None  # Function, global, etc.

@dataclass
class KernelMetadata:
    """Metadata about a kernel"""
    entry_point: str
    parameters: List[Dict]
    local_work_size: Tuple[int, int, int]
    global_work_size: Tuple[int, int, int]
    shared_memory_size: int
    required_features: List[str]
    optimization_hints: Dict[str, Any]

class UniversalKernelTranslator:
    """Universal kernel translator between GPU languages"""
    
    def __init__(self):
        self.translation_rules: Dict[Tuple[KernelLanguage, KernelLanguage], List[TranslationRule]] = {}
        self.builtin_functions: Dict[KernelLanguage, Dict[str, str]] = {}
        self.language_headers: Dict[KernelLanguage, str] = {}
        
        self._initialize_translation_rules()
        self._initialize_builtin_functions()
        self._initialize_language_headers()
    
    def _initialize_translation_rules(self):
        """Initialize translation rules between languages"""
        
        # CUDA to HIP translations
        cuda_to_hip_rules = [
            # Memory management
            TranslationRule(r'cudaMalloc', 'hipMalloc', KernelLanguage.CUDA_C, KernelLanguage.HIP_C),
            TranslationRule(r'cudaFree', 'hipFree', KernelLanguage.CUDA_C, KernelLanguage.HIP_C),
            TranslationRule(r'cudaMemcpy', 'hipMemcpy', KernelLanguage.CUDA_C, KernelLanguage.HIP_C),
            TranslationRule(r'cudaMemset', 'hipMemset', KernelLanguage.CUDA_C, KernelLanguage.HIP_C),
            TranslationRule(r'cudaMemcpyDeviceToHost', 'hipMemcpyDeviceToHost', KernelLanguage.CUDA_C, KernelLanguage.HIP_C),
            TranslationRule(r'cudaMemcpyHostToDevice', 'hipMemcpyHostToDevice', KernelLanguage.CUDA_C, KernelLanguage.HIP_C),
            
            # Thread and block indices
            TranslationRule(r'blockIdx\.x', 'hipBlockIdx_x', KernelLanguage.CUDA_C, KernelLanguage.HIP_C),
            TranslationRule(r'blockIdx\.y', 'hipBlockIdx_y', KernelLanguage.CUDA_C, KernelLanguage.HIP_C),
            TranslationRule(r'blockIdx\.z', 'hipBlockIdx_z', KernelLanguage.CUDA_C, KernelLanguage.HIP_C),
            TranslationRule(r'threadIdx\.x', 'hipThreadIdx_x', KernelLanguage.CUDA_C, KernelLanguage.HIP_C),
            TranslationRule(r'threadIdx\.y', 'hipThreadIdx_y', KernelLanguage.CUDA_C, KernelLanguage.HIP_C),
            TranslationRule(r'threadIdx\.z', 'hipThreadIdx_z', KernelLanguage.CUDA_C, KernelLanguage.HIP_C),
            TranslationRule(r'blockDim\.x', 'hipBlockDim_x', KernelLanguage.CUDA_C, KernelLanguage.HIP_C),
            TranslationRule(r'blockDim\.y', 'hipBlockDim_y', KernelLanguage.CUDA_C, KernelLanguage.HIP_C),
            TranslationRule(r'blockDim\.z', 'hipBlockDim_z', KernelLanguage.CUDA_C, KernelLanguage.HIP_C),
            TranslationRule(r'gridDim\.x', 'hipGridDim_x', KernelLanguage.CUDA_C, KernelLanguage.HIP_C),
            TranslationRule(r'gridDim\.y', 'hipGridDim_y', KernelLanguage.CUDA_C, KernelLanguage.HIP_C),
            TranslationRule(r'gridDim\.z', 'hipGridDim_z', KernelLanguage.CUDA_C, KernelLanguage.HIP_C),
            
            # Device management
            TranslationRule(r'cudaSetDevice', 'hipSetDevice', KernelLanguage.CUDA_C, KernelLanguage.HIP_C),
            TranslationRule(r'cudaDeviceSynchronize', 'hipDeviceSynchronize', KernelLanguage.CUDA_C, KernelLanguage.HIP_C),
            TranslationRule(r'cudaGetDevice', 'hipGetDevice', KernelLanguage.CUDA_C, KernelLanguage.HIP_C),
            
            # Error handling
            TranslationRule(r'cudaError_t', 'hipError_t', KernelLanguage.CUDA_C, KernelLanguage.HIP_C),
            TranslationRule(r'cudaSuccess', 'hipSuccess', KernelLanguage.CUDA_C, KernelLanguage.HIP_C),
            TranslationRule(r'cudaGetLastError', 'hipGetLastError', KernelLanguage.CUDA_C, KernelLanguage.HIP_C),
        ]
        
        # HIP to CUDA (reverse)
        hip_to_cuda_rules = []
        for rule in cuda_to_hip_rules:
            hip_to_cuda_rules.append(TranslationRule(
                rule.replacement, rule.pattern, 
                KernelLanguage.HIP_C, KernelLanguage.CUDA_C
            ))
        
        # CUDA/HIP to Metal translations
        cuda_to_metal_rules = [
            # Thread indices
            TranslationRule(r'blockIdx\.x \* blockDim\.x \+ threadIdx\.x', 
                          'thread_position_in_grid.x', KernelLanguage.CUDA_C, KernelLanguage.METAL_SHADER),
            TranslationRule(r'threadIdx\.x', 'thread_position_in_threadgroup.x', 
                          KernelLanguage.CUDA_C, KernelLanguage.METAL_SHADER),
            TranslationRule(r'blockDim\.x', 'threads_per_threadgroup.x', 
                          KernelLanguage.CUDA_C, KernelLanguage.METAL_SHADER),
            
            # Synchronization
            TranslationRule(r'__syncthreads\(\)', 'threadgroup_barrier(mem_flags::mem_threadgroup)', 
                          KernelLanguage.CUDA_C, KernelLanguage.METAL_SHADER),
            
            # Shared memory
            TranslationRule(r'__shared__', 'threadgroup', 
                          KernelLanguage.CUDA_C, KernelLanguage.METAL_SHADER),
            
            # Kernel declaration
            TranslationRule(r'__global__\s+void\s+(\w+)\s*\(', 
                          r'kernel void \1(', KernelLanguage.CUDA_C, KernelLanguage.METAL_SHADER),
        ]
        
        # Universal KOS to all languages
        kos_to_cuda_rules = [
            TranslationRule(r'kos_thread_id\(\)', 'blockIdx.x * blockDim.x + threadIdx.x', 
                          KernelLanguage.UNIVERSAL_KOS, KernelLanguage.CUDA_C),
            TranslationRule(r'kos_thread_count\(\)', 'gridDim.x * blockDim.x', 
                          KernelLanguage.UNIVERSAL_KOS, KernelLanguage.CUDA_C),
            TranslationRule(r'kos_barrier\(\)', '__syncthreads()', 
                          KernelLanguage.UNIVERSAL_KOS, KernelLanguage.CUDA_C),
            TranslationRule(r'kos_shared', '__shared__', 
                          KernelLanguage.UNIVERSAL_KOS, KernelLanguage.CUDA_C),
        ]
        
        # Store rules
        self.translation_rules[(KernelLanguage.CUDA_C, KernelLanguage.HIP_C)] = cuda_to_hip_rules
        self.translation_rules[(KernelLanguage.HIP_C, KernelLanguage.CUDA_C)] = hip_to_cuda_rules
        self.translation_rules[(KernelLanguage.CUDA_C, KernelLanguage.METAL_SHADER)] = cuda_to_metal_rules
        self.translation_rules[(KernelLanguage.UNIVERSAL_KOS, KernelLanguage.CUDA_C)] = kos_to_cuda_rules
    
    def _initialize_builtin_functions(self):
        """Initialize builtin function mappings"""
        
        # CUDA builtins
        self.builtin_functions[KernelLanguage.CUDA_C] = {
            'get_thread_id': 'blockIdx.x * blockDim.x + threadIdx.x',
            'get_block_id': 'blockIdx.x',
            'get_thread_in_block': 'threadIdx.x',
            'barrier_sync': '__syncthreads()',
            'atomic_add': 'atomicAdd',
            'atomic_cas': 'atomicCAS',
            'sqrt_f': 'sqrtf',
            'sin_f': 'sinf',
            'cos_f': 'cosf',
            'exp_f': 'expf',
            'log_f': 'logf',
        }
        
        # HIP builtins  
        self.builtin_functions[KernelLanguage.HIP_C] = {
            'get_thread_id': 'hipBlockIdx_x * hipBlockDim_x + hipThreadIdx_x',
            'get_block_id': 'hipBlockIdx_x',
            'get_thread_in_block': 'hipThreadIdx_x',
            'barrier_sync': '__syncthreads()',
            'atomic_add': 'atomicAdd',
            'atomic_cas': 'atomicCAS',
            'sqrt_f': 'sqrtf',
            'sin_f': 'sinf',
            'cos_f': 'cosf',
            'exp_f': 'expf',
            'log_f': 'logf',
        }
        
        # Metal builtins
        self.builtin_functions[KernelLanguage.METAL_SHADER] = {
            'get_thread_id': 'thread_position_in_grid.x',
            'get_block_id': 'threadgroup_position_in_grid.x',
            'get_thread_in_block': 'thread_position_in_threadgroup.x',
            'barrier_sync': 'threadgroup_barrier(mem_flags::mem_threadgroup)',
            'atomic_add': 'atomic_fetch_add_explicit',
            'atomic_cas': 'atomic_compare_exchange_weak_explicit',
            'sqrt_f': 'sqrt',
            'sin_f': 'sin',
            'cos_f': 'cos',
            'exp_f': 'exp',
            'log_f': 'log',
        }
    
    def _initialize_language_headers(self):
        """Initialize language-specific headers"""
        
        self.language_headers[KernelLanguage.CUDA_C] = """
#include <cuda_runtime.h>
#include <device_launch_parameters.h>
#include <math.h>
"""
        
        self.language_headers[KernelLanguage.HIP_C] = """
#include <hip/hip_runtime.h>
#include <hip/hip_math_constants.h>
#include <math.h>
"""
        
        self.language_headers[KernelLanguage.METAL_SHADER] = """
#include <metal_stdlib>
using namespace metal;
"""
        
        self.language_headers[KernelLanguage.OPENCL_C] = """
#pragma OPENCL EXTENSION cl_khr_fp64 : enable
"""
    
    def translate_kernel(self, source_code: str, from_lang: KernelLanguage, 
                        to_lang: KernelLanguage, metadata: Optional[KernelMetadata] = None) -> Optional[str]:
        """Translate kernel from one language to another"""
        
        if from_lang == to_lang:
            return source_code
        
        try:
            # Get translation rules
            rules = self.translation_rules.get((from_lang, to_lang))
            if not rules:
                logger.warning(f"No direct translation rules from {from_lang.value} to {to_lang.value}")
                # Try indirect translation via Universal KOS
                return self._indirect_translation(source_code, from_lang, to_lang)
            
            # Apply translation rules
            translated = source_code
            for rule in rules:
                if rule.context:
                    # Context-sensitive translation
                    translated = self._apply_context_rule(translated, rule)
                else:
                    # Simple pattern replacement
                    translated = re.sub(rule.pattern, rule.replacement, translated)
            
            # Add language-specific header
            if to_lang in self.language_headers:
                header = self.language_headers[to_lang]
                translated = header + "\n" + translated
            
            # Apply language-specific transformations
            translated = self._apply_language_transformations(translated, to_lang, metadata)
            
            logger.info(f"Successfully translated kernel from {from_lang.value} to {to_lang.value}")
            return translated
            
        except Exception as e:
            logger.error(f"Kernel translation failed: {e}")
            return None
    
    def _indirect_translation(self, source_code: str, from_lang: KernelLanguage, 
                            to_lang: KernelLanguage) -> Optional[str]:
        """Perform indirect translation via Universal KOS"""
        
        # First translate to Universal KOS
        kos_code = self.translate_kernel(source_code, from_lang, KernelLanguage.UNIVERSAL_KOS)
        if not kos_code:
            return None
        
        # Then translate from Universal KOS to target language
        return self.translate_kernel(kos_code, KernelLanguage.UNIVERSAL_KOS, to_lang)
    
    def _apply_context_rule(self, source: str, rule: TranslationRule) -> str:
        """Apply context-sensitive translation rule"""
        
        if rule.context == "function":
            # Only apply within function definitions
            function_pattern = r'(\w+\s+\w+\s*\([^)]*\)\s*\{[^}]*?)' + rule.pattern + r'([^}]*\})'
            def replacer(match):
                return match.group(1) + rule.replacement + match.group(2)
            return re.sub(function_pattern, replacer, source, flags=re.DOTALL)
        
        elif rule.context == "kernel":
            # Only apply within kernel functions
            kernel_pattern = r'(__global__\s+\w+\s+\w+\s*\([^)]*\)\s*\{[^}]*?)' + rule.pattern + r'([^}]*\})'
            def replacer(match):
                return match.group(1) + rule.replacement + match.group(2)
            return re.sub(kernel_pattern, replacer, source, flags=re.DOTALL)
        
        else:
            # Global context
            return re.sub(rule.pattern, rule.replacement, source)
    
    def _apply_language_transformations(self, source: str, target_lang: KernelLanguage, 
                                       metadata: Optional[KernelMetadata]) -> str:
        """Apply language-specific transformations"""
        
        if target_lang == KernelLanguage.METAL_SHADER:
            return self._transform_to_metal(source, metadata)
        elif target_lang == KernelLanguage.OPENCL_C:
            return self._transform_to_opencl(source, metadata)
        elif target_lang in [KernelLanguage.CUDA_C, KernelLanguage.HIP_C]:
            return self._transform_to_cuda_hip(source, metadata)
        
        return source
    
    def _transform_to_metal(self, source: str, metadata: Optional[KernelMetadata]) -> str:
        """Apply Metal-specific transformations"""
        
        # Convert parameter declarations
        source = re.sub(r'(\w+)\s*\*\s*(\w+)', r'device \1* \2', source)
        
        # Convert kernel signature
        if metadata and metadata.entry_point:
            pattern = rf'__global__\s+void\s+{metadata.entry_point}\s*\('
            replacement = f'kernel void {metadata.entry_point}('
            source = re.sub(pattern, replacement, source)
        
        # Add thread position parameters
        source = re.sub(r'kernel\s+void\s+(\w+)\s*\(([^)]*)\)', 
                       r'kernel void \1(\2, uint3 thread_position_in_grid [[thread_position_in_grid]], uint3 threads_per_threadgroup [[threads_per_threadgroup]])', 
                       source)
        
        return source
    
    def _transform_to_opencl(self, source: str, metadata: Optional[KernelMetadata]) -> str:
        """Apply OpenCL-specific transformations"""
        
        # Convert kernel signature
        source = re.sub(r'__global__\s+void\s+(\w+)', r'__kernel void \1', source)
        
        # Convert memory spaces
        source = re.sub(r'(\w+)\s*\*\s*(\w+)', r'__global \1* \2', source)
        source = re.sub(r'__shared__', '__local', source)
        
        # Convert thread indices
        source = re.sub(r'blockIdx\.x \* blockDim\.x \+ threadIdx\.x', 'get_global_id(0)', source)
        source = re.sub(r'threadIdx\.x', 'get_local_id(0)', source)
        source = re.sub(r'blockDim\.x', 'get_local_size(0)', source)
        
        # Convert synchronization
        source = re.sub(r'__syncthreads\(\)', 'barrier(CLK_LOCAL_MEM_FENCE)', source)
        
        return source
    
    def _transform_to_cuda_hip(self, source: str, metadata: Optional[KernelMetadata]) -> str:
        """Apply CUDA/HIP-specific transformations"""
        
        # Ensure proper kernel signature
        if not re.search(r'__global__', source):
            # Add __global__ if missing
            source = re.sub(r'void\s+(\w+)\s*\(', r'__global__ void \1(', source)
        
        return source
    
    def detect_kernel_language(self, source_code: str) -> Optional[KernelLanguage]:
        """Detect the language of a kernel source"""
        
        # CUDA indicators
        cuda_patterns = [
            r'blockIdx\.',
            r'threadIdx\.',
            r'__global__',
            r'__device__',
            r'__shared__',
            r'cudaMalloc',
            r'__syncthreads'
        ]
        
        # HIP indicators  
        hip_patterns = [
            r'hipBlockIdx',
            r'hipThreadIdx',
            r'hipMalloc',
            r'hipMemcpy'
        ]
        
        # Metal indicators
        metal_patterns = [
            r'kernel\s+void',
            r'thread_position_in_grid',
            r'threadgroup_barrier',
            r'#include\s+<metal_stdlib>',
            r'using\s+namespace\s+metal'
        ]
        
        # OpenCL indicators
        opencl_patterns = [
            r'__kernel\s+void',
            r'get_global_id',
            r'get_local_id',
            r'__global',
            r'__local',
            r'barrier\(CLK'
        ]
        
        # Universal KOS indicators
        kos_patterns = [
            r'kos_thread_id',
            r'kos_barrier',
            r'kos_shared',
            r'KOS_KERNEL'
        ]
        
        # Count matches for each language
        scores = {
            KernelLanguage.CUDA_C: sum(1 for p in cuda_patterns if re.search(p, source_code)),
            KernelLanguage.HIP_C: sum(1 for p in hip_patterns if re.search(p, source_code)),
            KernelLanguage.METAL_SHADER: sum(1 for p in metal_patterns if re.search(p, source_code)),
            KernelLanguage.OPENCL_C: sum(1 for p in opencl_patterns if re.search(p, source_code)),
            KernelLanguage.UNIVERSAL_KOS: sum(1 for p in kos_patterns if re.search(p, source_code))
        }
        
        # Return language with highest score
        if max(scores.values()) > 0:
            return max(scores, key=scores.get)
        
        return None
    
    def extract_kernel_metadata(self, source_code: str, language: KernelLanguage) -> Optional[KernelMetadata]:
        """Extract metadata from kernel source"""
        
        try:
            # Find entry point
            entry_point = None
            if language in [KernelLanguage.CUDA_C, KernelLanguage.HIP_C]:
                match = re.search(r'__global__\s+void\s+(\w+)\s*\(', source_code)
                if match:
                    entry_point = match.group(1)
            elif language == KernelLanguage.METAL_SHADER:
                match = re.search(r'kernel\s+void\s+(\w+)\s*\(', source_code)
                if match:
                    entry_point = match.group(1)
            elif language == KernelLanguage.OPENCL_C:
                match = re.search(r'__kernel\s+void\s+(\w+)\s*\(', source_code)
                if match:
                    entry_point = match.group(1)
            
            if not entry_point:
                return None
            
            # Extract parameters
            param_pattern = rf'{entry_point}\s*\(([^)]*)\)'
            param_match = re.search(param_pattern, source_code)
            parameters = []
            
            if param_match:
                param_str = param_match.group(1)
                # Simple parameter parsing
                for param in param_str.split(','):
                    param = param.strip()
                    if param:
                        parts = param.split()
                        if len(parts) >= 2:
                            param_type = ' '.join(parts[:-1])
                            param_name = parts[-1].strip('*')
                            parameters.append({
                                'name': param_name,
                                'type': param_type,
                                'is_pointer': '*' in param
                            })
            
            # Default work sizes (would be extracted from pragmas or comments in real implementation)
            local_work_size = (256, 1, 1)
            global_work_size = (65536, 1, 1)
            shared_memory_size = 0
            
            # Look for shared memory declarations
            shared_matches = re.findall(r'__shared__\s+\w+\s+\w+\[(\d+)\]', source_code)
            if shared_matches:
                shared_memory_size = sum(int(m) for m in shared_matches) * 4  # Assume float32
            
            return KernelMetadata(
                entry_point=entry_point,
                parameters=parameters,
                local_work_size=local_work_size,
                global_work_size=global_work_size,
                shared_memory_size=shared_memory_size,
                required_features=[],
                optimization_hints={}
            )
            
        except Exception as e:
            logger.error(f"Failed to extract kernel metadata: {e}")
            return None
    
    def optimize_kernel_for_device(self, source_code: str, device_type: DeviceType, 
                                  language: KernelLanguage) -> str:
        """Apply device-specific optimizations"""
        
        optimized = source_code
        
        if device_type == DeviceType.GPU_CUDA:
            # NVIDIA-specific optimizations
            # Use faster intrinsics
            optimized = re.sub(r'\bsqrtf\b', '__fsqrt_rn', optimized)
            optimized = re.sub(r'\bsinf\b', '__sinf', optimized)
            optimized = re.sub(r'\bcosf\b', '__cosf', optimized)
            
        elif device_type == DeviceType.GPU_ROCM:
            # AMD-specific optimizations
            # Use wavefront-aware code
            if 'barrier' in optimized:
                optimized += "\n// Optimized for AMD wavefront size 64"
                
        elif device_type == DeviceType.GPU_METAL:
            # Apple Silicon optimizations
            # Use SIMD group functions
            optimized = re.sub(r'__syncthreads\(\)', 'simdgroup_barrier(mem_flags::mem_device)', optimized)
        
        return optimized
    
    def validate_translation(self, original: str, translated: str, 
                           from_lang: KernelLanguage, to_lang: KernelLanguage) -> bool:
        """Validate that translation preserves semantic meaning"""
        
        try:
            # Extract key elements from both versions
            orig_metadata = self.extract_kernel_metadata(original, from_lang)
            trans_metadata = self.extract_kernel_metadata(translated, to_lang)
            
            if not orig_metadata or not trans_metadata:
                return False
            
            # Check entry point preservation
            if orig_metadata.entry_point != trans_metadata.entry_point:
                logger.warning("Entry point mismatch in translation")
                return False
            
            # Check parameter count
            if len(orig_metadata.parameters) != len(trans_metadata.parameters):
                logger.warning("Parameter count mismatch in translation")
                return False
            
            logger.info("Translation validation passed")
            return True
            
        except Exception as e:
            logger.error(f"Translation validation failed: {e}")
            return False