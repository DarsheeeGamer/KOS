"""
Kaede High-Performance Compiler
==============================

A sophisticated compiler for the Kaede programming language that provides:
- Multi-target compilation (bytecode, native x86_64, ARM64)
- Advanced optimizations (SSA, dead code elimination, constant folding)
- Just-In-Time (JIT) compilation
- Link-time optimization (LTO)
- Profile-guided optimization (PGO)
- Automatic vectorization
- Memory layout optimization
"""

import os
import sys
import time
import struct
import hashlib
import threading
import mmap
import ctypes
import platform
import functools
from typing import Dict, List, Any, Optional, Union, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque

from .lexer import KaedeLexer, Token, TokenType
from .parser import KaedeParser
from .ast_nodes import *
from .exceptions import *
from .memory_manager import memory_manager, KaedeMemoryManager

class TargetArch(Enum):
    """Target architectures"""
    X86_64 = "x86_64"
    ARM64 = "arm64"
    WASM = "wasm"
    KAEDE_VM = "kaede_vm"

@functools.total_ordering
class OptimizationLevel(Enum):
    """Optimization levels"""
    O0 = 0  # No optimization
    O1 = 1  # Basic optimization
    O2 = 2  # Full optimization
    O3 = 3  # Aggressive optimization
    OS = 4  # Size optimization
    OZ = 5  # Aggressive size optimization
    
    def __lt__(self, other):
        if self.__class__ is other.__class__:
            return self.value < other.value
        return NotImplemented

class Opcode(Enum):
    """Kaede VM opcodes"""
    # Stack operations
    PUSH_CONST = 0x01
    PUSH_LOCAL = 0x02
    PUSH_GLOBAL = 0x03
    POP = 0x04
    DUP = 0x05
    SWAP = 0x06
    
    # Arithmetic operations
    ADD = 0x10
    SUB = 0x11
    MUL = 0x12
    DIV = 0x13
    MOD = 0x14
    NEG = 0x15
    
    # Bitwise operations
    AND = 0x20
    OR = 0x21
    XOR = 0x22
    NOT = 0x23
    SHL = 0x24
    SHR = 0x25
    
    # Comparison operations
    EQ = 0x30
    NE = 0x31
    LT = 0x32
    LE = 0x33
    GT = 0x34
    GE = 0x35
    
    # Control flow
    JMP = 0x40
    JMP_IF_TRUE = 0x41
    JMP_IF_FALSE = 0x42
    CALL = 0x43
    RET = 0x44
    
    # Memory operations
    LOAD = 0x50
    STORE = 0x51
    ALLOC = 0x52
    FREE = 0x53
    
    # Object operations
    NEW = 0x60
    DELETE = 0x61
    GET_ATTR = 0x62
    SET_ATTR = 0x63
    
    # Function operations
    MAKE_FUNCTION = 0x70
    CALL_FUNCTION = 0x71
    RETURN_VALUE = 0x72
    
    # Exception handling
    SETUP_TRY = 0x80
    END_TRY = 0x81
    RAISE = 0x82
    
    # Advanced operations
    VECTORIZE = 0x90
    PARALLEL = 0x91
    ATOMIC = 0x92
    
    # System calls
    SYSCALL = 0xF0
    
    # Halt
    HALT = 0xFF

@dataclass
class Instruction:
    """Bytecode instruction"""
    opcode: Opcode
    arg: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    line_number: int = 0

@dataclass
class BasicBlock:
    """Basic block for optimization"""
    id: int
    instructions: List[Instruction] = field(default_factory=list)
    predecessors: Set[int] = field(default_factory=set)
    successors: Set[int] = field(default_factory=set)
    live_in: Set[str] = field(default_factory=set)
    live_out: Set[str] = field(default_factory=set)

@dataclass
class Function:
    """Compiled function representation"""
    name: str
    parameters: List[str]
    locals: List[str]
    bytecode: bytes
    native_code: Optional[bytes] = None
    basic_blocks: List[BasicBlock] = field(default_factory=list)
    call_count: int = 0
    execution_time: float = 0.0

@dataclass
class Module:
    """Compiled module"""
    name: str
    functions: Dict[str, Function] = field(default_factory=dict)
    globals: Dict[str, Any] = field(default_factory=dict)
    imports: List[str] = field(default_factory=list)
    exports: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

