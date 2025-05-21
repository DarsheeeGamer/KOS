"""
Documentation system for KOS
"""
import logging
from typing import Dict, Optional

logger = logging.getLogger('KOS.docs')

class ManualSystem:
    """Manages command documentation and manual pages"""
    def __init__(self):
        self.manual_pages: Dict[str, str] = {}

    def get_manual(self, command: str) -> Optional[str]:
        """Get manual page for a command"""
        return self.manual_pages.get(command)

    def add_manual(self, command: str, content: str) -> None:
        """Add or update a manual page"""
        self.manual_pages[command] = content

    def list_commands(self) -> list:
        """List all commands with manual pages"""
        return sorted(self.manual_pages.keys())
