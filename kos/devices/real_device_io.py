"""
KOS Real Device I/O Implementation
Direct hardware access using Linux kernel interfaces
"""

import os
import fcntl
import struct
import array
import select
import termios
import logging
from typing import Optional, Dict, Any, List, Tuple

logger = logging.getLogger('kos.devices.real_io')


# Linux ioctl constants
class IoctlConstants:
    """Linux ioctl constants for various devices"""
    
    # Terminal ioctls
    TCGETS = 0x5401
    TCSETS = 0x5402
    TCSETSW = 0x5403
    TCSETSF = 0x5404
    TCGETA = 0x5405
    TCSETA = 0x5406
    TCSETAW = 0x5407
    TCSETAF = 0x5408
    TCSBRK = 0x5409
    TCXONC = 0x540A
    TCFLSH = 0x540B
    TIOCEXCL = 0x540C
    TIOCNXCL = 0x540D
    TIOCSCTTY = 0x540E
    TIOCGPGRP = 0x540F
    TIOCSPGRP = 0x5410
    TIOCOUTQ = 0x5411
    TIOCSTI = 0x5412
    TIOCGWINSZ = 0x5413
    TIOCSWINSZ = 0x5414
    TIOCMGET = 0x5415
    TIOCMBIS = 0x5416
    TIOCMBIC = 0x5417
    TIOCMSET = 0x5418
    TIOCGSOFTCAR = 0x5419
    TIOCSSOFTCAR = 0x541A
    
    # Block device ioctls
    BLKRRPART = 0x125F
    BLKGETSIZE = 0x1260
    BLKFLSBUF = 0x1261
    BLKRASET = 0x1262
    BLKRAGET = 0x1263
    BLKFRASET = 0x1264
    BLKFRAGET = 0x1265
    BLKSECTSET = 0x1266
    BLKSECTGET = 0x1267
    BLKSSZGET = 0x1268
    BLKBSZGET = 0x80081270
    BLKBSZSET = 0x40081271
    BLKGETSIZE64 = 0x80081272
    BLKTRACESETUP = 0xC0481273
    BLKTRACESTART = 0x1274
    BLKTRACESTOP = 0x1275
    BLKTRACETEARDOWN = 0x1276
    BLKDISCARD = 0x1277
    BLKIOMIN = 0x1278
    BLKIOOPT = 0x1279
    BLKALIGNOFF = 0x127A
    BLKPBSZGET = 0x127B
    BLKDISCARDZEROES = 0x127C
    BLKSECDISCARD = 0x127D
    BLKROTATIONAL = 0x127E
    BLKZEROOUT = 0x127F
    
    # SCSI generic ioctls
    SG_IO = 0x2285
    SG_GET_VERSION_NUM = 0x2282
    
    # Input device ioctls
    EVIOCGVERSION = 0x80044501
    EVIOCGID = 0x80084502
    EVIOCGREP = 0x80084503
    EVIOCSREP = 0x40084503
    EVIOCGKEYCODE = 0x80084504
    EVIOCGKEYCODE_V2 = 0x80284504
    EVIOCSKEYCODE = 0x40084504
    EVIOCSKEYCODE_V2 = 0x40284504
    EVIOCGNAME = lambda len: (2 << 30) | (ord('E') << 8) | (0x06 << 0) | (len << 16)
    EVIOCGPHYS = lambda len: (2 << 30) | (ord('E') << 8) | (0x07 << 0) | (len << 16)
    EVIOCGUNIQ = lambda len: (2 << 30) | (ord('E') << 8) | (0x08 << 0) | (len << 16)
    EVIOCGPROP = lambda len: (2 << 30) | (ord('E') << 8) | (0x09 << 0) | (len << 16)
    EVIOCGBIT = lambda ev, len: (2 << 30) | (ord('E') << 8) | (0x20 + ev << 0) | (len << 16)
    EVIOCGABS = lambda abs: (2 << 30) | (ord('E') << 8) | (0x40 + abs << 0) | (40 << 16)
    EVIOCSABS = lambda abs: (1 << 30) | (ord('E') << 8) | (0xC0 + abs << 0) | (40 << 16)


