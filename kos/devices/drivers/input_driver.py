"""
Input Device Driver for KOS
Implements actual hardware access for input devices (keyboard, mouse, touchpad)
"""

import os
import struct
import fcntl
import select
import logging
import threading
import time
from typing import Dict, Any, Optional, List, Tuple, Callable
from pathlib import Path
from collections import deque
from enum import IntEnum

logger = logging.getLogger('kos.devices.input')

# Event device ioctl commands
EVIOCGVERSION = 0x80044501  # Get driver version
EVIOCGID = 0x80084502       # Get device ID
EVIOCGNAME = lambda len: 0x80004506 + (len << 16)  # Get device name
EVIOCGPHYS = lambda len: 0x80004507 + (len << 16)  # Get physical location
EVIOCGUNIQ = lambda len: 0x80004508 + (len << 16)  # Get unique ID
EVIOCGPROP = lambda len: 0x80004509 + (len << 16)  # Get properties
EVIOCGKEY = lambda len: 0x80004518 + (len << 16)   # Get key states
EVIOCGLED = lambda len: 0x80004519 + (len << 16)   # Get LED states
EVIOCGSND = lambda len: 0x8000451a + (len << 16)   # Get sound states
EVIOCGSW = lambda len: 0x8000451b + (len << 16)    # Get switch states
EVIOCGBIT = lambda ev, len: 0x80004520 + ((ev & 0x1f) << 8) + (len << 16)
EVIOCGABS = lambda abs: 0x80184540 + (abs << 16)   # Get absolute axis info
EVIOCSABS = lambda abs: 0x401845c0 + (abs << 16)   # Set absolute axis info
EVIOCGRAB = 0x40044590      # Grab/release device
EVIOCREVOKE = 0x40044591    # Revoke device access

# Event types
class EventType(IntEnum):
    EV_SYN = 0x00       # Synchronization events
    EV_KEY = 0x01       # Keyboard/button events
    EV_REL = 0x02       # Relative axis events (mouse)
    EV_ABS = 0x03       # Absolute axis events (touchpad)
    EV_MSC = 0x04       # Miscellaneous events
    EV_SW = 0x05        # Switch events
    EV_LED = 0x11       # LED events
    EV_SND = 0x12       # Sound events
    EV_REP = 0x14       # Auto-repeat events
    EV_FF = 0x15        # Force feedback
    EV_PWR = 0x16       # Power events
    EV_FF_STATUS = 0x17 # Force feedback status

# Synchronization events
class SynEvent(IntEnum):
    SYN_REPORT = 0      # End of event packet
    SYN_CONFIG = 1      # Configuration changed
    SYN_MT_REPORT = 2   # Multi-touch slot sync
    SYN_DROPPED = 3     # Events were dropped

# Key/Button codes (partial list)
class KeyCode(IntEnum):
    KEY_RESERVED = 0
    KEY_ESC = 1
    KEY_1 = 2
    KEY_2 = 3
    KEY_3 = 4
    KEY_4 = 5
    KEY_5 = 6
    KEY_6 = 7
    KEY_7 = 8
    KEY_8 = 9
    KEY_9 = 10
    KEY_0 = 11
    KEY_MINUS = 12
    KEY_EQUAL = 13
    KEY_BACKSPACE = 14
    KEY_TAB = 15
    KEY_Q = 16
    KEY_W = 17
    KEY_E = 18
    KEY_R = 19
    KEY_T = 20
    KEY_Y = 21
    KEY_U = 22
    KEY_I = 23
    KEY_O = 24
    KEY_P = 25
    KEY_LEFTBRACE = 26
    KEY_RIGHTBRACE = 27
    KEY_ENTER = 28
    KEY_LEFTCTRL = 29
    KEY_A = 30
    KEY_S = 31
    KEY_D = 32
    KEY_F = 33
    KEY_G = 34
    KEY_H = 35
    KEY_J = 36
    KEY_K = 37
    KEY_L = 38
    KEY_SEMICOLON = 39
    KEY_APOSTROPHE = 40
    KEY_GRAVE = 41
    KEY_LEFTSHIFT = 42
    KEY_BACKSLASH = 43
    KEY_Z = 44
    KEY_X = 45
    KEY_C = 46
    KEY_V = 47
    KEY_B = 48
    KEY_N = 49
    KEY_M = 50
    KEY_COMMA = 51
    KEY_DOT = 52
    KEY_SLASH = 53
    KEY_RIGHTSHIFT = 54
    KEY_KPASTERISK = 55
    KEY_LEFTALT = 56
    KEY_SPACE = 57
    KEY_CAPSLOCK = 58
    KEY_F1 = 59
    KEY_F2 = 60
    KEY_F3 = 61
    KEY_F4 = 62
    KEY_F5 = 63
    KEY_F6 = 64
    KEY_F7 = 65
    KEY_F8 = 66
    KEY_F9 = 67
    KEY_F10 = 68
    KEY_NUMLOCK = 69
    KEY_SCROLLLOCK = 70
    # Mouse buttons
    BTN_MOUSE = 0x110
    BTN_LEFT = 0x110
    BTN_RIGHT = 0x111
    BTN_MIDDLE = 0x112
    BTN_SIDE = 0x113
    BTN_EXTRA = 0x114

