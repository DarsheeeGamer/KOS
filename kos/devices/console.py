"""
Console Device Implementation

Provides console/terminal device functionality similar to /dev/console.
"""

import os
import sys
import logging
import termios
import tty
import select
from typing import Optional, Any, List

logger = logging.getLogger('KOS.devices.console')


class ConsoleDevice:
    """
    Console device implementation (/dev/console)
    
    Provides system console functionality with terminal control.
    """
    
    def __init__(self, name: str = "console"):
        self.name = name
        self.major = 5  # Standard major number for console
        self.minor = 1  # Standard minor number for console
        self.mode = 0o620  # crw--w---- (owner read/write, group write)
        self.device_type = 'c'  # Character device
        
        # Terminal settings
        self.rows = 24
        self.cols = 80
        self.current_row = 0
        self.current_col = 0
        
        # Input/output buffers
        self.input_buffer = []
        self.output_buffer = []
        
        # Terminal attributes
        self.termios_settings = None
        self.is_raw = False
        self.echo_enabled = True
        
        # Try to get real terminal settings if available
        try:
            if sys.stdin.isatty():
                self.termios_settings = termios.tcgetattr(sys.stdin.fileno())
                # Get terminal size
                import shutil
                size = shutil.get_terminal_size()
                self.cols = size.columns
                self.rows = size.lines
        except:
            pass
            
    def open(self, flags: int = os.O_RDWR) -> 'ConsoleDevice':
        """Open the console device"""
        logger.debug(f"Opening console device with flags {flags}")
        return self
        
    def close(self) -> None:
        """Close the console device"""
        logger.debug("Closing console device")
        
        # Restore terminal settings if changed
        if self.is_raw and self.termios_settings and sys.stdin.isatty():
            try:
                termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, self.termios_settings)
            except:
                pass
                
    def read(self, size: int = -1) -> bytes:
        """
        Read from console device
        
        Args:
            size: Number of bytes to read (-1 for line-buffered)
            
        Returns:
            Bytes read from console
        """
        if size == 0:
            return b''
            
        # Check if we have buffered input
        if self.input_buffer:
            if size == -1:
                # Read until newline
                result = []
                while self.input_buffer:
                    char = self.input_buffer.pop(0)
                    result.append(char)
                    if char == ord('\n'):
                        break
                return bytes(result)
            else:
                # Read specified number of bytes
                result = self.input_buffer[:size]
                self.input_buffer = self.input_buffer[size:]
                return bytes(result)
        
        # Read from stdin if available
        if sys.stdin.isatty():
            try:
                if self.is_raw:
                    # Raw mode - read single character
                    data = sys.stdin.read(1 if size == -1 else size)
                else:
                    # Line-buffered mode
                    if size == -1:
                        data = sys.stdin.readline()
                    else:
                        data = sys.stdin.read(size)
                return data.encode('utf-8')
            except Exception as e:
                logger.error(f"Console read error: {e}")
                return b''
        else:
            # No real terminal - return empty
            return b''
            
    def write(self, data: bytes) -> int:
        """
        Write to console device
        
        Args:
            data: Data to write
            
        Returns:
            Number of bytes written
        """
        try:
            # Convert bytes to string
            text = data.decode('utf-8', errors='replace')
            
            # Process control characters
            for char in text:
                if char == '\n':
                    self.current_row += 1
                    self.current_col = 0
                elif char == '\r':
                    self.current_col = 0
                elif char == '\t':
                    self.current_col = ((self.current_col + 8) // 8) * 8
                elif char == '\b':
                    if self.current_col > 0:
                        self.current_col -= 1
                else:
                    self.current_col += 1
                    
                # Wrap to next line if needed
                if self.current_col >= self.cols:
                    self.current_col = 0
                    self.current_row += 1
                    
                # Scroll if at bottom
                if self.current_row >= self.rows:
                    self.current_row = self.rows - 1
                    
            # Write to stdout if available
            if sys.stdout.isatty():
                sys.stdout.write(text)
                sys.stdout.flush()
            else:
                # Buffer output
                self.output_buffer.extend(data)
                
            return len(data)
            
        except Exception as e:
            logger.error(f"Console write error: {e}")
            return 0
            
    def seek(self, offset: int, whence: int = os.SEEK_SET) -> int:
        """Seek not supported on console device"""
        raise OSError("Console device does not support seeking")
        
    def tell(self) -> int:
        """Tell not supported on console device"""
        raise OSError("Console device does not support position queries")
        
    def truncate(self, size: Optional[int] = None) -> int:
        """Truncate not supported on console device"""
        raise OSError("Console device does not support truncation")
        
    def flush(self) -> None:
        """Flush console output"""
        if sys.stdout.isatty():
            sys.stdout.flush()
            
    def fileno(self) -> int:
        """Get file descriptor"""
        if sys.stdout.isatty():
            return sys.stdout.fileno()
        return -1
        
    def isatty(self) -> bool:
        """Check if device is a TTY"""
        return sys.stdout.isatty()
        
    def readable(self) -> bool:
        """Check if device is readable"""
        return True
        
    def writable(self) -> bool:
        """Check if device is writable"""
        return True
        
    def seekable(self) -> bool:
        """Check if device is seekable"""
        return False
        
    def ioctl(self, request: int, arg: Any = 0) -> Any:
        """
        Perform ioctl operation
        
        Args:
            request: ioctl request code
            arg: ioctl argument
            
        Returns:
            Result depends on request
        """
        # TIOCGWINSZ - Get window size
        if request == 0x5413:
            import struct
            return struct.pack('HHHH', self.rows, self.cols, 0, 0)
            
        # TIOCSWINSZ - Set window size
        elif request == 0x5414:
            if isinstance(arg, bytes) and len(arg) >= 8:
                import struct
                self.rows, self.cols = struct.unpack('HH', arg[:4])
                return 0
                
        # TCGETS - Get terminal attributes
        elif request == 0x5401:
            if self.termios_settings:
                return self.termios_settings
                
        # TCSETS - Set terminal attributes
        elif request == 0x5402:
            if arg:
                self.termios_settings = arg
                if sys.stdin.isatty():
                    termios.tcsetattr(sys.stdin.fileno(), termios.TCSANOW, arg)
                return 0
                
        # TIOCGPGRP - Get process group
        elif request == 0x540F:
            return os.getpgrp()
            
        # VT_GETMODE - Get VT mode
        elif request == 0x5601:
            return 0  # VT_AUTO
            
        else:
            logger.debug(f"Unknown ioctl request 0x{request:x} on console device")
            return -1
            
    def set_raw_mode(self, enable: bool = True) -> None:
        """Enable or disable raw mode"""
        if not sys.stdin.isatty():
            return
            
        if enable and not self.is_raw:
            # Save current settings
            self.termios_settings = termios.tcgetattr(sys.stdin.fileno())
            # Enable raw mode
            tty.setraw(sys.stdin.fileno())
            self.is_raw = True
        elif not enable and self.is_raw:
            # Restore settings
            if self.termios_settings:
                termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, self.termios_settings)
            self.is_raw = False
            
    def clear_screen(self) -> None:
        """Clear the console screen"""
        if sys.stdout.isatty():
            # ANSI escape sequence to clear screen
            sys.stdout.write('\033[2J\033[H')
            sys.stdout.flush()
            self.current_row = 0
            self.current_col = 0
            
    def set_cursor_position(self, row: int, col: int) -> None:
        """Set cursor position"""
        if sys.stdout.isatty():
            # ANSI escape sequence to move cursor
            sys.stdout.write(f'\033[{row+1};{col+1}H')
            sys.stdout.flush()
            self.current_row = row
            self.current_col = col
            
    def stat(self) -> dict:
        """Get device statistics"""
        import time
        current_time = time.time()
        
        return {
            'st_mode': 0o020620,  # Character device with 620 permissions
            'st_ino': 0,
            'st_dev': (self.major << 8) | self.minor,
            'st_nlink': 1,
            'st_uid': 0,
            'st_gid': 5,  # tty group
            'st_size': 0,
            'st_atime': current_time,
            'st_mtime': current_time,
            'st_ctime': current_time,
            'st_blksize': 4096,
            'st_blocks': 0,
            'st_rdev': (self.major << 8) | self.minor,
        }
        
    def __repr__(self) -> str:
        return f"<ConsoleDevice name='{self.name}' size={self.rows}x{self.cols}>"