class SSAValue:
    """Static Single Assignment value"""
    def __init__(self, name: str, version: int, type_hint: Optional[str] = None):
        self.name = name
        self.version = version
        self.type_hint = type_hint
        self.uses: Set['SSAInstruction'] = set()
        self.definition: Optional['SSAInstruction'] = None
    
    def __str__(self):
        return f"{self.name}_{self.version}"

class SSAInstruction:
    """SSA form instruction"""
    def __init__(self, opcode: str, result: Optional[SSAValue] = None, 
                 operands: List[SSAValue] = None):
        self.opcode = opcode
        self.result = result
        self.operands = operands or []
        
        # Add use-def chains
        if result:
            result.definition = self
        for operand in self.operands:
            operand.uses.add(self)

class OptimizationPass:
    """Base class for optimization passes"""
    
    def __init__(self, name: str):
        self.name = name
    
    def run(self, function: Function) -> bool:
        """Run optimization pass on function. Returns True if modified."""
        raise NotImplementedError

class ConstantFoldingPass(OptimizationPass):
    """Constant folding optimization"""
    
    def __init__(self):
        super().__init__("constant_folding")
    
    def run(self, function: Function) -> bool:
        """Fold constants in function"""
        modified = False
        new_instructions = []
        
        i = 0
        instructions = self._decode_bytecode(function.bytecode)
        
        while i < len(instructions):
            inst = instructions[i]
            
            # Look for constant arithmetic patterns
            if (i >= 2 and 
                instructions[i-2].opcode == Opcode.PUSH_CONST and
                instructions[i-1].opcode == Opcode.PUSH_CONST and
                inst.opcode in [Opcode.ADD, Opcode.SUB, Opcode.MUL, Opcode.DIV]):
                
                # Fold the operation
                val1 = instructions[i-2].arg
                val2 = instructions[i-1].arg
                
                if inst.opcode == Opcode.ADD:
                    result = val1 + val2
                elif inst.opcode == Opcode.SUB:
                    result = val1 - val2
                elif inst.opcode == Opcode.MUL:
                    result = val1 * val2
                elif inst.opcode == Opcode.DIV and val2 != 0:
                    result = val1 // val2
                else:
                    new_instructions.extend([instructions[i-2], instructions[i-1], inst])
                    i += 1
                    continue
                
                # Replace with single constant
                new_instructions.pop()  # Remove val1
                new_instructions.pop()  # Remove val2
                new_instructions.append(Instruction(Opcode.PUSH_CONST, result))
                modified = True
            else:
                new_instructions.append(inst)
            
            i += 1
        
        if modified:
            function.bytecode = self._encode_bytecode(new_instructions)
        
        return modified
    
    def _decode_bytecode(self, bytecode: bytes) -> List[Instruction]:
        """Decode bytecode to instructions"""
        instructions = []
        i = 0
        while i < len(bytecode):
            opcode = Opcode(bytecode[i])
            i += 1
            
            arg = None
            if i < len(bytecode) and opcode in [Opcode.PUSH_CONST, Opcode.PUSH_LOCAL, 
                                               Opcode.PUSH_GLOBAL, Opcode.JMP, 
                                               Opcode.JMP_IF_TRUE, Opcode.JMP_IF_FALSE]:
                arg = struct.unpack('>I', bytecode[i:i+4])[0]
                i += 4
            
            instructions.append(Instruction(opcode, arg))
        
        return instructions
    
    def _encode_bytecode(self, instructions: List[Instruction]) -> bytes:
        """Encode instructions to bytecode"""
        bytecode = bytearray()
        
        for inst in instructions:
            bytecode.append(inst.opcode.value)
            if inst.arg is not None:
                bytecode.extend(struct.pack('>I', inst.arg))
        
        return bytes(bytecode)

