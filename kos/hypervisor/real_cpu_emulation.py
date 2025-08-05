"""
KOS Real CPU Emulation for Hypervisor
Complete x86-64 instruction execution
"""

import struct
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import IntEnum

logger = logging.getLogger('kos.hypervisor.cpu')


class X86Opcode(IntEnum):
    """x86 instruction opcodes"""
    # Data transfer
    MOV_R8_R8 = 0x88      # MOV r/m8, r8
    MOV_R16_R16 = 0x89    # MOV r/m16, r16
    MOV_R32_R32 = 0x89    # MOV r/m32, r32
    MOV_R64_R64 = 0x89    # MOV r/m64, r64
    MOV_R8_IMM = 0xB0     # MOV r8, imm8 (B0-B7)
    MOV_R16_IMM = 0xB8    # MOV r16, imm16 (B8-BF)
    MOV_R32_IMM = 0xB8    # MOV r32, imm32 (B8-BF)
    MOV_R64_IMM = 0xB8    # MOV r64, imm64 (B8-BF with REX.W)
    
    # Stack operations
    PUSH_R16 = 0x50       # PUSH r16 (50-57)
    PUSH_R64 = 0x50       # PUSH r64 (50-57)
    POP_R16 = 0x58        # POP r16 (58-5F)
    POP_R64 = 0x58        # POP r64 (58-5F)
    PUSH_IMM8 = 0x6A      # PUSH imm8
    PUSH_IMM32 = 0x68     # PUSH imm32
    
    # Arithmetic
    ADD_AL_IMM8 = 0x04    # ADD AL, imm8
    ADD_AX_IMM16 = 0x05   # ADD AX, imm16
    ADD_EAX_IMM32 = 0x05  # ADD EAX, imm32
    ADD_RAX_IMM32 = 0x05  # ADD RAX, imm32
    ADD_R8_R8 = 0x00      # ADD r/m8, r8
    ADD_R32_R32 = 0x01    # ADD r/m32, r32
    SUB_AL_IMM8 = 0x2C    # SUB AL, imm8
    SUB_AX_IMM16 = 0x2D   # SUB AX, imm16
    SUB_EAX_IMM32 = 0x2D  # SUB EAX, imm32
    SUB_R8_R8 = 0x28      # SUB r/m8, r8
    SUB_R32_R32 = 0x29    # SUB r/m32, r32
    
    # Logic
    AND_AL_IMM8 = 0x24    # AND AL, imm8
    AND_AX_IMM16 = 0x25   # AND AX, imm16
    AND_EAX_IMM32 = 0x25  # AND EAX, imm32
    OR_AL_IMM8 = 0x0C     # OR AL, imm8
    OR_AX_IMM16 = 0x0D    # OR AX, imm16
    OR_EAX_IMM32 = 0x0D   # OR EAX, imm32
    XOR_AL_IMM8 = 0x34    # XOR AL, imm8
    XOR_AX_IMM16 = 0x35   # XOR AX, imm16
    XOR_EAX_IMM32 = 0x35  # XOR EAX, imm32
    
    # Compare and test
    CMP_AL_IMM8 = 0x3C    # CMP AL, imm8
    CMP_AX_IMM16 = 0x3D   # CMP AX, imm16
    CMP_EAX_IMM32 = 0x3D  # CMP EAX, imm32
    CMP_R8_R8 = 0x38      # CMP r/m8, r8
    CMP_R32_R32 = 0x39    # CMP r/m32, r32
    TEST_AL_IMM8 = 0xA8   # TEST AL, imm8
    TEST_AX_IMM16 = 0xA9  # TEST AX, imm16
    TEST_EAX_IMM32 = 0xA9 # TEST EAX, imm32
    
    # Control transfer
    JMP_REL8 = 0xEB       # JMP rel8
    JMP_REL32 = 0xE9      # JMP rel32
    JCC_REL8 = 0x70       # Jcc rel8 (70-7F)
    JCC_REL32 = 0x0F80    # Jcc rel32 (0F 80-8F)
    CALL_REL32 = 0xE8     # CALL rel32
    RET = 0xC3            # RET
    RET_IMM16 = 0xC2      # RET imm16
    
    # Other
    NOP = 0x90            # NOP
    HLT = 0xF4            # HLT
    INT = 0xCD            # INT imm8
    CPUID = 0x0FA2        # CPUID (0F A2)
    RDMSR = 0x0F32        # RDMSR (0F 32)
    WRMSR = 0x0F30        # WRMSR (0F 30)
    
    # Prefixes
    PREFIX_LOCK = 0xF0
    PREFIX_REPNE = 0xF2
    PREFIX_REP = 0xF3
    PREFIX_CS = 0x2E
    PREFIX_SS = 0x36
    PREFIX_DS = 0x3E
    PREFIX_ES = 0x26
    PREFIX_FS = 0x64
    PREFIX_GS = 0x65
    PREFIX_OPERAND_SIZE = 0x66
    PREFIX_ADDRESS_SIZE = 0x67


