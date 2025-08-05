"""
KOS Hypervisor Implementation
Lightweight virtualization support for running VMs
"""

import os
import json
import time
import uuid
import threading
import logging
import struct
import mmap
from typing import Dict, Any, Optional, List, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum, auto
import multiprocessing as mp

logger = logging.getLogger('kos.hypervisor')


class VMState(Enum):
    """Virtual machine states"""
    CREATED = auto()
    RUNNING = auto()
    PAUSED = auto()
    SUSPENDED = auto()
    STOPPED = auto()
    CRASHED = auto()


class CPUArchitecture(Enum):
    """CPU architectures"""
    X86 = "x86"
    X86_64 = "x86_64"
    ARM = "arm"
    ARM64 = "arm64"


@dataclass
class VMConfig:
    """Virtual machine configuration"""
    name: str
    memory_mb: int
    vcpus: int
    arch: CPUArchitecture = CPUArchitecture.X86_64
    boot_device: str = "hd"  # hd, cdrom, network
    disk_images: List[str] = field(default_factory=list)
    cdrom_image: Optional[str] = None
    network_interfaces: List[Dict[str, Any]] = field(default_factory=list)
    display: Dict[str, Any] = field(default_factory=dict)
    usb_devices: List[Dict[str, Any]] = field(default_factory=list)
    pci_devices: List[Dict[str, Any]] = field(default_factory=list)
    bios: str = "seabios"  # seabios, uefi
    machine_type: str = "pc"  # pc, q35, virt
    cpu_model: str = "host"  # host, qemu64, etc
    enable_kvm: bool = True
    enable_nested: bool = False
    
    
@dataclass 
class VCPUState:
    """Virtual CPU state"""
    vcpu_id: int
    thread_id: Optional[int] = None
    
    # x86_64 registers
    rax: int = 0
    rbx: int = 0
    rcx: int = 0
    rdx: int = 0
    rsi: int = 0
    rdi: int = 0
    rbp: int = 0
    rsp: int = 0
    r8: int = 0
    r9: int = 0
    r10: int = 0
    r11: int = 0
    r12: int = 0
    r13: int = 0
    r14: int = 0
    r15: int = 0
    rip: int = 0
    rflags: int = 0
    
    # Segment registers
    cs: int = 0
    ds: int = 0
    es: int = 0
    fs: int = 0
    gs: int = 0
    ss: int = 0
    
    # Control registers
    cr0: int = 0
    cr2: int = 0
    cr3: int = 0
    cr4: int = 0
    
    # Debug registers
    dr0: int = 0
    dr1: int = 0
    dr2: int = 0
    dr3: int = 0
    dr6: int = 0
    dr7: int = 0
    
    # MSRs (Model Specific Registers)
    msrs: Dict[int, int] = field(default_factory=dict)
    
    # Interrupt state
    interrupt_pending: bool = False
    interrupt_vector: int = 0
    
    # Performance counters
    instructions_executed: int = 0
    cycles: int = 0