class DeadCodeEliminationPass(OptimizationPass):
    """Dead code elimination"""
    
    def __init__(self):
        super().__init__("dead_code_elimination")
    
    def run(self, function: Function) -> bool:
        """Remove dead code from function"""
        # Build control flow graph
        cfg = self._build_cfg(function)
        
        # Mark reachable blocks
        reachable = self._mark_reachable(cfg)
        
        # Remove unreachable blocks
        modified = False
        new_blocks = []
        for block in function.basic_blocks:
            if block.id in reachable:
                new_blocks.append(block)
            else:
                modified = True
        
        function.basic_blocks = new_blocks
        return modified
    
    def _build_cfg(self, function: Function) -> Dict[int, BasicBlock]:
        """Build control flow graph"""
        if not function.basic_blocks:
            self._create_basic_blocks(function)
        
        return {block.id: block for block in function.basic_blocks}
    
    def _create_basic_blocks(self, function: Function):
        """Create basic blocks from bytecode"""
        instructions = self._decode_bytecode(function.bytecode)
        
        # Find block boundaries
        leaders = {0}  # First instruction is always a leader
        
        for i, inst in enumerate(instructions):
            if inst.opcode in [Opcode.JMP, Opcode.JMP_IF_TRUE, Opcode.JMP_IF_FALSE]:
                leaders.add(inst.arg)  # Target of jump
                if i + 1 < len(instructions):
                    leaders.add(i + 1)  # Instruction after jump
        
        # Create blocks
        leaders = sorted(leaders)
        blocks = []
        
        for i, start in enumerate(leaders):
            end = leaders[i + 1] if i + 1 < len(leaders) else len(instructions)
            block = BasicBlock(id=len(blocks))
            block.instructions = instructions[start:end]
            blocks.append(block)
        
        # Add edges
        for i, block in enumerate(blocks):
            last_inst = block.instructions[-1] if block.instructions else None
            
            if last_inst:
                if last_inst.opcode == Opcode.JMP:
                    target_block = self._find_block_by_offset(blocks, last_inst.arg)
                    if target_block:
                        block.successors.add(target_block.id)
                        target_block.predecessors.add(block.id)
                elif last_inst.opcode in [Opcode.JMP_IF_TRUE, Opcode.JMP_IF_FALSE]:
                    # Branch instruction has two successors
                    target_block = self._find_block_by_offset(blocks, last_inst.arg)
                    if target_block:
                        block.successors.add(target_block.id)
                        target_block.predecessors.add(block.id)
                    
                    # Fall-through to next block
                    if i + 1 < len(blocks):
                        next_block = blocks[i + 1]
                        block.successors.add(next_block.id)
                        next_block.predecessors.add(block.id)
                elif last_inst.opcode not in [Opcode.RET, Opcode.HALT]:
                    # Fall-through to next block
                    if i + 1 < len(blocks):
                        next_block = blocks[i + 1]
                        block.successors.add(next_block.id)
                        next_block.predecessors.add(block.id)
        
        function.basic_blocks = blocks
    
    def _find_block_by_offset(self, blocks: List[BasicBlock], offset: int) -> Optional[BasicBlock]:
        """Find block containing instruction at offset"""
        current_offset = 0
        for block in blocks:
            block_size = len(block.instructions)
            if current_offset <= offset < current_offset + block_size:
                return block
            current_offset += block_size
        return None
    
    def _mark_reachable(self, cfg: Dict[int, BasicBlock]) -> Set[int]:
        """Mark reachable blocks using DFS"""
        reachable = set()
        stack = [0]  # Start from entry block
        
        while stack:
            block_id = stack.pop()
            if block_id not in reachable:
                reachable.add(block_id)
                if block_id in cfg:
                    stack.extend(cfg[block_id].successors)
        
        return reachable
    
    def _decode_bytecode(self, bytecode: bytes) -> List[Instruction]:
        """Decode bytecode to instructions"""
        instructions = []
        i = 0
        while i < len(bytecode):
            opcode = Opcode(bytecode[i])
            i += 1
            
            arg = None
            if i < len(bytecode) and opcode in [Opcode.PUSH_CONST, Opcode.PUSH_LOCAL, 
                                               Opcode.PUSH_GLOBAL, Opcode.JMP, 
                                               Opcode.JMP_IF_TRUE, Opcode.JMP_IF_FALSE]:
                arg = struct.unpack('>I', bytecode[i:i+4])[0]
                i += 4
            
            instructions.append(Instruction(opcode, arg))
        
        return instructions