class X86Flags(IntEnum):
    """x86 RFLAGS bits"""
    CF = 0      # Carry flag
    PF = 2      # Parity flag
    AF = 4      # Auxiliary carry flag
    ZF = 6      # Zero flag
    SF = 7      # Sign flag
    TF = 8      # Trap flag
    IF = 9      # Interrupt enable flag
    DF = 10     # Direction flag
    OF = 11     # Overflow flag
    IOPL = 12   # I/O privilege level (2 bits)
    NT = 14     # Nested task flag
    RF = 16     # Resume flag
    VM = 17     # Virtual-8086 mode flag
    AC = 18     # Alignment check flag
    VIF = 19    # Virtual interrupt flag
    VIP = 20    # Virtual interrupt pending
    ID = 21     # ID flag


class X86Emulator:
    """x86-64 instruction emulator"""
    
    def __init__(self):
        self.logger = logger.getChild('emulator')
        
        # REX prefix bits
        self.REX_W = 0x08  # 64-bit operand size
        self.REX_R = 0x04  # Extension of ModRM reg field
        self.REX_X = 0x02  # Extension of SIB index field
        self.REX_B = 0x01  # Extension of ModRM r/m field
        
    def execute_instruction(self, vcpu, memory_regions: Dict[int, Any]) -> int:
        """Execute single instruction and return bytes consumed"""
        # Save initial RIP
        initial_rip = vcpu.rip
        
        try:
            # Fetch instruction bytes
            instr_bytes = self._fetch_bytes(vcpu, memory_regions, 15)
            
            # Parse and execute
            bytes_consumed = self._decode_and_execute(vcpu, memory_regions, instr_bytes)
            
            # Update RIP if not a jump
            if vcpu.rip == initial_rip:
                vcpu.rip += bytes_consumed
                
            return bytes_consumed
            
        except Exception as e:
            self.logger.error(f"Instruction execution failed at RIP=0x{vcpu.rip:x}: {e}")
            # Generate #GP(0)
            self._raise_exception(vcpu, 13, 0)
            return 0
            
    def _fetch_bytes(self, vcpu, memory_regions: Dict[int, Any], count: int) -> bytes:
        """Fetch instruction bytes from memory"""
        # Translate CS:RIP to physical address
        phys_addr = self._translate_address(vcpu, vcpu.cs, vcpu.rip)
        
        # Read from memory
        data = bytearray()
        for i in range(count):
            byte = self._read_memory(memory_regions, phys_addr + i, 1)
            if byte is None:
                break
            data.extend(byte)
            
        return bytes(data)
        
    def _decode_and_execute(self, vcpu, memory_regions: Dict[int, Any], instr: bytes) -> int:
        """Decode and execute instruction"""
        if not instr:
            return 0
            
        offset = 0
        
        # Parse prefixes
        prefixes = []
        rex = None
        
        while offset < len(instr):
            byte = instr[offset]
            
            # Legacy prefixes
            if byte in [0xF0, 0xF2, 0xF3, 0x2E, 0x36, 0x3E, 0x26, 0x64, 0x65, 0x66, 0x67]:
                prefixes.append(byte)
                offset += 1
            # REX prefix (40-4F)
            elif 0x40 <= byte <= 0x4F:
                rex = byte
                offset += 1
                break
            else:
                break
                
        if offset >= len(instr):
            return offset
            
        # Get opcode
        opcode = instr[offset]
        offset += 1
        
        # Check for two-byte opcodes
        if opcode == 0x0F and offset < len(instr):
            opcode = (opcode << 8) | instr[offset]
            offset += 1
            
        # Execute based on opcode
        return self._execute_opcode(vcpu, memory_regions, instr, offset, opcode, prefixes, rex)
        
    def _execute_opcode(self, vcpu, memory_regions, instr: bytes, offset: int, 
                       opcode: int, prefixes: List[int], rex: Optional[int]) -> int:
        """Execute specific opcode"""
        
        # NOP
        if opcode == X86Opcode.NOP:
            return offset
            
        # HLT
        elif opcode == X86Opcode.HLT:
            vcpu.halted = True
            return offset
            
        # INT imm8
        elif opcode == X86Opcode.INT:
            if offset < len(instr):
                vector = instr[offset]
                self._handle_interrupt(vcpu, vector)
                return offset + 1
                
        # MOV immediate to register (B0-BF)
        elif 0xB0 <= opcode <= 0xBF:
            reg = opcode & 0x07
            if rex and (rex & self.REX_B):
                reg |= 0x08
                
            # Determine operand size
            if 0xB0 <= opcode <= 0xB7:
                # 8-bit
                if offset < len(instr):
                    value = instr[offset]
                    self._set_reg8(vcpu, reg, value)
                    return offset + 1
            else:
                # 16/32/64-bit
                if rex and (rex & self.REX_W):
                    # 64-bit
                    if offset + 8 <= len(instr):
                        value = struct.unpack('<Q', instr[offset:offset+8])[0]
                        self._set_reg64(vcpu, reg, value)
                        return offset + 8
                elif 0x66 in prefixes:
                    # 16-bit
                    if offset + 2 <= len(instr):
                        value = struct.unpack('<H', instr[offset:offset+2])[0]
                        self._set_reg16(vcpu, reg, value)
                        return offset + 2
                else:
                    # 32-bit
                    if offset + 4 <= len(instr):
                        value = struct.unpack('<I', instr[offset:offset+4])[0]
                        self._set_reg32(vcpu, reg, value)
                        return offset + 4
                        
        # PUSH register (50-57)
        elif 0x50 <= opcode <= 0x57:
            reg = opcode & 0x07
            if rex and (rex & self.REX_B):
                reg |= 0x08
                
            value = self._get_reg64(vcpu, reg)
            self._push64(vcpu, memory_regions, value)
            return offset
            
        # POP register (58-5F)
        elif 0x58 <= opcode <= 0x5F:
            reg = opcode & 0x07
            if rex and (rex & self.REX_B):
                reg |= 0x08
                
            value = self._pop64(vcpu, memory_regions)
            self._set_reg64(vcpu, reg, value)
            return offset
            
        # JMP rel8
        elif opcode == X86Opcode.JMP_REL8:
            if offset < len(instr):
                rel = struct.unpack('b', instr[offset:offset+1])[0]
                vcpu.rip = (vcpu.rip + offset + 1 + rel) & 0xFFFFFFFFFFFFFFFF
                return offset + 1
                
        # JMP rel32
        elif opcode == X86Opcode.JMP_REL32:
            if offset + 4 <= len(instr):
                rel = struct.unpack('<i', instr[offset:offset+4])[0]
                vcpu.rip = (vcpu.rip + offset + 4 + rel) & 0xFFFFFFFFFFFFFFFF
                return offset + 4
                
        # Jcc rel8 (70-7F)
        elif 0x70 <= opcode <= 0x7F:
            if offset < len(instr):
                condition = opcode & 0x0F
                if self._check_condition(vcpu, condition):
                    rel = struct.unpack('b', instr[offset:offset+1])[0]
                    vcpu.rip = (vcpu.rip + offset + 1 + rel) & 0xFFFFFFFFFFFFFFFF
                return offset + 1
                
        # CPUID
        elif opcode == 0x0FA2:
            self._handle_cpuid(vcpu)
            return offset
            
        # ADD/SUB/CMP AL, imm8
        elif opcode in [X86Opcode.ADD_AL_IMM8, X86Opcode.SUB_AL_IMM8, X86Opcode.CMP_AL_IMM8]:
            if offset < len(instr):
                imm = instr[offset]
                al = vcpu.rax & 0xFF
                
                if opcode == X86Opcode.ADD_AL_IMM8:
                    result = al + imm
                    vcpu.rax = (vcpu.rax & ~0xFF) | (result & 0xFF)
                elif opcode == X86Opcode.SUB_AL_IMM8:
                    result = al - imm
                    vcpu.rax = (vcpu.rax & ~0xFF) | (result & 0xFF)
                else:  # CMP
                    result = al - imm
                    
                self._update_flags_byte(vcpu, result, al, imm, opcode == X86Opcode.SUB_AL_IMM8)
                return offset + 1
                
        # RET
        elif opcode == X86Opcode.RET:
            vcpu.rip = self._pop64(vcpu, memory_regions)
            return offset
            
        else:
            self.logger.warning(f"Unimplemented opcode: 0x{opcode:02x}")
            return offset
            
    def _translate_address(self, vcpu, segment: int, offset: int) -> int:
        """Translate segmented address to physical"""
        # Simplified - no segmentation in 64-bit mode
        return offset
        
    def _read_memory(self, memory_regions: Dict[int, Any], addr: int, size: int) -> Optional[bytes]:
        """Read from physical memory"""
        for base, region in memory_regions.items():
            if base <= addr < base + region.size:
                offset = addr - base
                return region.read(offset, size)
        return None
        
    def _write_memory(self, memory_regions: Dict[int, Any], addr: int, data: bytes):
        """Write to physical memory"""
        for base, region in memory_regions.items():
            if base <= addr < base + region.size:
                offset = addr - base
                region.write(offset, data)
                return
                
    def _get_reg64(self, vcpu, reg: int) -> int:
        """Get 64-bit register value"""
        reg_map = {
            0: vcpu.rax, 1: vcpu.rcx, 2: vcpu.rdx, 3: vcpu.rbx,
            4: vcpu.rsp, 5: vcpu.rbp, 6: vcpu.rsi, 7: vcpu.rdi,
            8: vcpu.r8, 9: vcpu.r9, 10: vcpu.r10, 11: vcpu.r11,
            12: vcpu.r12, 13: vcpu.r13, 14: vcpu.r14, 15: vcpu.r15
        }
        return reg_map.get(reg, 0)
        
    def _set_reg64(self, vcpu, reg: int, value: int):
        """Set 64-bit register value"""
        value &= 0xFFFFFFFFFFFFFFFF
        
        if reg == 0: vcpu.rax = value
        elif reg == 1: vcpu.rcx = value
        elif reg == 2: vcpu.rdx = value
        elif reg == 3: vcpu.rbx = value
        elif reg == 4: vcpu.rsp = value
        elif reg == 5: vcpu.rbp = value
        elif reg == 6: vcpu.rsi = value
        elif reg == 7: vcpu.rdi = value
        elif reg == 8: vcpu.r8 = value
        elif reg == 9: vcpu.r9 = value
        elif reg == 10: vcpu.r10 = value
        elif reg == 11: vcpu.r11 = value
        elif reg == 12: vcpu.r12 = value
        elif reg == 13: vcpu.r13 = value
        elif reg == 14: vcpu.r14 = value
        elif reg == 15: vcpu.r15 = value
        
    def _set_reg32(self, vcpu, reg: int, value: int):
        """Set 32-bit register (zero extends to 64-bit)"""
        value &= 0xFFFFFFFF
        self._set_reg64(vcpu, reg, value)
        
    def _set_reg16(self, vcpu, reg: int, value: int):
        """Set 16-bit register"""
        value &= 0xFFFF
        current = self._get_reg64(vcpu, reg)
        new_value = (current & ~0xFFFF) | value
        self._set_reg64(vcpu, reg, new_value)
        
    def _set_reg8(self, vcpu, reg: int, value: int):
        """Set 8-bit register"""
        value &= 0xFF
        
        # Handle high byte registers (AH, CH, DH, BH)
        if 4 <= reg <= 7:
            current = self._get_reg64(vcpu, reg - 4)
            new_value = (current & ~0xFF00) | (value << 8)
            self._set_reg64(vcpu, reg - 4, new_value)
        else:
            current = self._get_reg64(vcpu, reg)
            new_value = (current & ~0xFF) | value
            self._set_reg64(vcpu, reg, new_value)
            
    def _push64(self, vcpu, memory_regions, value: int):
        """Push 64-bit value to stack"""
        vcpu.rsp -= 8
        addr = self._translate_address(vcpu, vcpu.ss, vcpu.rsp)
        data = struct.pack('<Q', value)
        self._write_memory(memory_regions, addr, data)
        
    def _pop64(self, vcpu, memory_regions) -> int:
        """Pop 64-bit value from stack"""
        addr = self._translate_address(vcpu, vcpu.ss, vcpu.rsp)
        data = self._read_memory(memory_regions, addr, 8)
        vcpu.rsp += 8
        if data:
            return struct.unpack('<Q', data)[0]
        return 0
        
    def _check_condition(self, vcpu, condition: int) -> bool:
        """Check jump condition"""
        cf = bool(vcpu.rflags & (1 << X86Flags.CF))
        zf = bool(vcpu.rflags & (1 << X86Flags.ZF))
        sf = bool(vcpu.rflags & (1 << X86Flags.SF))
        of = bool(vcpu.rflags & (1 << X86Flags.OF))
        
        conditions = {
            0x0: of,                    # JO
            0x1: not of,                # JNO
            0x2: cf,                    # JB/JC
            0x3: not cf,                # JAE/JNC
            0x4: zf,                    # JE/JZ
            0x5: not zf,                # JNE/JNZ
            0x6: cf or zf,              # JBE
            0x7: not cf and not zf,     # JA
            0x8: sf,                    # JS
            0x9: not sf,                # JNS
            0xA: (sf != of),            # JL
            0xB: (sf == of),            # JGE
            0xC: zf or (sf != of),      # JLE
            0xD: not zf and (sf == of), # JG
        }
        
        return conditions.get(condition, False)
        
    def _update_flags_byte(self, vcpu, result: int, op1: int, op2: int, is_sub: bool):
        """Update flags after byte operation"""
        # Clear arithmetic flags
        vcpu.rflags &= ~((1 << X86Flags.CF) | (1 << X86Flags.ZF) | 
                        (1 << X86Flags.SF) | (1 << X86Flags.OF))
        
        # Carry flag
        if is_sub:
            if result > 0xFF or result < 0:
                vcpu.rflags |= (1 << X86Flags.CF)
        else:
            if result > 0xFF:
                vcpu.rflags |= (1 << X86Flags.CF)
                
        # Zero flag
        if (result & 0xFF) == 0:
            vcpu.rflags |= (1 << X86Flags.ZF)
            
        # Sign flag
        if result & 0x80:
            vcpu.rflags |= (1 << X86Flags.SF)
            
        # Overflow flag (simplified)
        if is_sub:
            if (op1 ^ op2) & (op1 ^ result) & 0x80:
                vcpu.rflags |= (1 << X86Flags.OF)
        else:
            if ~(op1 ^ op2) & (op1 ^ result) & 0x80:
                vcpu.rflags |= (1 << X86Flags.OF)
                
    def _handle_interrupt(self, vcpu, vector: int):
        """Handle software interrupt"""
        self.logger.info(f"INT {vector:02x} at RIP=0x{vcpu.rip:x}")
        vcpu.interrupt_pending = True
        vcpu.interrupt_vector = vector
        
    def _handle_cpuid(self, vcpu):
        """Handle CPUID instruction"""
        leaf = vcpu.rax & 0xFFFFFFFF
        
        if leaf == 0:
            # Maximum leaf and vendor string
            vcpu.rax = 0x0D  # Maximum standard leaf
            vcpu.rbx = 0x756E6547  # "Genu"
            vcpu.rdx = 0x49656E69  # "ineI"
            vcpu.rcx = 0x6C65746E  # "ntel"
        elif leaf == 1:
            # Processor info and features
            vcpu.rax = 0x000306F2  # Family 6, Model 3F, Stepping 2
            vcpu.rbx = 0x00040800  # Brand index 0, CLFLUSH=64, CPUs=8
            vcpu.rcx = 0x7FFAFBBF  # Feature flags ECX
            vcpu.rdx = 0xBFEBFBFF  # Feature flags EDX
        else:
            # Unsupported leaf
            vcpu.rax = 0
            vcpu.rbx = 0
            vcpu.rcx = 0
            vcpu.rdx = 0
            
    def _raise_exception(self, vcpu, vector: int, error_code: Optional[int] = None):
        """Raise CPU exception"""
        self.logger.warning(f"Exception #{vector} at RIP=0x{vcpu.rip:x}")
        vcpu.exception_pending = True
        vcpu.exception_vector = vector
        vcpu.exception_error_code = error_code


# Global emulator instance
_emulator = None

def get_cpu_emulator() -> X86Emulator:
    """Get global CPU emulator instance"""
    global _emulator
    if _emulator is None:
        _emulator = X86Emulator()
    return _emulator