class RealDeviceIO:
    """Real device I/O operations"""
    
    def __init__(self):
        self.ioctl = IoctlConstants()
        
    def open_device(self, path: str, flags: int = os.O_RDWR) -> int:
        """Open device file"""
        return os.open(path, flags)
        
    def close_device(self, fd: int):
        """Close device file"""
        os.close(fd)
        
    def read_device(self, fd: int, size: int) -> bytes:
        """Read from device"""
        return os.read(fd, size)
        
    def write_device(self, fd: int, data: bytes) -> int:
        """Write to device"""
        return os.write(fd, data)
        
    def ioctl_device(self, fd: int, request: int, arg: Any = None) -> Any:
        """Perform ioctl on device"""
        try:
            return fcntl.ioctl(fd, request, arg)
        except IOError as e:
            logger.error(f"ioctl failed: {e}")
            raise


class RealBlockDevice(RealDeviceIO):
    """Real block device operations"""
    
    def get_size(self, device_path: str) -> int:
        """Get block device size in bytes"""
        fd = self.open_device(device_path, os.O_RDONLY)
        try:
            buf = array.array('Q', [0])
            self.ioctl_device(fd, self.ioctl.BLKGETSIZE64, buf)
            return buf[0]
        finally:
            self.close_device(fd)
            
    def get_sector_size(self, device_path: str) -> int:
        """Get logical sector size"""
        fd = self.open_device(device_path, os.O_RDONLY)
        try:
            buf = array.array('i', [0])
            self.ioctl_device(fd, self.ioctl.BLKSSZGET, buf)
            return buf[0]
        finally:
            self.close_device(fd)
            
    def get_physical_block_size(self, device_path: str) -> int:
        """Get physical block size"""
        fd = self.open_device(device_path, os.O_RDONLY)
        try:
            buf = array.array('i', [0])
            self.ioctl_device(fd, self.ioctl.BLKPBSZGET, buf)
            return buf[0]
        finally:
            self.close_device(fd)
            
    def flush_buffers(self, device_path: str):
        """Flush device buffers"""
        fd = self.open_device(device_path, os.O_RDONLY)
        try:
            self.ioctl_device(fd, self.ioctl.BLKFLSBUF, 0)
        finally:
            self.close_device(fd)
            
    def reread_partition_table(self, device_path: str):
        """Re-read partition table"""
        fd = self.open_device(device_path, os.O_RDONLY)
        try:
            self.ioctl_device(fd, self.ioctl.BLKRRPART, 0)
        finally:
            self.close_device(fd)
            
    def discard_range(self, device_path: str, offset: int, length: int):
        """Discard/TRIM range on device"""
        fd = self.open_device(device_path, os.O_RDWR)
        try:
            buf = struct.pack('QQ', offset, length)
            self.ioctl_device(fd, self.ioctl.BLKDISCARD, buf)
        finally:
            self.close_device(fd)
            
    def secure_discard_range(self, device_path: str, offset: int, length: int):
        """Secure discard range on device"""
        fd = self.open_device(device_path, os.O_RDWR)
        try:
            buf = struct.pack('QQ', offset, length)
            self.ioctl_device(fd, self.ioctl.BLKSECDISCARD, buf)
        finally:
            self.close_device(fd)
            
    def zero_range(self, device_path: str, offset: int, length: int):
        """Zero out range on device"""
        fd = self.open_device(device_path, os.O_RDWR)
        try:
            buf = struct.pack('QQ', offset, length)
            self.ioctl_device(fd, self.ioctl.BLKZEROOUT, buf)
        finally:
            self.close_device(fd)
            
    def is_rotational(self, device_path: str) -> bool:
        """Check if device is rotational (HDD)"""
        fd = self.open_device(device_path, os.O_RDONLY)
        try:
            buf = array.array('H', [0])
            self.ioctl_device(fd, self.ioctl.BLKROTATIONAL, buf)
            return bool(buf[0])
        finally:
            self.close_device(fd)
            
    def read_sectors(self, device_path: str, start_sector: int, num_sectors: int,
                    sector_size: int = 512) -> bytes:
        """Read sectors from device"""
        fd = self.open_device(device_path, os.O_RDONLY | os.O_DIRECT)
        try:
            offset = start_sector * sector_size
            size = num_sectors * sector_size
            
            # Seek to position
            os.lseek(fd, offset, os.SEEK_SET)
            
            # Read data
            return self.read_device(fd, size)
        finally:
            self.close_device(fd)
            
    def write_sectors(self, device_path: str, start_sector: int, data: bytes,
                     sector_size: int = 512):
        """Write sectors to device"""
        if len(data) % sector_size != 0:
            raise ValueError("Data size must be multiple of sector size")
            
        fd = self.open_device(device_path, os.O_WRONLY | os.O_DIRECT)
        try:
            offset = start_sector * sector_size
            
            # Seek to position
            os.lseek(fd, offset, os.SEEK_SET)
            
            # Write data
            self.write_device(fd, data)
            
            # Sync to ensure data is written
            os.fsync(fd)
        finally:
            self.close_device(fd)