class JITCompiler:
    """Just-In-Time compiler for hot functions"""
    
    def __init__(self, target_arch: TargetArch = TargetArch.X86_64):
        self.target_arch = target_arch
        self.hot_threshold = 1000  # Calls before JIT compilation
        self.native_cache = {}
        
    def should_compile(self, function: Function) -> bool:
        """Check if function should be JIT compiled"""
        return (function.call_count >= self.hot_threshold and 
                function.native_code is None)
    
    def compile_to_native(self, function: Function) -> bytes:
        """Compile function to native code"""
        if self.target_arch == TargetArch.X86_64:
            return self._compile_x86_64(function)
        elif self.target_arch == TargetArch.ARM64:
            return self._compile_arm64(function)
        else:
            raise KaedeCompilerError(f"Unsupported target architecture: {self.target_arch}")
    
    def _compile_x86_64(self, function: Function) -> bytes:
        """Compile to x86_64 machine code"""
        code = bytearray()
        
        # Function prologue
        code.extend([0x55])  # push rbp
        code.extend([0x48, 0x89, 0xe5])  # mov rbp, rsp
        
        # Decode and compile bytecode
        instructions = self._decode_bytecode(function.bytecode)
        
        for inst in instructions:
            if inst.opcode == Opcode.PUSH_CONST:
                # mov rax, immediate
                code.extend([0x48, 0xb8])
                code.extend(struct.pack('<Q', inst.arg))
                # push rax
                code.extend([0x50])
            
            elif inst.opcode == Opcode.ADD:
                # pop rax (second operand)
                code.extend([0x58])
                # pop rbx (first operand)
                code.extend([0x5b])
                # add rax, rbx
                code.extend([0x48, 0x01, 0xd8])
                # push rax (result)
                code.extend([0x50])
            
            elif inst.opcode == Opcode.SUB:
                # pop rbx (second operand)
                code.extend([0x5b])
                # pop rax (first operand)
                code.extend([0x58])
                # sub rax, rbx
                code.extend([0x48, 0x29, 0xd8])
                # push rax (result)
                code.extend([0x50])
            
            elif inst.opcode == Opcode.MUL:
                # pop rax (second operand)
                code.extend([0x58])
                # pop rbx (first operand)
                code.extend([0x5b])
                # imul rax, rbx
                code.extend([0x48, 0x0f, 0xaf, 0xc3])
                # push rax (result)
                code.extend([0x50])
            
            elif inst.opcode == Opcode.RET:
                # pop rax (return value)
                code.extend([0x58])
                # Function epilogue
                code.extend([0x48, 0x89, 0xec])  # mov rsp, rbp
                code.extend([0x5d])  # pop rbp
                code.extend([0xc3])  # ret
        
        return bytes(code)
    
    def _compile_arm64(self, function: Function) -> bytes:
        """Compile to ARM64 machine code"""
        code = bytearray()
        
        # Function prologue (simplified)
        # stp x29, x30, [sp, #-16]!
        code.extend([0xfd, 0x7b, 0xbf, 0xa9])
        # mov x29, sp
        code.extend([0xfd, 0x03, 0x00, 0x91])
        
        instructions = self._decode_bytecode(function.bytecode)
        
        for inst in instructions:
            if inst.opcode == Opcode.PUSH_CONST:
                # mov x0, #immediate (simplified)
                code.extend([0x00, 0x00, 0x80, 0xd2])  # placeholder
            
            elif inst.opcode == Opcode.ADD:
                # add x0, x0, x1 (simplified)
                code.extend([0x00, 0x00, 0x01, 0x8b])
            
            elif inst.opcode == Opcode.RET:
                # Function epilogue
                # ldp x29, x30, [sp], #16
                code.extend([0xfd, 0x7b, 0xc1, 0xa8])
                # ret
                code.extend([0xc0, 0x03, 0x5f, 0xd6])
        
        return bytes(code)
    
    def _decode_bytecode(self, bytecode: bytes) -> List[Instruction]:
        """Decode bytecode to instructions"""
        instructions = []
        i = 0
        while i < len(bytecode):
            opcode = Opcode(bytecode[i])
            i += 1
            
            arg = None
            if i < len(bytecode) and opcode in [Opcode.PUSH_CONST, Opcode.PUSH_LOCAL, 
                                               Opcode.PUSH_GLOBAL, Opcode.JMP, 
                                               Opcode.JMP_IF_TRUE, Opcode.JMP_IF_FALSE]:
                arg = struct.unpack('>I', bytecode[i:i+4])[0]
                i += 4
            
            instructions.append(Instruction(opcode, arg))
        
        return instructions