# Relative axes
class RelAxis(IntEnum):
    REL_X = 0x00
    REL_Y = 0x01
    REL_Z = 0x02
    REL_RX = 0x03
    REL_RY = 0x04
    REL_RZ = 0x05
    REL_HWHEEL = 0x06
    REL_DIAL = 0x07
    REL_WHEEL = 0x08
    REL_MISC = 0x09

# Absolute axes
class AbsAxis(IntEnum):
    ABS_X = 0x00
    ABS_Y = 0x01
    ABS_Z = 0x02
    ABS_RX = 0x03
    ABS_RY = 0x04
    ABS_RZ = 0x05
    ABS_THROTTLE = 0x06
    ABS_RUDDER = 0x07
    ABS_WHEEL = 0x08
    ABS_GAS = 0x09
    ABS_BRAKE = 0x0a
    ABS_HAT0X = 0x10
    ABS_HAT0Y = 0x11
    ABS_HAT1X = 0x12
    ABS_HAT1Y = 0x13
    ABS_HAT2X = 0x14
    ABS_HAT2Y = 0x15
    ABS_HAT3X = 0x16
    ABS_HAT3Y = 0x17
    ABS_PRESSURE = 0x18
    ABS_DISTANCE = 0x19
    ABS_TILT_X = 0x1a
    ABS_TILT_Y = 0x1b
    ABS_TOOL_WIDTH = 0x1c
    ABS_VOLUME = 0x20
    ABS_MISC = 0x28
    # Multi-touch
    ABS_MT_SLOT = 0x2f
    ABS_MT_TOUCH_MAJOR = 0x30
    ABS_MT_TOUCH_MINOR = 0x31
    ABS_MT_WIDTH_MAJOR = 0x32
    ABS_MT_WIDTH_MINOR = 0x33
    ABS_MT_ORIENTATION = 0x34
    ABS_MT_POSITION_X = 0x35
    ABS_MT_POSITION_Y = 0x36
    ABS_MT_TOOL_TYPE = 0x37
    ABS_MT_BLOB_ID = 0x38
    ABS_MT_TRACKING_ID = 0x39
    ABS_MT_PRESSURE = 0x3a
    ABS_MT_DISTANCE = 0x3b
    ABS_MT_TOOL_X = 0x3c
    ABS_MT_TOOL_Y = 0x3d


class InputEvent:
    """Input event structure"""
    FORMAT = 'llHHI'  # time_sec, time_usec, type, code, value
    SIZE = struct.calcsize(FORMAT)
    
    def __init__(self, tv_sec=0, tv_usec=0, type=0, code=0, value=0):
        self.tv_sec = tv_sec
        self.tv_usec = tv_usec
        self.type = type
        self.code = code
        self.value = value
        self.timestamp = tv_sec + tv_usec / 1000000.0
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'InputEvent':
        """Create event from raw bytes"""
        tv_sec, tv_usec, type, code, value = struct.unpack(cls.FORMAT, data)
        return cls(tv_sec, tv_usec, type, code, value)
    
    def to_bytes(self) -> bytes:
        """Convert event to bytes"""
        return struct.pack(self.FORMAT, self.tv_sec, self.tv_usec, 
                         self.type, self.code, self.value)
    
    def __repr__(self):
        return f"InputEvent(type={self.type}, code={self.code}, value={self.value})"