class RealInputDevice(RealDeviceIO):
    """Real input device operations"""
    
    # Input event types
    EV_SYN = 0x00
    EV_KEY = 0x01
    EV_REL = 0x02
    EV_ABS = 0x03
    EV_MSC = 0x04
    EV_SW = 0x05
    EV_LED = 0x11
    EV_SND = 0x12
    EV_REP = 0x14
    EV_FF = 0x15
    EV_PWR = 0x16
    EV_FF_STATUS = 0x17
    
    def __init__(self):
        super().__init__()
        self.event_struct = struct.Struct('llHHI')  # timeval (2 longs) + type + code + value
        
    def get_device_info(self, device_path: str) -> Dict[str, Any]:
        """Get input device information"""
        fd = self.open_device(device_path, os.O_RDONLY)
        try:
            info = {}
            
            # Get version
            version = array.array('i', [0])
            self.ioctl_device(fd, self.ioctl.EVIOCGVERSION, version)
            info['version'] = version[0]
            
            # Get ID
            id_buf = array.array('H', [0, 0, 0, 0])
            self.ioctl_device(fd, self.ioctl.EVIOCGID, id_buf)
            info['bustype'] = id_buf[0]
            info['vendor'] = id_buf[1]
            info['product'] = id_buf[2]
            info['version'] = id_buf[3]
            
            # Get name
            name_buf = bytearray(256)
            name_len = self.ioctl_device(fd, self.ioctl.EVIOCGNAME(256), name_buf)
            info['name'] = name_buf[:name_len-1].decode('utf-8')
            
            # Get physical location
            phys_buf = bytearray(256)
            try:
                phys_len = self.ioctl_device(fd, self.ioctl.EVIOCGPHYS(256), phys_buf)
                info['phys'] = phys_buf[:phys_len-1].decode('utf-8')
            except:
                info['phys'] = ''
                
            # Get unique ID
            uniq_buf = bytearray(256)
            try:
                uniq_len = self.ioctl_device(fd, self.ioctl.EVIOCGUNIQ(256), uniq_buf)
                info['uniq'] = uniq_buf[:uniq_len-1].decode('utf-8')
            except:
                info['uniq'] = ''
                
            return info
            
        finally:
            self.close_device(fd)
            
    def get_capabilities(self, device_path: str) -> Dict[int, List[int]]:
        """Get device capabilities"""
        fd = self.open_device(device_path, os.O_RDONLY)
        try:
            capabilities = {}
            
            # Check each event type
            for ev_type in range(32):
                bit_array = array.array('B', [0] * 64)  # 512 bits
                try:
                    self.ioctl_device(fd, self.ioctl.EVIOCGBIT(ev_type, 64), bit_array)
                    
                    # Convert bit array to list of supported codes
                    codes = []
                    for byte_idx, byte_val in enumerate(bit_array):
                        if byte_val:
                            for bit in range(8):
                                if byte_val & (1 << bit):
                                    codes.append(byte_idx * 8 + bit)
                                    
                    if codes:
                        capabilities[ev_type] = codes
                except:
                    pass
                    
            return capabilities
            
        finally:
            self.close_device(fd)
            
    def read_event(self, fd: int) -> Optional[Tuple[float, int, int, int]]:
        """Read single input event"""
        try:
            data = self.read_device(fd, self.event_struct.size)
            if len(data) == self.event_struct.size:
                tv_sec, tv_usec, ev_type, ev_code, ev_value = self.event_struct.unpack(data)
                timestamp = tv_sec + tv_usec / 1000000.0
                return (timestamp, ev_type, ev_code, ev_value)
        except:
            pass
        return None
        
    def write_event(self, fd: int, ev_type: int, ev_code: int, ev_value: int):
        """Write input event"""
        import time
        tv_sec = int(time.time())
        tv_usec = int((time.time() - tv_sec) * 1000000)
        
        data = self.event_struct.pack(tv_sec, tv_usec, ev_type, ev_code, ev_value)
        self.write_device(fd, data)
        
    def grab_device(self, fd: int, grab: bool = True):
        """Grab exclusive access to device"""
        EVIOCGRAB = 0x40044590
        self.ioctl_device(fd, EVIOCGRAB, 1 if grab else 0)
        
    def set_led(self, fd: int, led_code: int, state: bool):
        """Set LED state"""
        self.write_event(fd, self.EV_LED, led_code, 1 if state else 0)
        self.write_event(fd, self.EV_SYN, 0, 0)  # Sync
        
    def monitor_device(self, device_path: str, callback):
        """Monitor device for events"""
        fd = self.open_device(device_path, os.O_RDONLY | os.O_NONBLOCK)
        try:
            while True:
                # Use select to wait for events
                r, _, _ = select.select([fd], [], [], 1.0)
                
                if fd in r:
                    # Read all available events
                    while True:
                        event = self.read_event(fd)
                        if event:
                            if not callback(event):
                                return
                        else:
                            break
                            
        finally:
            self.close_device(fd)