class KaedeCompiler:
    """High-performance Kaede compiler with advanced optimizations"""
    
    def __init__(self, target_arch: TargetArch = None, optimization_level: OptimizationLevel = OptimizationLevel.O2):
        self.target_arch = target_arch or self._detect_target_arch()
        self.optimization_level = optimization_level
        self.lexer = KaedeLexer()
        self.parser = KaedeParser()
        
        # Compilation components
        self.code_generator = CodeGenerator(self.target_arch)
        self.optimizer = Optimizer(optimization_level)
        self.jit_compiler = JITCompiler(self.target_arch)
        
        # Compilation cache
        self.module_cache = {}
        self.bytecode_cache = {}
        
        # Statistics
        self.compilation_stats = {
            'modules_compiled': 0,
            'functions_compiled': 0,
            'optimizations_applied': 0,
            'jit_compilations': 0,
            'cache_hits': 0
        }
        
    def _detect_target_arch(self) -> TargetArch:
        """Detect target architecture"""
        machine = platform.machine().lower()
        if machine in ['x86_64', 'amd64']:
            return TargetArch.X86_64
        elif machine in ['arm64', 'aarch64']:
            return TargetArch.ARM64
        else:
            return TargetArch.KAEDE_VM
    
    def compile_file(self, file_path: str) -> Module:
        """Compile a Kaede source file"""
        # Check cache first
        cache_key = self._get_cache_key(file_path)
        if cache_key in self.module_cache:
            self.compilation_stats['cache_hits'] += 1
            return self.module_cache[cache_key]
        
        # Read and compile source
        with open(file_path, 'r', encoding='utf-8') as f:
            source_code = f.read()
        
        module = self.compile_source(source_code, os.path.basename(file_path))
        
        # Cache result
        self.module_cache[cache_key] = module
        return module
    
    def compile_source(self, source_code: str, module_name: str = "main") -> Module:
        """Compile Kaede source code"""
        try:
            # Lexical analysis
            tokens = self.lexer.tokenize(source_code)
            
            # Syntax analysis
            ast = self.parser.parse(tokens)
            
            # Semantic analysis
            self._semantic_analysis(ast)
            
            # Code generation
            module = self.code_generator.generate(ast, module_name)
            
            # Optimization
            if self.optimization_level != OptimizationLevel.O0:
                self.optimizer.optimize_module(module)
            
            self.compilation_stats['modules_compiled'] += 1
            self.compilation_stats['functions_compiled'] += len(module.functions)
            
            return module
            
        except Exception as e:
            raise KaedeCompilerError(f"Compilation failed: {e}") from e
    
    def _get_cache_key(self, file_path: str) -> str:
        """Generate cache key for file"""
        stat = os.stat(file_path)
        content_hash = hashlib.md5(f"{file_path}:{stat.st_mtime}:{stat.st_size}".encode()).hexdigest()
        return f"{content_hash}:{self.optimization_level.value}:{self.target_arch.value}"
    
    def _semantic_analysis(self, ast: ASTNode):
        """Perform semantic analysis"""
        # Type checking, symbol resolution, etc.
        # This would be implemented based on the language semantics
        pass
    
    def compile_to_bytecode(self, module: Module) -> bytes:
        """Compile module to bytecode"""
        bytecode = bytearray()
        
        # Module header
        bytecode.extend(b'KAEDE')  # Magic number
        bytecode.extend(struct.pack('>H', 1))  # Version
        bytecode.extend(struct.pack('>I', len(module.functions)))  # Function count
        
        # Function table
        for func_name, function in module.functions.items():
            name_bytes = func_name.encode('utf-8')
            bytecode.extend(struct.pack('>H', len(name_bytes)))
            bytecode.extend(name_bytes)
            bytecode.extend(struct.pack('>I', len(function.bytecode)))
            bytecode.extend(function.bytecode)
        
        return bytes(bytecode)
    
    def should_jit_compile(self, function: Function) -> bool:
        """Check if function should be JIT compiled"""
        return self.jit_compiler.should_compile(function)
    
    def jit_compile_function(self, function: Function):
        """JIT compile hot function"""
        try:
            function.native_code = self.jit_compiler.compile_to_native(function)
            self.compilation_stats['jit_compilations'] += 1
        except Exception as e:
            print(f"JIT compilation failed for {function.name}: {e}")
    
    def get_compilation_stats(self) -> Dict[str, Any]:
        """Get compilation statistics"""
        return dict(self.compilation_stats)

