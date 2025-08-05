"""
KOS Swap Manager - Virtual memory swap space management
"""

import threading
import os
from typing import Dict, List, Optional, Any

class SwapManager:
    """
    Swap space manager for virtual memory
    """
    
    def __init__(self, swap_size: int = 1024 * 1024 * 1024):  # 1GB default
        self.swap_size = swap_size
        self.swap_used = 0
        self.swap_file = None
        self.swap_pages = {}  # page_id -> swap_offset
        self.free_slots = []
        self.next_slot = 0
        self.lock = threading.Lock()
        
    def enable_swap(self, swap_file_path: str = "/tmp/kos_swap") -> bool:
        """Enable swap to file"""
        try:
            # Create swap file (in real system would be a dedicated partition)
            self.swap_file = open(swap_file_path, "w+b")
            self.swap_file.truncate(self.swap_size)
            
            # Initialize free slots
            page_size = 4096
            num_slots = self.swap_size // page_size
            self.free_slots = list(range(num_slots))
            
            return True
        except Exception:
            return False
            
    def disable_swap(self) -> bool:
        """Disable swap"""
        with self.lock:
            if self.swap_file:
                self.swap_file.close()
                self.swap_file = None
                self.swap_pages.clear()
                self.free_slots.clear()
                self.swap_used = 0
                return True
        return False
        
    def swap_out_page(self, page_id: int, page_data: bytes) -> bool:
        """Swap out a page to storage"""
        with self.lock:
            if not self.swap_file or not self.free_slots:
                return False
                
            slot = self.free_slots.pop(0)
            offset = slot * 4096
            
            try:
                self.swap_file.seek(offset)
                self.swap_file.write(page_data)
                self.swap_file.flush()
                
                self.swap_pages[page_id] = offset
                self.swap_used += 4096
                return True
            except Exception:
                self.free_slots.insert(0, slot)  # Return slot on error
                return False
                
    def swap_in_page(self, page_id: int) -> Optional[bytes]:
        """Swap in a page from storage"""
        with self.lock:
            offset = self.swap_pages.get(page_id)
            if offset is None or not self.swap_file:
                return None
                
            try:
                self.swap_file.seek(offset)
                page_data = self.swap_file.read(4096)
                
                # Free the swap slot
                slot = offset // 4096
                self.free_slots.append(slot)
                del self.swap_pages[page_id]
                self.swap_used -= 4096
                
                return page_data
            except Exception:
                return None
                
    def get_swap_info(self) -> Dict[str, Any]:
        """Get swap space information"""
        with self.lock:
            return {
                'total': self.swap_size,
                'used': self.swap_used,
                'free': self.swap_size - self.swap_used,
                'pages_swapped': len(self.swap_pages),
                'free_slots': len(self.free_slots)
            }