class InputDevice:
    """Base class for input devices"""
    
    def __init__(self, device_path: str):
        self.device_path = device_path
        self.device_name = os.path.basename(device_path)
        self.fd = None
        self._lock = threading.RLock()
        self._event_handlers = []
        self._event_thread = None
        self._running = False
        self.info = self._detect_device()
    
    def _detect_device(self) -> Dict[str, Any]:
        """Detect device type and capabilities"""
        info = {
            'path': self.device_path,
            'name': self.device_name,
            'type': 'unknown',
            'exists': False
        }
        
        if not os.path.exists(self.device_path):
            return info
        
        info['exists'] = True
        
        try:
            # Open device temporarily to get info
            fd = os.open(self.device_path, os.O_RDONLY | os.O_NONBLOCK)
            
            # Get device name
            name_buf = bytearray(256)
            try:
                fcntl.ioctl(fd, EVIOCGNAME(len(name_buf)), name_buf)
                info['device_name'] = name_buf.decode('utf-8').rstrip('\x00')
            except:
                pass
            
            # Get device ID
            id_buf = bytearray(8)
            try:
                fcntl.ioctl(fd, EVIOCGID, id_buf)
                bus, vendor, product, version = struct.unpack('HHHH', id_buf)
                info['id'] = {
                    'bus': bus,
                    'vendor': f"{vendor:04x}",
                    'product': f"{product:04x}",
                    'version': version
                }
            except:
                pass
            
            # Get capabilities
            capabilities = {}
            
            # Check event types
            evbit = bytearray(8)
            try:
                fcntl.ioctl(fd, EVIOCGBIT(0, len(evbit)), evbit)
                ev_types = struct.unpack('Q', evbit)[0]
                
                if ev_types & (1 << EventType.EV_KEY):
                    capabilities['keys'] = True
                    
                    # Check for keyboard vs mouse
                    keybit = bytearray(96)  # KEY_MAX/8
                    fcntl.ioctl(fd, EVIOCGBIT(EventType.EV_KEY, len(keybit)), keybit)
                    
                    # Check for alphabetic keys
                    has_alpha = any(keybit[i//8] & (1 << (i%8)) 
                                  for i in range(KeyCode.KEY_A, KeyCode.KEY_Z + 1))
                    
                    # Check for mouse buttons
                    has_mouse = any(keybit[i//8] & (1 << (i%8))
                                  for i in range(BTN_LEFT, BTN_EXTRA + 1))
                    
                    if has_alpha:
                        info['type'] = 'keyboard'
                    elif has_mouse:
                        info['type'] = 'mouse'
                
                if ev_types & (1 << EventType.EV_REL):
                    capabilities['relative'] = True
                    if info['type'] == 'unknown':
                        info['type'] = 'mouse'
                
                if ev_types & (1 << EventType.EV_ABS):
                    capabilities['absolute'] = True
                    if info['type'] == 'unknown':
                        info['type'] = 'touchpad'
                
                if ev_types & (1 << EventType.EV_LED):
                    capabilities['leds'] = True
                
                if ev_types & (1 << EventType.EV_FF):
                    capabilities['force_feedback'] = True
            except:
                pass
            
            info['capabilities'] = capabilities
            
            os.close(fd)
            
        except Exception as e:
            logger.error(f"Failed to detect device {self.device_path}: {e}")
        
        return info
    
    def open(self) -> bool:
        """Open device for reading"""
        with self._lock:
            if self.fd is not None:
                return True
            
            try:
                self.fd = os.open(self.device_path, os.O_RDONLY | os.O_NONBLOCK)
                return True
            except Exception as e:
                logger.error(f"Failed to open device {self.device_path}: {e}")
                return False
    
    def close(self):
        """Close device"""
        with self._lock:
            self.stop_event_loop()
            if self.fd is not None:
                os.close(self.fd)
                self.fd = None
    
    def grab(self, exclusive: bool = True) -> bool:
        """Grab device for exclusive access"""
        if not self.open():
            return False
        
        try:
            fcntl.ioctl(self.fd, EVIOCGRAB, 1 if exclusive else 0)
            return True
        except Exception as e:
            logger.error(f"Failed to grab device: {e}")
            return False
    
    def read_event(self) -> Optional[InputEvent]:
        """Read a single event from device"""
        if self.fd is None:
            return None
        
        try:
            data = os.read(self.fd, InputEvent.SIZE)
            if len(data) == InputEvent.SIZE:
                return InputEvent.from_bytes(data)
        except BlockingIOError:
            # No data available
            pass
        except Exception as e:
            logger.error(f"Failed to read event: {e}")
        
        return None
    
    def read_events(self, timeout: float = 0) -> List[InputEvent]:
        """Read all available events"""
        if self.fd is None:
            return []
        
        events = []
        
        # Use select for timeout
        if timeout > 0:
            readable, _, _ = select.select([self.fd], [], [], timeout)
            if not readable:
                return events
        
        # Read all available events
        while True:
            event = self.read_event()
            if event is None:
                break
            events.append(event)
        
        return events
    
    def write_event(self, event: InputEvent) -> bool:
        """Write an event to device (for synthetic events)"""
        if self.fd is None:
            return False
        
        try:
            # Need write access for this
            os.write(self.fd, event.to_bytes())
            return True
        except Exception as e:
            logger.error(f"Failed to write event: {e}")
            return False
    
    def add_event_handler(self, handler: Callable[[InputEvent], None]):
        """Add event handler callback"""
        self._event_handlers.append(handler)
    
    def remove_event_handler(self, handler: Callable[[InputEvent], None]):
        """Remove event handler callback"""
        if handler in self._event_handlers:
            self._event_handlers.remove(handler)
    
    def start_event_loop(self):
        """Start event reading thread"""
        if self._running:
            return
        
        if not self.open():
            return
        
        self._running = True
        self._event_thread = threading.Thread(target=self._event_loop, daemon=True)
        self._event_thread.start()
    
    def stop_event_loop(self):
        """Stop event reading thread"""
        self._running = False
        if self._event_thread:
            self._event_thread.join(timeout=1.0)
            self._event_thread = None
    
    def _event_loop(self):
        """Event reading loop"""
        while self._running:
            events = self.read_events(timeout=0.1)
            for event in events:
                for handler in self._event_handlers:
                    try:
                        handler(event)
                    except Exception as e:
                        logger.error(f"Event handler error: {e}")
    
    def get_led_states(self) -> Dict[str, bool]:
        """Get LED states (keyboard LEDs)"""
        if self.fd is None:
            return {}
        
        led_states = {}
        led_names = {
            0: 'num_lock',
            1: 'caps_lock',
            2: 'scroll_lock',
            3: 'compose',
            4: 'kana'
        }
        
        try:
            led_buf = bytearray(8)
            fcntl.ioctl(self.fd, EVIOCGLED(len(led_buf)), led_buf)
            led_bits = struct.unpack('Q', led_buf)[0]
            
            for bit, name in led_names.items():
                led_states[name] = bool(led_bits & (1 << bit))
                
        except Exception as e:
            logger.error(f"Failed to get LED states: {e}")
        
        return led_states
    
    def set_led(self, led_code: int, state: bool) -> bool:
        """Set LED state"""
        event = InputEvent(
            type=EventType.EV_LED,
            code=led_code,
            value=1 if state else 0
        )
        
        if self.write_event(event):
            # Send sync event
            sync = InputEvent(type=EventType.EV_SYN, code=SynEvent.SYN_REPORT)
            return self.write_event(sync)
        
        return False


class KeyboardDevice(InputDevice):
    """Keyboard device driver"""
    
    def __init__(self, device_path: str):
        super().__init__(device_path)
        self.key_states = {}  # Track key press states
        self.modifiers = {
            'shift': False,
            'ctrl': False,
            'alt': False,
            'meta': False
        }
    
    def process_event(self, event: InputEvent):
        """Process keyboard event"""
        if event.type == EventType.EV_KEY:
            # Update key state
            self.key_states[event.code] = bool(event.value)
            
            # Update modifier states
            if event.code in [KeyCode.KEY_LEFTSHIFT, KeyCode.KEY_RIGHTSHIFT]:
                self.modifiers['shift'] = bool(event.value)
            elif event.code in [KeyCode.KEY_LEFTCTRL, 97]:  # 97 = KEY_RIGHTCTRL
                self.modifiers['ctrl'] = bool(event.value)
            elif event.code in [KeyCode.KEY_LEFTALT, 100]:  # 100 = KEY_RIGHTALT
                self.modifiers['alt'] = bool(event.value)
            elif event.code in [125, 126]:  # KEY_LEFTMETA, KEY_RIGHTMETA
                self.modifiers['meta'] = bool(event.value)
    
    def get_key_state(self, key_code: int) -> bool:
        """Get current state of a key"""
        return self.key_states.get(key_code, False)
    
    def get_pressed_keys(self) -> List[int]:
        """Get list of currently pressed keys"""
        return [code for code, pressed in self.key_states.items() if pressed]


class MouseDevice(InputDevice):
    """Mouse device driver"""
    
    def __init__(self, device_path: str):
        super().__init__(device_path)
        self.position = [0, 0]  # Relative position tracking
        self.button_states = {}
        self.wheel_delta = 0
    
    def process_event(self, event: InputEvent):
        """Process mouse event"""
        if event.type == EventType.EV_REL:
            if event.code == RelAxis.REL_X:
                self.position[0] += event.value
            elif event.code == RelAxis.REL_Y:
                self.position[1] += event.value
            elif event.code == RelAxis.REL_WHEEL:
                self.wheel_delta = event.value
                
        elif event.type == EventType.EV_KEY:
            # Mouse button events
            if BTN_LEFT <= event.code <= BTN_EXTRA:
                self.button_states[event.code] = bool(event.value)
    
    def get_button_state(self, button_code: int) -> bool:
        """Get current state of a mouse button"""
        return self.button_states.get(button_code, False)


class TouchpadDevice(InputDevice):
    """Touchpad device driver"""
    
    def __init__(self, device_path: str):
        super().__init__(device_path)
        self.touches = {}  # Track multiple touches
        self.current_slot = 0
        self._get_abs_info()
    
    def _get_abs_info(self):
        """Get absolute axis information"""
        if not self.open():
            return
        
        self.abs_info = {}
        
        for axis in [AbsAxis.ABS_X, AbsAxis.ABS_Y, AbsAxis.ABS_MT_POSITION_X, 
                    AbsAxis.ABS_MT_POSITION_Y, AbsAxis.ABS_PRESSURE,
                    AbsAxis.ABS_MT_PRESSURE]:
            try:
                # struct input_absinfo
                buf = bytearray(24)
                fcntl.ioctl(self.fd, EVIOCGABS(axis), buf)
                value, minimum, maximum, fuzz, flat, resolution = struct.unpack('iiiiii', buf)
                
                self.abs_info[axis] = {
                    'value': value,
                    'min': minimum,
                    'max': maximum,
                    'fuzz': fuzz,
                    'flat': flat,
                    'resolution': resolution
                }
            except:
                pass
    
    def process_event(self, event: InputEvent):
        """Process touchpad event"""
        if event.type == EventType.EV_ABS:
            if event.code == AbsAxis.ABS_MT_SLOT:
                self.current_slot = event.value
                if self.current_slot not in self.touches:
                    self.touches[self.current_slot] = {}
                    
            elif event.code == AbsAxis.ABS_MT_TRACKING_ID:
                if event.value == -1:
                    # Touch lifted
                    if self.current_slot in self.touches:
                        del self.touches[self.current_slot]
                else:
                    # New touch
                    self.touches[self.current_slot] = {'id': event.value}
                    
            elif self.current_slot in self.touches:
                # Update touch properties
                if event.code == AbsAxis.ABS_MT_POSITION_X:
                    self.touches[self.current_slot]['x'] = event.value
                elif event.code == AbsAxis.ABS_MT_POSITION_Y:
                    self.touches[self.current_slot]['y'] = event.value
                elif event.code == AbsAxis.ABS_MT_PRESSURE:
                    self.touches[self.current_slot]['pressure'] = event.value
                elif event.code == AbsAxis.ABS_MT_TOUCH_MAJOR:
                    self.touches[self.current_slot]['major'] = event.value
                elif event.code == AbsAxis.ABS_MT_TOUCH_MINOR:
                    self.touches[self.current_slot]['minor'] = event.value
    
    def get_touches(self) -> Dict[int, Dict[str, Any]]:
        """Get current touch points"""
        return self.touches.copy()


class InputDriverManager:
    """Manages input device drivers"""
    
    def __init__(self):
        self.devices: Dict[str, InputDevice] = {}
        self._lock = threading.RLock()
        self._monitor_thread = None
        self._monitoring = False
        self._scan_devices()
    
    def _scan_devices(self):
        """Scan for input devices"""
        input_dir = "/dev/input"
        if not os.path.exists(input_dir):
            logger.warning("No /dev/input directory found")
            return
        
        try:
            for device_name in os.listdir(input_dir):
                if device_name.startswith('event'):
                    device_path = os.path.join(input_dir, device_name)
                    self._register_device(device_path)
        except Exception as e:
            logger.error(f"Failed to scan input devices: {e}")
    
    def _register_device(self, device_path: str):
        """Register an input device"""
        with self._lock:
            if device_path in self.devices:
                return
            
            try:
                # Create temporary device to detect type
                temp_device = InputDevice(device_path)
                device_type = temp_device.info.get('type', 'unknown')
                
                # Create appropriate driver
                if device_type == 'keyboard':
                    driver = KeyboardDevice(device_path)
                elif device_type == 'mouse':
                    driver = MouseDevice(device_path)
                elif device_type == 'touchpad':
                    driver = TouchpadDevice(device_path)
                else:
                    driver = temp_device
                
                self.devices[device_path] = driver
                logger.info(f"Registered input device: {device_path} (type: {device_type})")
                
            except Exception as e:
                logger.error(f"Failed to register device {device_path}: {e}")
    
    def get_device(self, device_path: str) -> Optional[InputDevice]:
        """Get an input device driver"""
        with self._lock:
            return self.devices.get(device_path)
    
    def list_devices(self) -> List[str]:
        """List all registered devices"""
        with self._lock:
            return list(self.devices.keys())
    
    def get_devices_by_type(self, device_type: str) -> List[InputDevice]:
        """Get all devices of a specific type"""
        devices = []
        with self._lock:
            for device in self.devices.values():
                if device.info.get('type') == device_type:
                    devices.append(device)
        return devices
    
    def get_device_info(self, device_path: str) -> Optional[Dict[str, Any]]:
        """Get comprehensive device information"""
        device = self.get_device(device_path)
        if not device:
            return None
        
        info = device.info.copy()
        
        # Add current state information
        if isinstance(device, KeyboardDevice):
            info['pressed_keys'] = device.get_pressed_keys()
            info['modifiers'] = device.modifiers.copy()
            info['led_states'] = device.get_led_states()
            
        elif isinstance(device, MouseDevice):
            info['position'] = device.position.copy()
            info['buttons'] = {
                'left': device.get_button_state(BTN_LEFT),
                'right': device.get_button_state(BTN_RIGHT),
                'middle': device.get_button_state(BTN_MIDDLE)
            }
            
        elif isinstance(device, TouchpadDevice):
            info['touches'] = device.get_touches()
            info['abs_info'] = device.abs_info.copy()
        
        return info
    
    def start_monitoring(self):
        """Start monitoring for device changes"""
        if self._monitoring:
            return
        
        self._monitoring = True
        self._monitor_thread = threading.Thread(target=self._monitor_devices, daemon=True)
        self._monitor_thread.start()
    
    def stop_monitoring(self):
        """Stop monitoring for device changes"""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=1.0)
            self._monitor_thread = None
    
    def _monitor_devices(self):
        """Monitor for device additions/removals"""
        known_devices = set(self.devices.keys())
        
        while self._monitoring:
            try:
                # Check for new devices
                input_dir = "/dev/input"
                if os.path.exists(input_dir):
                    current_devices = set()
                    
                    for device_name in os.listdir(input_dir):
                        if device_name.startswith('event'):
                            device_path = os.path.join(input_dir, device_name)
                            current_devices.add(device_path)
                            
                            if device_path not in known_devices:
                                # New device
                                self._register_device(device_path)
                                known_devices.add(device_path)
                    
                    # Check for removed devices
                    removed = known_devices - current_devices
                    for device_path in removed:
                        with self._lock:
                            if device_path in self.devices:
                                self.devices[device_path].close()
                                del self.devices[device_path]
                                logger.info(f"Removed input device: {device_path}")
                        known_devices.remove(device_path)
                
                time.sleep(1.0)  # Check every second
                
            except Exception as e:
                logger.error(f"Error monitoring devices: {e}")
                time.sleep(5.0)


# Global instance
_input_manager = None

def get_input_manager() -> InputDriverManager:
    """Get global input manager instance"""
    global _input_manager
    if _input_manager is None:
        _input_manager = InputDriverManager()
    return _input_manager