class MemoryRegion:
    """VM memory region"""
    
    def __init__(self, start: int, size: int, flags: int = 0):
        self.start = start
        self.size = size
        self.flags = flags
        self.data = bytearray(size)
        self.dirty_bitmap = bytearray((size + 4095) // 4096)  # Page granularity
        
    def read(self, offset: int, length: int) -> bytes:
        """Read from memory region"""
        if offset + length > self.size:
            raise ValueError("Read out of bounds")
        return bytes(self.data[offset:offset+length])
        
    def write(self, offset: int, data: bytes):
        """Write to memory region"""
        if offset + len(data) > self.size:
            raise ValueError("Write out of bounds")
        self.data[offset:offset+len(data)] = data
        
        # Mark pages as dirty
        start_page = offset // 4096
        end_page = (offset + len(data) + 4095) // 4096
        for page in range(start_page, end_page):
            self.dirty_bitmap[page] = 1
            
    def clear_dirty(self):
        """Clear dirty bitmap"""
        self.dirty_bitmap = bytearray((self.size + 4095) // 4096)


class VirtualMachine:
    """Virtual machine instance"""
    
    def __init__(self, vm_id: str, config: VMConfig):
        self.id = vm_id
        self.config = config
        self.state = VMState.CREATED
        self.created_at = time.time()
        self.started_at = 0
        
        # VM resources
        self.memory_regions: Dict[int, MemoryRegion] = {}
        self.vcpus: List[VCPUState] = []
        self.io_ports: Dict[int, Callable] = {}
        self.mmio_regions: Dict[Tuple[int, int], Callable] = {}
        self.interrupt_controller = None
        
        # VM process
        self.vm_process = None
        self.vcpu_threads = []
        
        # Shared memory for communication
        self.shared_memory = None
        self.control_pipe = None
        
        # Statistics
        self.stats = {
            'cpu_usage': 0,
            'memory_usage': 0,
            'disk_read_bytes': 0,
            'disk_write_bytes': 0,
            'network_rx_bytes': 0,
            'network_tx_bytes': 0
        }
        
        self._lock = threading.RLock()
        self._setup_vm()
        
    def _setup_vm(self):
        """Setup VM resources"""
        # Setup memory
        self._setup_memory()
        
        # Setup VCPUs
        for i in range(self.config.vcpus):
            vcpu = VCPUState(vcpu_id=i)
            self.vcpus.append(vcpu)
            
        # Setup devices
        self._setup_devices()
        
    def _setup_memory(self):
        """Setup VM memory layout"""
        # Main RAM
        ram_size = self.config.memory_mb * 1024 * 1024
        self.memory_regions[0] = MemoryRegion(0, ram_size)
        
        # ROM/BIOS region (last 1MB of 4GB address space)
        bios_start = 0xFFF00000
        bios_size = 0x100000  # 1MB
        self.memory_regions[bios_start] = MemoryRegion(bios_start, bios_size)
        
        # VGA memory
        vga_start = 0xA0000
        vga_size = 0x20000  # 128KB
        self.memory_regions[vga_start] = MemoryRegion(vga_start, vga_size)
        
    def _setup_devices(self):
        """Setup VM devices"""
        # Setup I/O ports
        self._setup_io_ports()
        
        # Setup MMIO regions
        self._setup_mmio()
        
        # Setup interrupt controller
        self._setup_interrupt_controller()
        
    def _setup_io_ports(self):
        """Setup I/O port handlers"""
        # Serial port (COM1)
        self.io_ports[0x3F8] = self._handle_serial_io
        
        # VGA ports
        self.io_ports[0x3C0] = self._handle_vga_io
        self.io_ports[0x3C4] = self._handle_vga_io
        self.io_ports[0x3C5] = self._handle_vga_io
        
        # Keyboard controller
        self.io_ports[0x60] = self._handle_keyboard_io
        self.io_ports[0x64] = self._handle_keyboard_io
        
        # PIC (Programmable Interrupt Controller)
        self.io_ports[0x20] = self._handle_pic_io
        self.io_ports[0x21] = self._handle_pic_io
        self.io_ports[0xA0] = self._handle_pic_io
        self.io_ports[0xA1] = self._handle_pic_io
        
    def _setup_mmio(self):
        """Setup MMIO regions"""
        # APIC MMIO
        apic_base = 0xFEE00000
        apic_size = 0x1000
        self.mmio_regions[(apic_base, apic_base + apic_size)] = self._handle_apic_mmio
        
        # HPET MMIO
        hpet_base = 0xFED00000
        hpet_size = 0x1000
        self.mmio_regions[(hpet_base, hpet_base + hpet_size)] = self._handle_hpet_mmio
        
    def _setup_interrupt_controller(self):
        """Setup interrupt controller (PIC/APIC)"""
        self.interrupt_controller = InterruptController()
        
    def start(self) -> bool:
        """Start virtual machine"""
        with self._lock:
            if self.state == VMState.RUNNING:
                return True
                
            try:
                # Create shared memory for VM
                shm_size = 16 * 1024 * 1024  # 16MB control region
                self.shared_memory = mmap.mmap(-1, shm_size)
                
                # Create control pipes
                parent_conn, child_conn = mp.Pipe()
                self.control_pipe = parent_conn
                
                # Start VM process
                self.vm_process = mp.Process(
                    target=self._vm_main_loop,
                    args=(child_conn,),
                    name=f"kos-vm-{self.config.name}"
                )
                self.vm_process.start()
                
                # Start VCPU threads
                for vcpu in self.vcpus:
                    thread = threading.Thread(
                        target=self._vcpu_loop,
                        args=(vcpu,),
                        name=f"vcpu-{vcpu.vcpu_id}"
                    )
                    thread.start()
                    self.vcpu_threads.append(thread)
                    vcpu.thread_id = thread.ident
                    
                self.state = VMState.RUNNING
                self.started_at = time.time()
                
                logger.info(f"Started VM {self.config.name}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to start VM: {e}")
                self.state = VMState.CRASHED
                return False
                
    def _vm_main_loop(self, control_pipe):
        """Main VM process loop"""
        logger.info(f"VM {self.config.name} main loop started")
        
        while True:
            # Check for control messages
            if control_pipe.poll(0.1):
                msg = control_pipe.recv()
                if msg['type'] == 'stop':
                    break
                elif msg['type'] == 'pause':
                    self.state = VMState.PAUSED
                elif msg['type'] == 'resume':
                    self.state = VMState.RUNNING
                    
            # Handle VM events
            if self.state == VMState.RUNNING:
                # Process pending I/O
                self._process_io()
                
                # Check for interrupts
                self._check_interrupts()
                
    def _vcpu_loop(self, vcpu: VCPUState):
        """VCPU execution loop"""
        logger.info(f"VCPU {vcpu.vcpu_id} started")
        
        while self.state != VMState.STOPPED:
            if self.state == VMState.RUNNING:
                # Execute instructions
                self._execute_vcpu(vcpu)
            else:
                # Sleep if paused
                time.sleep(0.001)
                
    def _execute_vcpu(self, vcpu: VCPUState):
        """Execute instructions on VCPU"""
        # Simplified instruction execution
        # In real implementation, would decode and execute x86 instructions
        
        # Fetch instruction
        try:
            instruction = self._fetch_instruction(vcpu)
            
            # Decode and execute
            self._execute_instruction(vcpu, instruction)
            
            # Update performance counters
            vcpu.instructions_executed += 1
            vcpu.cycles += 1
            
        except Exception as e:
            logger.error(f"VCPU {vcpu.vcpu_id} exception: {e}")
            self._handle_vm_exit(vcpu, 'exception')
            
    def _fetch_instruction(self, vcpu: VCPUState) -> bytes:
        """Fetch instruction at RIP"""
        # Translate virtual to physical address
        phys_addr = self._translate_address(vcpu, vcpu.rip)
        
        # Read instruction bytes (simplified - read 15 bytes max)
        instruction = self._read_physical_memory(phys_addr, 15)
        
        return instruction
        
    def _translate_address(self, vcpu: VCPUState, virt_addr: int) -> int:
        """Translate virtual to physical address"""
        # Simplified - no paging for now
        return virt_addr
        
    def _read_physical_memory(self, phys_addr: int, length: int) -> bytes:
        """Read from physical memory"""
        # Find memory region
        for base, region in self.memory_regions.items():
            if base <= phys_addr < base + region.size:
                offset = phys_addr - base
                return region.read(offset, length)
                
        # Memory not mapped
        raise ValueError(f"Invalid physical address: 0x{phys_addr:x}")
        
    def _write_physical_memory(self, phys_addr: int, data: bytes):
        """Write to physical memory"""
        # Find memory region
        for base, region in self.memory_regions.items():
            if base <= phys_addr < base + region.size:
                offset = phys_addr - base
                region.write(offset, data)
                return
                
        # Check MMIO regions
        for (start, end), handler in self.mmio_regions.items():
            if start <= phys_addr < end:
                handler(phys_addr, data, is_write=True)
                return
                
        # Memory not mapped
        raise ValueError(f"Invalid physical address: 0x{phys_addr:x}")
        
    def _execute_instruction(self, vcpu: VCPUState, instruction: bytes):
        """Execute single instruction"""
        # Very simplified instruction execution
        # In real implementation, would have full x86 decoder
        
        opcode = instruction[0]
        
        # NOP
        if opcode == 0x90:
            vcpu.rip += 1
            
        # HLT
        elif opcode == 0xF4:
            self._handle_vm_exit(vcpu, 'hlt')
            
        # MOV immediate to register
        elif opcode >= 0xB8 and opcode <= 0xBF:
            reg = opcode - 0xB8
            value = struct.unpack('<Q', instruction[1:9])[0]
            self._set_register(vcpu, reg, value)
            vcpu.rip += 9
            
        # INT (software interrupt)
        elif opcode == 0xCD:
            vector = instruction[1]
            self._handle_interrupt(vcpu, vector)
            vcpu.rip += 2
            
        else:
            # Unknown instruction
            logger.warning(f"Unknown instruction: 0x{opcode:02x}")
            vcpu.rip += 1
            
    def _set_register(self, vcpu: VCPUState, reg: int, value: int):
        """Set general purpose register"""
        registers = [
            'rax', 'rcx', 'rdx', 'rbx', 'rsp', 'rbp', 'rsi', 'rdi',
            'r8', 'r9', 'r10', 'r11', 'r12', 'r13', 'r14', 'r15'
        ]
        
        if reg < len(registers):
            setattr(vcpu, registers[reg], value)
            
    def _handle_interrupt(self, vcpu: VCPUState, vector: int):
        """Handle software interrupt"""
        logger.info(f"VCPU {vcpu.vcpu_id} interrupt 0x{vector:02x}")
        
        # BIOS interrupts
        if vector == 0x10:  # Video services
            self._handle_video_interrupt(vcpu)
        elif vector == 0x13:  # Disk services
            self._handle_disk_interrupt(vcpu)
        elif vector == 0x15:  # System services
            self._handle_system_interrupt(vcpu)
            
    def _handle_video_interrupt(self, vcpu: VCPUState):
        """Handle INT 10h video services"""
        ah = (vcpu.rax >> 8) & 0xFF
        
        if ah == 0x00:  # Set video mode
            mode = vcpu.rax & 0xFF
            logger.info(f"Set video mode: {mode}")
        elif ah == 0x0E:  # Write character
            char = vcpu.rax & 0xFF
            logger.info(f"Write character: {chr(char)}")
            
    def _handle_disk_interrupt(self, vcpu: VCPUState):
        """Handle INT 13h disk services"""
        ah = (vcpu.rax >> 8) & 0xFF
        
        if ah == 0x02:  # Read sectors
            logger.info("Read disk sectors")
            vcpu.rflags &= ~1  # Clear carry flag (success)
        elif ah == 0x03:  # Write sectors
            logger.info("Write disk sectors")
            vcpu.rflags &= ~1  # Clear carry flag (success)
            
    def _handle_system_interrupt(self, vcpu: VCPUState):
        """Handle INT 15h system services"""
        ah = (vcpu.rax >> 8) & 0xFF
        
        if ah == 0x88:  # Get extended memory size
            # Return 64MB
            vcpu.rax = 65535
            vcpu.rflags &= ~1  # Clear carry flag
            
    def _handle_vm_exit(self, vcpu: VCPUState, reason: str):
        """Handle VM exit"""
        logger.debug(f"VM exit on VCPU {vcpu.vcpu_id}: {reason}")
        
        if reason == 'hlt':
            # CPU halted, wait for interrupt
            vcpu.interrupt_pending = True
            
    def _process_io(self):
        """Process pending I/O operations"""
        # In real implementation, would handle device I/O
        pass
        
    def _check_interrupts(self):
        """Check and deliver pending interrupts"""
        if self.interrupt_controller:
            for vcpu in self.vcpus:
                if vcpu.interrupt_pending:
                    vector = self.interrupt_controller.get_pending_interrupt()
                    if vector is not None:
                        self._deliver_interrupt(vcpu, vector)
                        vcpu.interrupt_pending = False
                        
    def _deliver_interrupt(self, vcpu: VCPUState, vector: int):
        """Deliver interrupt to VCPU"""
        logger.debug(f"Delivering interrupt {vector} to VCPU {vcpu.vcpu_id}")
        
        # Save current state on stack
        # Jump to interrupt handler
        # In real implementation, would modify VCPU state
        
    # I/O handlers
    def _handle_serial_io(self, port: int, value: Optional[int] = None, is_write: bool = False):
        """Handle serial port I/O"""
        if is_write:
            # Output character
            if port == 0x3F8 and value is not None:
                logger.info(f"Serial output: {chr(value)}")
        else:
            # Input - return no data available
            return 0
            
    def _handle_vga_io(self, port: int, value: Optional[int] = None, is_write: bool = False):
        """Handle VGA I/O"""
        if is_write:
            logger.debug(f"VGA write port 0x{port:x} = 0x{value:x}")
        else:
            return 0
            
    def _handle_keyboard_io(self, port: int, value: Optional[int] = None, is_write: bool = False):
        """Handle keyboard controller I/O"""
        if is_write:
            logger.debug(f"Keyboard write port 0x{port:x} = 0x{value:x}")
        else:
            # No key pressed
            return 0
            
    def _handle_pic_io(self, port: int, value: Optional[int] = None, is_write: bool = False):
        """Handle PIC I/O"""
        if is_write:
            logger.debug(f"PIC write port 0x{port:x} = 0x{value:x}")
        else:
            return 0
            
    def _handle_apic_mmio(self, addr: int, data: Optional[bytes] = None, is_write: bool = False):
        """Handle APIC MMIO"""
        if is_write:
            logger.debug(f"APIC write addr 0x{addr:x}")
        else:
            # Return zeros
            return b'\x00' * 4
            
    def _handle_hpet_mmio(self, addr: int, data: Optional[bytes] = None, is_write: bool = False):
        """Handle HPET MMIO"""
        if is_write:
            logger.debug(f"HPET write addr 0x{addr:x}")
        else:
            # Return zeros
            return b'\x00' * 8
            
    def stop(self, timeout: int = 10) -> bool:
        """Stop virtual machine"""
        with self._lock:
            if self.state == VMState.STOPPED:
                return True
                
            try:
                # Send stop message
                if self.control_pipe:
                    self.control_pipe.send({'type': 'stop'})
                    
                # Wait for VM process to stop
                if self.vm_process:
                    self.vm_process.join(timeout)
                    if self.vm_process.is_alive():
                        self.vm_process.terminate()
                        
                # Stop VCPU threads
                self.state = VMState.STOPPED
                for thread in self.vcpu_threads:
                    thread.join(timeout=1.0)
                    
                # Cleanup resources
                if self.shared_memory:
                    self.shared_memory.close()
                    
                logger.info(f"Stopped VM {self.config.name}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to stop VM: {e}")
                return False
                
    def pause(self) -> bool:
        """Pause virtual machine"""
        with self._lock:
            if self.state != VMState.RUNNING:
                return False
                
            if self.control_pipe:
                self.control_pipe.send({'type': 'pause'})
                self.state = VMState.PAUSED
                logger.info(f"Paused VM {self.config.name}")
                return True
                
        return False
        
    def resume(self) -> bool:
        """Resume virtual machine"""
        with self._lock:
            if self.state != VMState.PAUSED:
                return False
                
            if self.control_pipe:
                self.control_pipe.send({'type': 'resume'})
                self.state = VMState.RUNNING
                logger.info(f"Resumed VM {self.config.name}")
                return True
                
        return False
        
    def reset(self) -> bool:
        """Reset virtual machine"""
        with self._lock:
            # Reset VCPU states
            for vcpu in self.vcpus:
                vcpu.rip = 0xFFFFFFF0  # Reset vector
                vcpu.cs = 0xF000
                vcpu.rflags = 0x2
                
            # Clear memory
            for region in self.memory_regions.values():
                region.data = bytearray(region.size)
                region.clear_dirty()
                
            logger.info(f"Reset VM {self.config.name}")
            return True
            
    def get_stats(self) -> Dict[str, Any]:
        """Get VM statistics"""
        with self._lock:
            return {
                'state': self.state.name,
                'vcpus': len(self.vcpus),
                'memory_mb': self.config.memory_mb,
                'uptime': time.time() - self.started_at if self.started_at else 0,
                **self.stats
            }


class InterruptController:
    """Interrupt controller (PIC/APIC emulation)"""
    
    def __init__(self):
        self.irr = 0  # Interrupt Request Register
        self.isr = 0  # In-Service Register
        self.imr = 0  # Interrupt Mask Register
        self.priority = 0
        self._lock = threading.Lock()
        
    def raise_interrupt(self, irq: int):
        """Raise interrupt request"""
        with self._lock:
            self.irr |= (1 << irq)
            
    def get_pending_interrupt(self) -> Optional[int]:
        """Get highest priority pending interrupt"""
        with self._lock:
            # Find highest priority unmasked interrupt
            pending = self.irr & ~self.imr & ~self.isr
            
            if pending == 0:
                return None
                
            # Find lowest bit set (highest priority)
            for i in range(16):
                if pending & (1 << i):
                    # Mark as in-service
                    self.isr |= (1 << i)
                    self.irr &= ~(1 << i)
                    return i + 0x20  # IRQ0 = vector 0x20
                    
            return None
            
    def eoi(self, irq: int):
        """End of interrupt"""
        with self._lock:
            self.isr &= ~(1 << irq)


class Hypervisor:
    """KOS Hypervisor manager"""
    
    def __init__(self, kernel):
        self.kernel = kernel
        self.vms: Dict[str, VirtualMachine] = {}
        self._lock = threading.RLock()
        
        # Check virtualization support
        self.kvm_available = self._check_kvm_support()
        
    def _check_kvm_support(self) -> bool:
        """Check if KVM is available"""
        return os.path.exists("/dev/kvm") and os.access("/dev/kvm", os.R_OK)
        
    def create_vm(self, config: VMConfig) -> VirtualMachine:
        """Create new virtual machine"""
        with self._lock:
            # Generate VM ID
            vm_id = str(uuid.uuid4())
            
            # Check name uniqueness
            for vm in self.vms.values():
                if vm.config.name == config.name:
                    raise ValueError(f"VM name '{config.name}' already exists")
                    
            # Create VM
            vm = VirtualMachine(vm_id, config)
            self.vms[vm_id] = vm
            
            logger.info(f"Created VM {config.name} ({vm_id})")
            return vm
            
    def list_vms(self) -> List[VirtualMachine]:
        """List all VMs"""
        with self._lock:
            return list(self.vms.values())
            
    def get_vm(self, vm_id: str) -> Optional[VirtualMachine]:
        """Get VM by ID"""
        return self.vms.get(vm_id)
        
    def delete_vm(self, vm_id: str) -> bool:
        """Delete VM"""
        with self._lock:
            vm = self.vms.get(vm_id)
            if not vm:
                return False
                
            # Stop VM if running
            if vm.state == VMState.RUNNING:
                vm.stop()
                
            # Remove from registry
            del self.vms[vm_id]
            
            logger.info(f"Deleted VM {vm.config.name}")
            return True
            
    def migrate_vm(self, vm_id: str, target_host: str) -> bool:
        """Live migrate VM to another host"""
        vm = self.get_vm(vm_id)
        if not vm or vm.state != VMState.RUNNING:
            return False
            
        logger.info(f"Migrating VM {vm.config.name} to {target_host}")
        
        # Simplified migration
        # 1. Pause VM
        vm.pause()
        
        # 2. Copy memory pages (track dirty pages)
        # 3. Copy device state
        # 4. Resume on target
        
        # For now, just log
        logger.info("Migration not fully implemented")
        vm.resume()
        
        return True


# Global hypervisor instance
_hypervisor = None

def get_hypervisor(kernel) -> Hypervisor:
    """Get global hypervisor instance"""
    global _hypervisor
    if _hypervisor is None:
        _hypervisor = Hypervisor(kernel)
    return _hypervisor