class RealTerminalDevice(RealDeviceIO):
    """Real terminal device operations"""
    
    def get_window_size(self, fd: int) -> Tuple[int, int]:
        """Get terminal window size"""
        buf = array.array('H', [0, 0, 0, 0])
        self.ioctl_device(fd, self.ioctl.TIOCGWINSZ, buf)
        return (buf[0], buf[1])  # rows, cols
        
    def set_window_size(self, fd: int, rows: int, cols: int):
        """Set terminal window size"""
        buf = struct.pack('HHHH', rows, cols, 0, 0)
        self.ioctl_device(fd, self.ioctl.TIOCSWINSZ, buf)
        
    def get_terminal_attributes(self, fd: int) -> termios.tcgetattr:
        """Get terminal attributes"""
        return termios.tcgetattr(fd)
        
    def set_terminal_attributes(self, fd: int, when: int, attrs):
        """Set terminal attributes"""
        termios.tcsetattr(fd, when, attrs)
        
    def set_raw_mode(self, fd: int):
        """Set terminal to raw mode"""
        attrs = termios.tcgetattr(fd)
        attrs[3] &= ~(termios.ECHO | termios.ICANON | termios.ISIG)
        termios.tcsetattr(fd, termios.TCSANOW, attrs)
        
    def set_cooked_mode(self, fd: int):
        """Set terminal to cooked mode"""
        attrs = termios.tcgetattr(fd)
        attrs[3] |= (termios.ECHO | termios.ICANON | termios.ISIG)
        termios.tcsetattr(fd, termios.TCSANOW, attrs)
        
    def get_foreground_process_group(self, fd: int) -> int:
        """Get foreground process group"""
        buf = array.array('i', [0])
        self.ioctl_device(fd, self.ioctl.TIOCGPGRP, buf)
        return buf[0]
        
    def set_foreground_process_group(self, fd: int, pgid: int):
        """Set foreground process group"""
        buf = array.array('i', [pgid])
        self.ioctl_device(fd, self.ioctl.TIOCSPGRP, buf)
        
    def send_break(self, fd: int, duration: int = 0):
        """Send break signal"""
        self.ioctl_device(fd, self.ioctl.TCSBRK, duration)
        
    def flush_input(self, fd: int):
        """Flush input buffer"""
        termios.tcflush(fd, termios.TCIFLUSH)
        
    def flush_output(self, fd: int):
        """Flush output buffer"""
        termios.tcflush(fd, termios.TCOFLUSH)
        
    def get_output_queue_size(self, fd: int) -> int:
        """Get number of bytes in output queue"""
        buf = array.array('i', [0])
        self.ioctl_device(fd, self.ioctl.TIOCOUTQ, buf)
        return buf[0]


# Global device I/O instances
_block_device_io = None
_input_device_io = None
_terminal_device_io = None

def get_block_device_io() -> RealBlockDevice:
    """Get global block device I/O instance"""
    global _block_device_io
    if _block_device_io is None:
        _block_device_io = RealBlockDevice()
    return _block_device_io

def get_input_device_io() -> RealInputDevice:
    """Get global input device I/O instance"""
    global _input_device_io
    if _input_device_io is None:
        _input_device_io = RealInputDevice()
    return _input_device_io

def get_terminal_device_io() -> RealTerminalDevice:
    """Get global terminal device I/O instance"""
    global _terminal_device_io
    if _terminal_device_io is None:
        _terminal_device_io = RealTerminalDevice()
    return _terminal_device_io