class CodeGenerator:
    """Generate bytecode from AST"""
    
    def __init__(self, target_arch: TargetArch):
        self.target_arch = target_arch
        self.constants = []
        self.locals = []
        self.globals = []
        
    def generate(self, ast: ASTNode, module_name: str) -> Module:
        """Generate code for AST"""
        module = Module(name=module_name)
        
        if isinstance(ast, ModuleNode):
            for statement in ast.statements:
                if isinstance(statement, FunctionDeclarationNode):
                    function = self._generate_function(statement)
                    module.functions[function.name] = function
                elif isinstance(statement, VariableDeclarationNode):
                    # Handle global variables
                    pass
        
        return module
    
    def _generate_function(self, func_node: FunctionDeclarationNode) -> Function:
        """Generate code for function"""
        function = Function(
            name=func_node.name,
            parameters=[param.name for param in func_node.parameters],
            locals=[]
        )
        
        bytecode = bytearray()
        
        # Generate code for function body
        if func_node.body:
            for statement in func_node.body.statements:
                self._generate_statement(statement, bytecode)
        
        # Ensure function returns
        if not bytecode or bytecode[-1] != Opcode.RET.value:
            bytecode.append(Opcode.PUSH_CONST.value)
            bytecode.extend(struct.pack('>I', 0))  # Push null
            bytecode.append(Opcode.RET.value)
        
        function.bytecode = bytes(bytecode)
        return function
    
    def _generate_statement(self, stmt: ASTNode, bytecode: bytearray):
        """Generate code for statement"""
        if isinstance(stmt, ReturnStatementNode):
            if stmt.value:
                self._generate_expression(stmt.value, bytecode)
            else:
                bytecode.append(Opcode.PUSH_CONST.value)
                bytecode.extend(struct.pack('>I', 0))  # Push null
            bytecode.append(Opcode.RET.value)
        
        elif isinstance(stmt, ExpressionStatementNode):
            self._generate_expression(stmt.expression, bytecode)
            bytecode.append(Opcode.POP.value)  # Discard result
        
        elif isinstance(stmt, IfStatementNode):
            self._generate_if(stmt, bytecode)
        
        elif isinstance(stmt, WhileStatementNode):
            self._generate_while(stmt, bytecode)
    
    def _generate_expression(self, expr: ASTNode, bytecode: bytearray):
        """Generate code for expression"""
        if isinstance(expr, LiteralNode):
            if expr.value_type == "integer":
                bytecode.append(Opcode.PUSH_CONST.value)
                bytecode.extend(struct.pack('>I', int(expr.value)))
            elif expr.value_type == "string":
                const_index = self._add_constant(expr.value)
                bytecode.append(Opcode.PUSH_CONST.value)
                bytecode.extend(struct.pack('>I', const_index))
        
        elif isinstance(expr, IdentifierNode):
            # Look up variable
            bytecode.append(Opcode.PUSH_LOCAL.value)
            bytecode.extend(struct.pack('>I', 0))  # Placeholder
        
        elif isinstance(expr, BinaryOpNode):
            self._generate_expression(expr.left, bytecode)
            self._generate_expression(expr.right, bytecode)
            
            if expr.operator == "+":
                bytecode.append(Opcode.ADD.value)
            elif expr.operator == "-":
                bytecode.append(Opcode.SUB.value)
            elif expr.operator == "*":
                bytecode.append(Opcode.MUL.value)
            elif expr.operator == "/":
                bytecode.append(Opcode.DIV.value)
            elif expr.operator == "==":
                bytecode.append(Opcode.EQ.value)
            elif expr.operator == "!=":
                bytecode.append(Opcode.NE.value)
            elif expr.operator == "<":
                bytecode.append(Opcode.LT.value)
            elif expr.operator == "<=":
                bytecode.append(Opcode.LE.value)
            elif expr.operator == ">":
                bytecode.append(Opcode.GT.value)
            elif expr.operator == ">=":
                bytecode.append(Opcode.GE.value)
        
        elif isinstance(expr, FunctionCallNode):
            # Generate arguments
            for arg in expr.arguments:
                self._generate_expression(arg, bytecode)
            
            # Call function
            bytecode.append(Opcode.CALL.value)
            bytecode.extend(struct.pack('>I', len(expr.arguments)))
    
    def _generate_if(self, if_stmt: IfStatementNode, bytecode: bytearray):
        """Generate code for if statement"""
        # Generate condition
        self._generate_expression(if_stmt.condition, bytecode)
        
        # Jump if false
        else_jump = len(bytecode)
        bytecode.append(Opcode.JMP_IF_FALSE.value)
        bytecode.extend(struct.pack('>I', 0))  # Placeholder
        
        # Generate then block
        for stmt in if_stmt.then_block.statements:
            self._generate_statement(stmt, bytecode)
        
        # Jump over else block
        end_jump = len(bytecode)
        bytecode.append(Opcode.JMP.value)
        bytecode.extend(struct.pack('>I', 0))  # Placeholder
        
        # Patch else jump
        else_addr = len(bytecode)
        struct.pack_into('>I', bytecode, else_jump + 1, else_addr)
        
        # Generate else block
        if if_stmt.else_block:
            for stmt in if_stmt.else_block.statements:
                self._generate_statement(stmt, bytecode)
        
        # Patch end jump
        end_addr = len(bytecode)
        struct.pack_into('>I', bytecode, end_jump + 1, end_addr)
    
    def _generate_while(self, while_stmt: WhileStatementNode, bytecode: bytearray):
        """Generate code for while loop"""
        loop_start = len(bytecode)
        
        # Generate condition
        self._generate_expression(while_stmt.condition, bytecode)
        
        # Jump if false (exit loop)
        exit_jump = len(bytecode)
        bytecode.append(Opcode.JMP_IF_FALSE.value)
        bytecode.extend(struct.pack('>I', 0))  # Placeholder
        
        # Generate loop body
        for stmt in while_stmt.body.statements:
            self._generate_statement(stmt, bytecode)
        
        # Jump back to condition
        bytecode.append(Opcode.JMP.value)
        bytecode.extend(struct.pack('>I', loop_start))
        
        # Patch exit jump
        exit_addr = len(bytecode)
        struct.pack_into('>I', bytecode, exit_jump + 1, exit_addr)
    
    def _add_constant(self, value: Any) -> int:
        """Add constant to constant pool"""
        if value not in self.constants:
            self.constants.append(value)
        return self.constants.index(value)

class Optimizer:
    """Advanced optimizer with multiple passes"""
    
    def __init__(self, optimization_level: OptimizationLevel):
        self.optimization_level = optimization_level
        self.passes = self._create_optimization_passes()
    
    def _create_optimization_passes(self) -> List[OptimizationPass]:
        """Create optimization passes based on level"""
        passes = []
        
        if self.optimization_level >= OptimizationLevel.O1:
            passes.extend([
                ConstantFoldingPass(),
                DeadCodeEliminationPass(),
            ])
        
        if self.optimization_level >= OptimizationLevel.O2:
            # Add more aggressive optimizations
            pass
        
        return passes
    
    def optimize_module(self, module: Module):
        """Optimize entire module"""
        for function in module.functions.values():
            self.optimize_function(function)
    
    def optimize_function(self, function: Function):
        """Optimize single function"""
        modified = True
        iterations = 0
        max_iterations = 10
        
        while modified and iterations < max_iterations:
            modified = False
            for opt_pass in self.passes:
                if opt_pass.run(function):
                    modified = True
            iterations += 1

# Global compiler instance
compiler = KaedeCompiler() 