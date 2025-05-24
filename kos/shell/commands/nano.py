"""
Nano-like text editor implementation for KOS

This module provides a feature-rich text editor for KOS with:
- Syntax highlighting for multiple languages
- Line numbering
- Auto-indentation
- Multiple buffer support
- Macro recording and playback
- Backup files
- Auto-save functionality
- Mouse support (when available)
"""
import os
import sys
import curses
import re
import time
import threading
import json
import signal
from typing import Optional, List, Tuple, Dict, Any, Union, Set
from datetime import datetime, timedelta
from pathlib import Path
from ...exceptions import KOSError, FileSystemError

# Syntax highlighting patterns for different file types
SYNTAX_PATTERNS = {
    'python': {
        'keywords': r'\b(and|as|assert|async|await|break|class|continue|def|del|elif|else|except|finally|for|from|global|if|import|in|is|lambda|nonlocal|not|or|pass|raise|return|try|while|with|yield)\b',
        'types': r'\b(bool|bytes|dict|float|int|list|object|set|str|tuple)\b',
        'strings': r'(["\'])(.*?)\1',
        'comments': r'#.*$',
        'functions': r'\bdef\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(',
        'classes': r'\bclass\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*[:\(]',
        'numbers': r'\b[0-9]+\b'
    },
    'javascript': {
        'keywords': r'\b(async|await|break|case|catch|class|const|continue|debugger|default|delete|do|else|export|extends|finally|for|function|if|import|in|instanceof|let|new|of|return|super|switch|this|throw|try|typeof|var|void|while|with|yield)\b',
        'types': r'\b(Array|Boolean|Date|Error|Function|JSON|Map|Math|Number|Object|Promise|Proxy|RegExp|Set|String|Symbol|WeakMap|WeakSet)\b',
        'strings': r'(["\'])(.*?)\1',
        'comments': r'(/\*.*?\*/|//.*$)',
        'functions': r'\bfunction\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(',
        'numbers': r'\b[0-9]+\b'
    },
    'html': {
        'tags': r'</?\s*([a-zA-Z0-9]+).*?>',
        'attributes': r'\s([a-zA-Z0-9_-]+)=',
        'strings': r'(["\'])(.*?)\1',
        'comments': r'<!--.*?-->'
    },
    'markdown': {
        'headers': r'^#+\s+(.*)$',
        'emphasis': r'(\*\*|__).*?\1',
        'italic': r'(\*|_).*?\1',
        'links': r'\[.*?\]\(.*?\)',
        'code': r'`.*?`',
        'lists': r'^\s*[-*+]\s+'
    },
    'json': {
        'keys': r'"([^"]+)"\s*:',
        'strings': r'"(.*?)"',
        'numbers': r'\b[0-9]+\b',
        'booleans': r'\b(true|false|null)\b'
    },
    'shell': {
        'keywords': r'\b(if|then|else|elif|fi|case|esac|for|while|until|do|done|in|function|select|time|coproc)\b',
        'commands': r'\b(cd|ls|mkdir|rm|cp|mv|cat|grep|find|echo|export|source|alias|unalias|pwd|sudo|su|chown|chmod|touch)\b',
        'variables': r'\$([a-zA-Z0-9_]+|\{[a-zA-Z0-9_]+\})',
        'strings': r'(["\'])(.*?)\1',
        'comments': r'#.*$'
    }
}

# Define color pairs for syntax highlighting
SYNTAX_COLORS = {
    'default': 0,
    'keywords': 1,
    'types': 2,
    'strings': 3,
    'comments': 4,
    'functions': 5,
    'classes': 6,
    'numbers': 7,
    'tags': 8,
    'attributes': 9,
    'headers': 10,
    'emphasis': 11,
    'italic': 12,
    'links': 13,
    'keys': 14,
    'booleans': 15,
    'variables': 16,
    'commands': 17,
    'statusbar': 18,
    'helpbar': 19,
    'linenumbers': 20,
    'selection': 21,
    'search_match': 22,
    'error_msg': 23
}

# File extension to syntax mapping
FILE_EXT_SYNTAX = {
    '.py': 'python',
    '.js': 'javascript',
    '.html': 'html',
    '.htm': 'html',
    '.md': 'markdown',
    '.json': 'json',
    '.sh': 'shell',
    '.bash': 'shell',
    '.css': 'css',
    '.xml': 'xml',
    '.txt': None  # No syntax highlighting for plain text
}

# Auto-save interval in seconds
AUTO_SAVE_INTERVAL = 60

# Keyboard shortcuts (Alt key combinations)
ALT_KEYS = {
    'n': 'toggle_line_numbers',
    'i': 'toggle_auto_indent',
    'b': 'toggle_backup',
    'a': 'toggle_auto_save',
    '<': 'prev_buffer',
    '>': 'next_buffer',
    's': 'save_file',
    'x': 'exit',
    'c': 'cancel',
    '/': 'search',
    '\\': 'replace',
    'g': 'goto_line',
    'r': 'read_file',
    'w': 'write_file',
    't': 'spell_check',
    'j': 'justify',
    'u': 'undo',
    'e': 'redo',
    'q': 'record_macro',
    'p': 'play_macro'
}

class Buffer:
    """Represents a file buffer in the editor"""
    
    def __init__(self, fs, filename: str):
        self.fs = fs
        self.filename = filename
        self.lines: List[str] = [""]
        self.cursor_x = 0
        self.cursor_y = 0
        self.offset_x = 0
        self.offset_y = 0
        self.modified = False
        self.syntax = self._detect_syntax()
        self.last_save_time = datetime.now()
        self.undo_stack: List[Dict[str, Any]] = []
        self.redo_stack: List[Dict[str, Any]] = []
        self.selection_start: Optional[Tuple[int, int]] = None
        self.selection_end: Optional[Tuple[int, int]] = None
        self.search_matches: List[Tuple[int, int, int]] = []  # (y, start_x, end_x)
        self.current_match_index = -1
        
        # Try to load the file if it exists
        self.load_file()
    
    def _detect_syntax(self) -> Optional[str]:
        """Detect syntax highlighting based on file extension"""
        _, ext = os.path.splitext(self.filename.lower())
        return FILE_EXT_SYNTAX.get(ext)
    
    def load_file(self) -> None:
        """Load file contents if it exists"""
        try:
            if self.fs.exists(self.filename):
                content = self.fs.read_file(self.filename)
                self.lines = content.split('\n')
                if not self.lines:  # Empty file
                    self.lines = [""]
                self.last_save_time = datetime.now()
            else:
                self.lines = [""]
                self.modified = True
        except FileSystemError as e:
            raise KOSError(f"Error loading file: {e}")
    
    def save_file(self, create_backup: bool = False) -> None:
        """Save file contents"""
        try:
            # Create backup if requested
            if create_backup and self.fs.exists(self.filename):
                backup_name = f"{self.filename}.bak"
                self.fs.copy_file(self.filename, backup_name)
                
            content = '\n'.join(self.lines)
            self.fs.write_file(self.filename, content)
            self.modified = False
            self.last_save_time = datetime.now()
        except FileSystemError as e:
            raise KOSError(f"Error saving file: {e}")
    
    def add_undo_state(self) -> None:
        """Add current state to undo stack"""
        state = {
            'lines': self.lines.copy(),
            'cursor_x': self.cursor_x,
            'cursor_y': self.cursor_y
        }
        self.undo_stack.append(state)
        self.redo_stack = []  # Clear redo stack on new edit
        
        # Limit undo stack size
        if len(self.undo_stack) > 100:
            self.undo_stack.pop(0)
    
    def undo(self) -> bool:
        """Undo last edit"""
        if not self.undo_stack:
            return False
            
        # Save current state to redo stack
        current_state = {
            'lines': self.lines.copy(),
            'cursor_x': self.cursor_x,
            'cursor_y': self.cursor_y
        }
        self.redo_stack.append(current_state)
        
        # Restore previous state
        state = self.undo_stack.pop()
        self.lines = state['lines']
        self.cursor_x = state['cursor_x']
        self.cursor_y = state['cursor_y']
        self.modified = True
        
        return True
    
    def redo(self) -> bool:
        """Redo previously undone edit"""
        if not self.redo_stack:
            return False
            
        # Save current state to undo stack
        current_state = {
            'lines': self.lines.copy(),
            'cursor_x': self.cursor_x,
            'cursor_y': self.cursor_y
        }
        self.undo_stack.append(current_state)
        
        # Restore next state
        state = self.redo_stack.pop()
        self.lines = state['lines']
        self.cursor_x = state['cursor_x']
        self.cursor_y = state['cursor_y']
        self.modified = True
        
        return True
    
    def search(self, search_str: str, case_sensitive: bool = False) -> bool:
        """Search for text in the buffer"""
        if not search_str:
            return False
            
        # Clear previous search results
        self.search_matches = []
        self.current_match_index = -1
        
        flags = 0 if case_sensitive else re.IGNORECASE
        
        # Find all matches
        for y, line in enumerate(self.lines):
            for match in re.finditer(re.escape(search_str), line, flags):
                self.search_matches.append((y, match.start(), match.end()))
        
        # Go to first match if any found
        if self.search_matches:
            self.current_match_index = 0
            match = self.search_matches[0]
            self.cursor_y = match[0]
            self.cursor_x = match[1]
            return True
            
        return False
    
    def find_next(self) -> bool:
        """Find next search match"""
        if not self.search_matches:
            return False
            
        # Move to next match
        self.current_match_index = (self.current_match_index + 1) % len(self.search_matches)
        match = self.search_matches[self.current_match_index]
        self.cursor_y = match[0]
        self.cursor_x = match[1]
        
        return True
    
    def find_prev(self) -> bool:
        """Find previous search match"""
        if not self.search_matches:
            return False
            
        # Move to previous match
        self.current_match_index = (self.current_match_index - 1) % len(self.search_matches)
        match = self.search_matches[self.current_match_index]
        self.cursor_y = match[0]
        self.cursor_x = match[1]
        
        return True
    
    def replace(self, search_str: str, replace_str: str, case_sensitive: bool = False, all_occurrences: bool = False) -> int:
        """Replace text in the buffer"""
        if not search_str:
            return 0
            
        flags = 0 if case_sensitive else re.IGNORECASE
        count = 0
        
        self.add_undo_state()
        
        if all_occurrences:
            # Replace all occurrences
            for y in range(len(self.lines)):
                new_line, n = re.subn(re.escape(search_str), replace_str, self.lines[y], flags=flags)
                if n > 0:
                    self.lines[y] = new_line
                    count += n
        elif self.search_matches and self.current_match_index >= 0:
            # Replace current match
            match = self.search_matches[self.current_match_index]
            y, start, end = match
            line = self.lines[y]
            self.lines[y] = line[:start] + replace_str + line[end:]
            count = 1
            
            # Update search matches
            self.search(search_str, case_sensitive)
        
        if count > 0:
            self.modified = True
            
        return count
    
    def goto_line(self, line_number: int) -> bool:
        """Go to specified line number"""
        if 1 <= line_number <= len(self.lines):
            self.cursor_y = line_number - 1
            self.cursor_x = 0
            return True
        return False
    
    def start_selection(self) -> None:
        """Start text selection at current cursor position"""
        self.selection_start = (self.cursor_y, self.cursor_x)
        self.selection_end = (self.cursor_y, self.cursor_x)
    
    def update_selection(self) -> None:
        """Update text selection end point to current cursor position"""
        if self.selection_start:
            self.selection_end = (self.cursor_y, self.cursor_x)
    
    def cancel_selection(self) -> None:
        """Cancel text selection"""
        self.selection_start = None
        self.selection_end = None
    
    def get_selected_text(self) -> str:
        """Get selected text"""
        if not self.selection_start or not self.selection_end:
            return ""
            
        start_y, start_x = self.selection_start
        end_y, end_x = self.selection_end
        
        # Ensure start comes before end
        if (start_y > end_y) or (start_y == end_y and start_x > end_x):
            start_y, start_x, end_y, end_x = end_y, end_x, start_y, start_x
        
        # Extract selected text
        if start_y == end_y:
            # Selection within a single line
            return self.lines[start_y][start_x:end_x]
        else:
            # Multi-line selection
            selected_lines = []
            # First line (partial)
            selected_lines.append(self.lines[start_y][start_x:])
            # Middle lines (complete)
            for y in range(start_y + 1, end_y):
                selected_lines.append(self.lines[y])
            # Last line (partial)
            selected_lines.append(self.lines[end_y][:end_x])
            return '\n'.join(selected_lines)
    
    def delete_selected_text(self) -> bool:
        """Delete selected text"""
        if not self.selection_start or not self.selection_end:
            return False
            
        self.add_undo_state()
        
        start_y, start_x = self.selection_start
        end_y, end_x = self.selection_end
        
        # Ensure start comes before end
        if (start_y > end_y) or (start_y == end_y and start_x > end_x):
            start_y, start_x, end_y, end_x = end_y, end_x, start_y, start_x
        
        # Delete selected text
        if start_y == end_y:
            # Selection within a single line
            line = self.lines[start_y]
            self.lines[start_y] = line[:start_x] + line[end_x:]
        else:
            # Multi-line selection
            # First line (partial)
            first_part = self.lines[start_y][:start_x]
            # Last line (partial)
            last_part = self.lines[end_y][end_x:]
            # Join first and last parts
            self.lines[start_y] = first_part + last_part
            # Remove middle lines
            for _ in range(end_y - start_y):
                self.lines.pop(start_y + 1)
        
        # Move cursor to start of selection
        self.cursor_y = start_y
        self.cursor_x = start_x
        
        self.selection_start = None
        self.selection_end = None
        self.modified = True
        
        return True
    
    def is_point_in_selection(self, y: int, x: int) -> bool:
        """Check if point is within selection"""
        if not self.selection_start or not self.selection_end:
            return False
            
        start_y, start_x = self.selection_start
        end_y, end_x = self.selection_end
        
        # Ensure start comes before end
        if (start_y > end_y) or (start_y == end_y and start_x > end_x):
            start_y, start_x, end_y, end_x = end_y, end_x, start_y, start_x
        
        # Check if point is within selection
        if start_y < y < end_y:
            return True
        elif start_y == y and end_y > y and x >= start_x:
            return True
        elif end_y == y and start_y < y and x < end_x:
            return True
        elif start_y == end_y and y == start_y and start_x <= x < end_x:
            return True
        
        return False
    
    def auto_indent(self, y: int) -> None:
        """Auto-indent line based on previous line"""
        if y <= 0 or y >= len(self.lines):
            return
            
        prev_line = self.lines[y - 1]
        indent = re.match(r'^(\s*)', prev_line).group(1)
        
        # Add extra indent after lines ending with :
        if prev_line.rstrip().endswith(':'):
            if '\t' in indent:
                indent += '\t'
            else:
                indent += '    '  # 4 spaces
        
        # Apply indent to current line
        current_line = self.lines[y].lstrip()
        self.lines[y] = indent + current_line
        
        # Move cursor after indent
        self.cursor_x = len(indent)

class NanoEditor:
    """An advanced nano-like text editor for KOS with syntax highlighting, line numbering, and more"""
    
    def __init__(self, fs, filename: str):
        """Initialize the editor with file system and filename"""
        self.fs = fs
        self.buffers: List[Buffer] = []
        self.current_buffer_index = 0
        self.screen = None
        self.status_msg = ""
        self.quit = False
        self.help_visible = False
        self.line_numbers_visible = True
        self.auto_indent_enabled = True
        self.create_backup = True
        self.auto_save_enabled = False
        self.auto_save_timer = None
        self.recording_macro = False
        self.macro: List[int] = []
        self.clipboard: List[str] = []
        self.search_str = ""
        self.replace_str = ""
        self.case_sensitive = False
        
        # Help text with enhanced commands
        self.help_text = [
            "^G Get Help    ^O Write Out   ^W Where Is    ^K Cut Text    ^J Justify     ^C Cur Pos",
            "^X Exit        ^R Read File   ^\\ Replace     ^U Uncut Text  ^T To Spell    ^_ Go To Line",
            "Alt+N LineNum  Alt+I AutoIndent Alt+B Backup  Alt+A AutoSave  Alt+< PrevBuf  Alt+> NextBuf",
            "Alt+U Undo     Alt+E Redo     Alt+Q RecMacro Alt+P PlayMacro Alt+S Save     Alt+X Exit"
        ]
        
        # Add the initial buffer
        self.add_buffer(filename)
        
        # Start auto-save timer if enabled
        if self.auto_save_enabled:
            self._start_auto_save_timer()
    
    def add_buffer(self, filename: str) -> None:
        """Add a new buffer"""
        self.buffers.append(Buffer(self.fs, filename))
        self.current_buffer_index = len(self.buffers) - 1
    
    def current_buffer(self) -> Buffer:
        """Get the current buffer"""
        return self.buffers[self.current_buffer_index]
    
    def next_buffer(self) -> None:
        """Switch to the next buffer"""
        if len(self.buffers) > 1:
            self.current_buffer_index = (self.current_buffer_index + 1) % len(self.buffers)
    
    def prev_buffer(self) -> None:
        """Switch to the previous buffer"""
        if len(self.buffers) > 1:
            self.current_buffer_index = (self.current_buffer_index - 1) % len(self.buffers)
    
    def close_current_buffer(self) -> bool:
        """Close the current buffer"""
        if len(self.buffers) <= 1:
            return False
            
        self.buffers.pop(self.current_buffer_index)
        if self.current_buffer_index >= len(self.buffers):
            self.current_buffer_index = len(self.buffers) - 1
        return True
    
    def _start_auto_save_timer(self) -> None:
        """Start auto-save timer"""
        if self.auto_save_timer:
            self.auto_save_timer.cancel()
            
        def auto_save():
            buffer = self.current_buffer()
            if buffer.modified and (datetime.now() - buffer.last_save_time).seconds >= AUTO_SAVE_INTERVAL:
                try:
                    buffer.save_file(self.create_backup)
                    self.status_msg = f"Auto-saved: {os.path.basename(buffer.filename)}"
                except Exception as e:
                    self.status_msg = f"Auto-save failed: {str(e)}"
            
            # Schedule next auto-save
            if self.auto_save_enabled and not self.quit:
                self.auto_save_timer = threading.Timer(AUTO_SAVE_INTERVAL, auto_save)
                self.auto_save_timer.daemon = True
                self.auto_save_timer.start()
        
        self.auto_save_timer = threading.Timer(AUTO_SAVE_INTERVAL, auto_save)
        self.auto_save_timer.daemon = True
        self.auto_save_timer.start()
    
    def _stop_auto_save_timer(self) -> None:
        """Stop auto-save timer"""
        if self.auto_save_timer:
            self.auto_save_timer.cancel()
            self.auto_save_timer = None
    
    def run(self) -> None:
        """Run the editor"""
        try:
            curses.wrapper(self._main_loop)
        except Exception as e:
            raise KOSError(f"Editor error: {e}")
        finally:
            self._stop_auto_save_timer()
    
    def _main_loop(self, stdscr) -> None:
        """Main editor loop"""
        self.screen = stdscr
        curses.curs_set(1)  # Show cursor
        self._init_colors()
        
        # Enable mouse events if available
        if hasattr(curses, 'mousemask'):
            curses.mousemask(curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION)
        
        while not self.quit:
            self._update_display()
            self._process_input()
    
    def _init_colors(self) -> None:
        """Initialize color pairs for syntax highlighting"""
        if curses.has_colors():
            curses.start_color()
            curses.use_default_colors()
            
            # Base colors
            curses.init_pair(SYNTAX_COLORS['statusbar'], curses.COLOR_BLACK, curses.COLOR_WHITE)  # Status bar
            curses.init_pair(SYNTAX_COLORS['helpbar'], curses.COLOR_WHITE, curses.COLOR_BLUE)    # Help bar
            curses.init_pair(SYNTAX_COLORS['linenumbers'], curses.COLOR_CYAN, -1)               # Line numbers
            curses.init_pair(SYNTAX_COLORS['selection'], curses.COLOR_BLACK, curses.COLOR_CYAN)  # Selection
            curses.init_pair(SYNTAX_COLORS['search_match'], curses.COLOR_BLACK, curses.COLOR_YELLOW) # Search match
            curses.init_pair(SYNTAX_COLORS['error_msg'], curses.COLOR_RED, -1)                  # Error messages
            
            # Syntax highlighting colors
            curses.init_pair(SYNTAX_COLORS['keywords'], curses.COLOR_BLUE, -1)
            curses.init_pair(SYNTAX_COLORS['types'], curses.COLOR_GREEN, -1)
            curses.init_pair(SYNTAX_COLORS['strings'], curses.COLOR_MAGENTA, -1)
            curses.init_pair(SYNTAX_COLORS['comments'], curses.COLOR_RED, -1)
            curses.init_pair(SYNTAX_COLORS['functions'], curses.COLOR_CYAN, -1)
            curses.init_pair(SYNTAX_COLORS['classes'], curses.COLOR_GREEN, -1)
            curses.init_pair(SYNTAX_COLORS['numbers'], curses.COLOR_MAGENTA, -1)
            curses.init_pair(SYNTAX_COLORS['tags'], curses.COLOR_GREEN, -1)
            curses.init_pair(SYNTAX_COLORS['attributes'], curses.COLOR_CYAN, -1)
            curses.init_pair(SYNTAX_COLORS['headers'], curses.COLOR_GREEN, -1)
            curses.init_pair(SYNTAX_COLORS['emphasis'], curses.COLOR_BLUE, -1)
            curses.init_pair(SYNTAX_COLORS['italic'], curses.COLOR_CYAN, -1)
            curses.init_pair(SYNTAX_COLORS['links'], curses.COLOR_BLUE, -1)
            curses.init_pair(SYNTAX_COLORS['keys'], curses.COLOR_CYAN, -1)
            curses.init_pair(SYNTAX_COLORS['booleans'], curses.COLOR_YELLOW, -1)
            curses.init_pair(SYNTAX_COLORS['variables'], curses.COLOR_YELLOW, -1)
            curses.init_pair(SYNTAX_COLORS['commands'], curses.COLOR_GREEN, -1)
    
    def _update_display(self) -> None:
        """Update the display"""
        if not self.screen:
            return
            
        self.screen.clear()
        height, width = self.screen.getmaxyx()
        buffer = self.current_buffer()
        
        # Calculate line number margin width if line numbers are visible
        line_num_width = 0
        if self.line_numbers_visible:
            line_num_width = len(str(len(buffer.lines))) + 2
        
        # Calculate content width
        content_width = width - line_num_width
        
        # Adjust viewport based on cursor position
        self._adjust_viewport(height, width)
        
        # Display file contents with syntax highlighting
        for i in range(min(len(buffer.lines) - buffer.offset_y, height - 2)):
            line_idx = i + buffer.offset_y
            line = buffer.lines[line_idx]
            
            # Display line numbers if enabled
            if self.line_numbers_visible:
                line_num = f"{line_idx + 1:{line_num_width-1}} "
                self.screen.addstr(i, 0, line_num, curses.color_pair(SYNTAX_COLORS['linenumbers']))
            
            # Handle line wrapping and horizontal scrolling
            if buffer.offset_x < len(line):
                display_line = line[buffer.offset_x:buffer.offset_x + content_width]
            else:
                display_line = ""
            
            # Apply syntax highlighting if available for the file type
            if buffer.syntax and display_line:
                self._highlight_line(i, line_num_width, display_line, buffer.syntax, line_idx)
            else:
                # Display without syntax highlighting
                try:
                    # Check if character is in a selection
                    for x, char in enumerate(display_line):
                        pos_x = x + buffer.offset_x
                        attr = curses.A_NORMAL
                        
                        # Highlight selected text
                        if buffer.is_point_in_selection(line_idx, pos_x):
                            attr = curses.color_pair(SYNTAX_COLORS['selection'])
                        # Highlight search matches
                        elif buffer.search_matches and any(match[0] == line_idx and match[1] <= pos_x < match[2] for match in buffer.search_matches):
                            attr = curses.color_pair(SYNTAX_COLORS['search_match'])
                            
                        self.screen.addch(i, x + line_num_width, char, attr)
                except curses.error:
                    pass  # Ignore errors at the bottom right corner
        
        # Status bar
        self._display_status_bar(height, width)
        
        # Help bar
        if self.help_visible and height > 6:
            for idx, help_line in enumerate(self.help_text):
                if idx < 4:  # Only show 4 lines of help
                    help_text = help_line[:width-1]
                    self.screen.addstr(height - 6 + idx, 0, help_text, curses.color_pair(SYNTAX_COLORS['helpbar']))
        
        # Position cursor
        buffer = self.current_buffer()
        cursor_y = min(buffer.cursor_y - buffer.offset_y, height - 3)
        cursor_x = min(buffer.cursor_x - buffer.offset_x, width - 1)
        
        if self.line_numbers_visible:
            cursor_x += line_num_width
        
        try:
            self.screen.move(cursor_y, cursor_x)
        except curses.error:
            pass
        
        # Status message
        if self.status_msg:
            msg = self.status_msg[:width-1]
            self.screen.addstr(height - 1, 0, msg)
            self.status_msg = ""
        
        self.screen.refresh()
    
    def _display_status_bar(self, height: int, width: int) -> None:
        """Display status bar with file info and editor status"""
        buffer = self.current_buffer()
        status = f" {os.path.basename(buffer.filename)}"
        status += f" | Line {buffer.cursor_y + 1}/{len(buffer.lines)}"
        status += f" | Col {buffer.cursor_x + 1}"
        
        # Add indicators for enabled features
        if self.line_numbers_visible:
            status += " | Line#"
        if self.auto_indent_enabled:
            status += " | AutoIn"
        if self.create_backup:
            status += " | Backup"
        if self.auto_save_enabled:
            status += " | AutoSave"
        if buffer.modified:
            status += " | [Modified]"
        
        # Add buffer info if multiple buffers
        if len(self.buffers) > 1:
            status += f" | Buf {self.current_buffer_index + 1}/{len(self.buffers)}"
        
        # Add recording indicator
        if self.recording_macro:
            status += " | [Recording]"
            
        # Add syntax info
        if buffer.syntax:
            status += f" | {buffer.syntax.capitalize()}"
            
        # Pad to fill width
        status += ' ' * (width - len(status) - 1)
        
        # Display status bar
        self.screen.addstr(height - 2, 0, status, curses.color_pair(SYNTAX_COLORS['statusbar']))
    
    def _highlight_line(self, y: int, x_offset: int, line: str, syntax: str, line_idx: int) -> None:
        """Apply syntax highlighting to a line"""
        if not syntax in SYNTAX_PATTERNS:
            return
            
        buffer = self.current_buffer()
        patterns = SYNTAX_PATTERNS[syntax]
        
        # Create a list of character attributes
        attrs = [curses.A_NORMAL] * len(line)
        
        # Apply syntax highlighting
        for pattern_type, pattern in patterns.items():
            if pattern_type in SYNTAX_COLORS:
                color_pair = curses.color_pair(SYNTAX_COLORS[pattern_type])
                for match in re.finditer(pattern, line):
                    start, end = match.span()
                    for i in range(start, end):
                        if i < len(attrs):
                            attrs[i] = color_pair
        
        # Apply selection and search match highlighting (overrides syntax highlighting)
        for i in range(len(line)):
            pos_x = i + buffer.offset_x
            
            # Selection highlighting takes precedence
            if buffer.is_point_in_selection(line_idx, pos_x):
                attrs[i] = curses.color_pair(SYNTAX_COLORS['selection'])
            # Then search matches
            elif buffer.search_matches and any(match[0] == line_idx and match[1] <= pos_x < match[2] for match in buffer.search_matches):
                attrs[i] = curses.color_pair(SYNTAX_COLORS['search_match'])
        
        # Display line with highlighting
        try:
            for i, char in enumerate(line):
                self.screen.addch(y, x_offset + i, char, attrs[i])
        except curses.error:
            pass  # Ignore errors at the bottom right corner
    
    def _adjust_viewport(self, height: int, width: int) -> None:
        """Adjust viewport to keep cursor in view"""
        buffer = self.current_buffer()
        
        # Calculate the content width (accounting for line numbers)
        line_num_width = 0
        if self.line_numbers_visible:
            line_num_width = len(str(len(buffer.lines))) + 2
        content_width = width - line_num_width
        
        # Adjust vertical position
        if buffer.cursor_y < buffer.offset_y:
            buffer.offset_y = buffer.cursor_y
        elif buffer.cursor_y >= buffer.offset_y + height - 2:
            buffer.offset_y = buffer.cursor_y - (height - 3)
        
        # Adjust horizontal position
        line_length = len(buffer.lines[buffer.cursor_y]) if buffer.cursor_y < len(buffer.lines) else 0
        if buffer.cursor_x < buffer.offset_x:
            buffer.offset_x = max(0, buffer.cursor_x - 5)  # Scroll left with some margin
        elif buffer.cursor_x >= buffer.offset_x + content_width - 1:
            buffer.offset_x = buffer.cursor_x - content_width + 6  # Scroll right with some margin
        
        # Ensure offset_x doesn't go beyond line length
        if buffer.offset_x > line_length:
            buffer.offset_x = max(0, line_length - 1)
    
    def _process_input(self) -> None:
        """Process user input"""
        if not self.screen:
            return
            
        buffer = self.current_buffer()
        
        try:
            key = self.screen.getch()
        except KeyboardInterrupt:
            self.quit = True
            return
        
        # If recording a macro, store the key
        if self.recording_macro and key not in (27, curses.KEY_RESIZE):  # Ignore ESC and resize events
            self.macro.append(key)
        
        # Handle Alt key combinations (ESC followed by another key)
        if key == 27:  # ESC key
            # Wait briefly for another key
            self.screen.nodelay(True)
            second_key = self.screen.getch()
            self.screen.nodelay(False)
            
            if second_key != -1:  # Got a second key, handle Alt+key combination
                char = chr(second_key) if 32 <= second_key <= 126 else None
                if char and char in ALT_KEYS:
                    method_name = ALT_KEYS[char]
                    method = getattr(self, f"_handle_{method_name}", None)
                    if method:
                        method()
                    return
        
        # Handle special keys
        if key == curses.KEY_UP:
            self._move_cursor(0, -1)
        elif key == curses.KEY_DOWN:
            self._move_cursor(0, 1)
        elif key == curses.KEY_LEFT:
            self._move_cursor(-1, 0)
        elif key == curses.KEY_RIGHT:
            self._move_cursor(1, 0)
        elif key == curses.KEY_HOME:
            self._move_to_start_of_line()
        elif key == curses.KEY_END:
            self._move_to_end_of_line()
        elif key == curses.KEY_PPAGE:  # Page Up
            self._move_page(-1)
        elif key == curses.KEY_NPAGE:  # Page Down
            self._move_page(1)
        elif key == 10:  # Enter
            self._insert_newline()
        elif key == 127 or key == 8 or key == curses.KEY_BACKSPACE:  # Backspace
            self._backspace()
        elif key == 9:  # Tab
            self._insert_tab()
        elif key == 11:  # ^K - Cut line
            self._cut_line()
        elif key == 21:  # ^U - Paste
            self._paste()
        elif key == 23:  # ^W - Search
            self._search()
        elif key == 6:  # ^F - Find next
            self._find_next()
        elif key == 18:  # ^R - Read file
            self._read_file()
        elif key == 3:  # ^C - Show cursor position
            self._show_cursor_position()
        elif key == 15:  # ^O - Save
            self._save_file()
        elif key == 24:  # ^X - Exit
            self._exit()
        elif key == 7:  # ^G - Toggle help
            self.help_visible = not self.help_visible
        elif key == 31:  # ^_ - Go to line
            self._goto_line()
        elif key == 10:  # Enter
            self._insert_newline()
        elif key == 12:  # ^L - Refresh screen
            self.screen.clear()
            self.screen.refresh()
        elif key == 20:  # ^T - Spell check (stub)
            self.status_msg = "Spell check not implemented"
        elif key == 10:  # ^J - Justify (stub)
            self.status_msg = "Justify not implemented"
        elif key == 92:  # \ - Replace
            self._replace()
        elif 32 <= key <= 126:  # Printable characters
            self._insert_char(chr(key))
        elif key == curses.KEY_MOUSE and hasattr(curses, 'getmouse'):
            self._handle_mouse()
        elif key == curses.KEY_RESIZE:
            # Terminal resized
            pass
    
    def _move_cursor(self, dx: int, dy: int) -> None:
        """Move cursor by dx, dy"""
        buffer = self.current_buffer()
        new_x = max(0, buffer.cursor_x + dx)
        new_y = max(0, min(len(buffer.lines) - 1, buffer.cursor_y + dy))
        
        # Adjust x position for the new line length
        max_x = len(buffer.lines[new_y]) if new_y < len(buffer.lines) else 0
        new_x = min(new_x, max_x)
        
        buffer.cursor_x, buffer.cursor_y = new_x, new_y
        
        # Update selection if active
        if buffer.selection_start:
            buffer.update_selection()
    
    def _move_to_start_of_line(self) -> None:
        """Move cursor to the start of the current line"""
        buffer = self.current_buffer()
        buffer.cursor_x = 0
        
        if buffer.selection_start:
            buffer.update_selection()
    
    def _move_to_end_of_line(self) -> None:
        """Move cursor to the end of the current line"""
        buffer = self.current_buffer()
        if buffer.cursor_y < len(buffer.lines):
            buffer.cursor_x = len(buffer.lines[buffer.cursor_y])
        
        if buffer.selection_start:
            buffer.update_selection()
    
    def _move_page(self, direction: int) -> None:
        """Move cursor by one page up or down"""
        if not self.screen:
            return
            
        height, _ = self.screen.getmaxyx()
        page_size = max(1, height - 3)
        self._move_cursor(0, direction * page_size)
    
    def _insert_char(self, char: str) -> None:
        """Insert a character at the cursor position"""
        buffer = self.current_buffer()
        
        # Delete selected text if any
        if buffer.selection_start:
            buffer.delete_selected_text()
        
        if not buffer.lines:
            buffer.lines = [""]
        
        buffer.add_undo_state()
        
        line = buffer.lines[buffer.cursor_y]
        new_line = line[:buffer.cursor_x] + char + line[buffer.cursor_x:]
        buffer.lines[buffer.cursor_y] = new_line
        buffer.cursor_x += 1
        buffer.modified = True
    
    def _insert_tab(self) -> None:
        """Insert a tab or spaces at the cursor position"""
        self._insert_char('\t')  # Simple implementation, could also insert spaces
    
    def _insert_newline(self) -> None:
        """Insert a newline at the cursor position"""
        buffer = self.current_buffer()
        
        # Delete selected text if any
        if buffer.selection_start:
            buffer.delete_selected_text()
        
        buffer.add_undo_state()
        
        if not buffer.lines:
            buffer.lines = ["", ""]
            buffer.cursor_y = 1
            buffer.cursor_x = 0
        else:
            current_line = buffer.lines[buffer.cursor_y]
            line_start = current_line[:buffer.cursor_x]
            line_end = current_line[buffer.cursor_x:]
            
            buffer.lines[buffer.cursor_y] = line_start
            buffer.lines.insert(buffer.cursor_y + 1, line_end)
            buffer.cursor_y += 1
            buffer.cursor_x = 0
            
            # Apply auto-indent if enabled
            if self.auto_indent_enabled:
                buffer.auto_indent(buffer.cursor_y)
        
        buffer.modified = True
    
    def _backspace(self) -> None:
        """Handle backspace key"""
        buffer = self.current_buffer()
        
        # Delete selected text if any
        if buffer.selection_start:
            buffer.delete_selected_text()
            return
        
        buffer.add_undo_state()
        
        if buffer.cursor_x > 0:
            # Delete character before cursor
            line = buffer.lines[buffer.cursor_y]
            buffer.lines[buffer.cursor_y] = line[:buffer.cursor_x-1] + line[buffer.cursor_x:]
            buffer.cursor_x -= 1
            buffer.modified = True
        elif buffer.cursor_y > 0:
            # Join with previous line
            prev_line_len = len(buffer.lines[buffer.cursor_y-1])
            buffer.lines[buffer.cursor_y-1] += buffer.lines.pop(buffer.cursor_y)
            buffer.cursor_y -= 1
            buffer.cursor_x = prev_line_len
            buffer.modified = True
    
    def _cut_line(self) -> None:
        """Cut the current line to clipboard"""
        buffer = self.current_buffer()
        
        if buffer.selection_start:
            # Cut selected text
            text = buffer.get_selected_text()
            if text:
                self.clipboard = [text]
                buffer.delete_selected_text()
                buffer.modified = True
            return
        
        if len(buffer.lines) > 0:
            buffer.add_undo_state()
            
            # Add line to clipboard
            self.clipboard = [buffer.lines[buffer.cursor_y]]
            
            # Remove line
            if len(buffer.lines) > 1:
                buffer.lines.pop(buffer.cursor_y)
                if buffer.cursor_y >= len(buffer.lines):
                    buffer.cursor_y = max(0, len(buffer.lines) - 1)
                buffer.cursor_x = 0
            else:
                buffer.lines[0] = ""
                buffer.cursor_x = 0
                
            buffer.modified = True
    
    def _paste(self) -> None:
        """Paste clipboard contents"""
        if not self.clipboard:
            return
            
        buffer = self.current_buffer()
        buffer.add_undo_state()
        
        # Delete selected text if any
        if buffer.selection_start:
            buffer.delete_selected_text()
        
        # Insert clipboard text
        text = '\n'.join(self.clipboard)
        lines = text.split('\n')
        
        if len(lines) == 1:
            # Single line paste
            line = buffer.lines[buffer.cursor_y]
            buffer.lines[buffer.cursor_y] = line[:buffer.cursor_x] + lines[0] + line[buffer.cursor_x:]
            buffer.cursor_x += len(lines[0])
        else:
            # Multi-line paste
            current_line = buffer.lines[buffer.cursor_y]
            prefix = current_line[:buffer.cursor_x]
            suffix = current_line[buffer.cursor_x:]
            
            # First line joins with current line prefix
            buffer.lines[buffer.cursor_y] = prefix + lines[0]
            
            # Middle lines inserted as-is
            for i, line in enumerate(lines[1:-1], 1):
                buffer.lines.insert(buffer.cursor_y + i, line)
                
            # Last line joins with current line suffix
            buffer.lines.insert(buffer.cursor_y + len(lines) - 1, lines[-1] + suffix)
            
            # Move cursor to end of pasted text
            buffer.cursor_y += len(lines) - 1
            buffer.cursor_x = len(lines[-1])
        
        buffer.modified = True
    
    def _search(self) -> None:
        """Search for text"""
        if not self.screen:
            return
            
        buffer = self.current_buffer()
        height, width = self.screen.getmaxyx()
        
        # Display search prompt
        self.screen.addstr(height-1, 0, "Search: ")
        self.screen.refresh()
        
        # Get search string
        curses.echo()
        try:
            search_str = self.screen.getstr(height-1, 8, width-10).decode('utf-8')
        except Exception:
            search_str = ""
        curses.noecho()
        
        if search_str:
            self.search_str = search_str
            if not buffer.search(search_str, self.case_sensitive):
                self.status_msg = f"Not found: {search_str}"
    
    def _find_next(self) -> None:
        """Find next occurrence of search string"""
        buffer = self.current_buffer()
        if not hasattr(self, 'search_str') or not self.search_str:
            self._search()
            return
            
        if not buffer.find_next():
            if buffer.search_matches:
                self.status_msg = "Search wrapped"
            else:
                self.status_msg = f"Not found: {self.search_str}"
    
    def _replace(self) -> None:
        """Replace text"""
        if not self.screen:
            return
            
        buffer = self.current_buffer()
        height, width = self.screen.getmaxyx()
        
        # Display search prompt
        self.screen.addstr(height-1, 0, "Search: ")
        self.screen.refresh()
        
        # Get search string
        curses.echo()
        try:
            search_str = self.screen.getstr(height-1, 8, width-10).decode('utf-8')
        except Exception:
            search_str = ""
            
        if not search_str:
            curses.noecho()
            return
            
        # Display replace prompt
        self.screen.addstr(height-1, 0, "Replace with: ")
        self.screen.clrtoeol()
        self.screen.refresh()
        
        # Get replacement string
        try:
            replace_str = self.screen.getstr(height-1, 14, width-16).decode('utf-8')
        except Exception:
            replace_str = ""
        curses.noecho()
        
        # Search for the first occurrence
        if buffer.search(search_str, self.case_sensitive):
            # Ask whether to replace all or confirm each replacement
            self.screen.addstr(height-1, 0, "Replace all? (Y/N/C for cancel): ")
            self.screen.clrtoeol()
            self.screen.refresh()
            
            choice = chr(self.screen.getch()).upper()
            if choice == 'Y':
                # Replace all occurrences
                count = buffer.replace(search_str, replace_str, self.case_sensitive, True)
                self.status_msg = f"Replaced {count} occurrences"
            elif choice == 'N':
                # Replace one by one
                self._replace_one_by_one(search_str, replace_str)
        else:
            self.status_msg = f"Not found: {search_str}"
    
    def _replace_one_by_one(self, search_str: str, replace_str: str) -> None:
        """Replace occurrences one by one with confirmation"""
        if not self.screen:
            return
            
        buffer = self.current_buffer()
        height, width = self.screen.getmaxyx()
        count = 0
        
        # First search already performed in _replace
        while buffer.search_matches:
            # Ask for confirmation for each match
            self.screen.addstr(height-1, 0, "Replace this instance? (Y/N/A for all/C for cancel): ")
            self.screen.clrtoeol()
            self.screen.refresh()
            
            # Update display to show the current search match
            self._update_display()
            
            choice = chr(self.screen.getch()).upper()
            if choice == 'Y':
                # Replace current occurrence
                buffer.replace(search_str, replace_str, self.case_sensitive, False)
                count += 1
                buffer.find_next()
            elif choice == 'N':
                # Skip this occurrence
                buffer.find_next()
            elif choice == 'A':
                # Replace all remaining occurrences
                remain_count = buffer.replace(search_str, replace_str, self.case_sensitive, True)
                count += remain_count
                break
            elif choice == 'C':
                # Cancel replacement
                break
                
            if not buffer.search_matches or buffer.current_match_index == 0:
                # Wrapped around or no more matches
                break
                
        self.status_msg = f"Replaced {count} occurrences"
    
    def _show_cursor_position(self) -> None:
        """Show cursor position in status bar"""
        buffer = self.current_buffer()
        self.status_msg = f"Line {buffer.cursor_y + 1}, Col {buffer.cursor_x + 1}"
    
    def _save_file(self) -> None:
        """Save file contents"""
        buffer = self.current_buffer()
        try:
            buffer.save_file(self.create_backup)
            self.status_msg = f'File "{os.path.basename(buffer.filename)}" written'
        except Exception as e:
            self.status_msg = f"Error saving file: {e}"
    
    def _exit(self) -> None:
        """Exit the editor"""
        buffer = self.current_buffer()
        if buffer.modified:
            if not self.screen:
                return
                
            height, width = self.screen.getmaxyx()
            self.screen.addstr(height-1, 0, "Save modified buffer? (Y/N/C): ")
            self.screen.clrtoeol()
            self.screen.refresh()
            
            choice = chr(self.screen.getch()).upper()
            if choice == 'Y':
                try:
                    buffer.save_file(self.create_backup)
                    self.quit = True
                except Exception as e:
                    self.status_msg = f"Error saving file: {e}"
            elif choice == 'N':
                self.quit = True
            # C or any other key cancels exit
        else:
            self.quit = True
    
    def _goto_line(self) -> None:
        """Go to specified line number"""
        if not self.screen:
            return
            
        buffer = self.current_buffer()
        height, width = self.screen.getmaxyx()
        
        # Display prompt
        self.screen.addstr(height-1, 0, "Go to line: ")
        self.screen.clrtoeol()
        self.screen.refresh()
        
        # Get line number
        curses.echo()
        try:
            line_str = self.screen.getstr(height-1, 11, 10).decode('utf-8')
            line_num = int(line_str)
        except (ValueError, Exception):
            line_num = 0
        curses.noecho()
        
        if line_num > 0:
            if buffer.goto_line(line_num):
                self.status_msg = f"Moved to line {line_num}"
            else:
                self.status_msg = f"Line number {line_num} out of range"
    
    def _read_file(self) -> None:
        """Read a file into the current buffer"""
        if not self.screen:
            return
            
        height, width = self.screen.getmaxyx()
        
        # Display prompt
        self.screen.addstr(height-1, 0, "File to insert: ")
        self.screen.clrtoeol()
        self.screen.refresh()
        
        # Get filename
        curses.echo()
        try:
            filename = self.screen.getstr(height-1, 15, width-17).decode('utf-8')
        except Exception:
            filename = ""
        curses.noecho()
        
        if filename:
            try:
                # Check if file exists
                if not self.fs.exists(filename):
                    self.status_msg = f"File not found: {filename}"
                    return
                    
                # Read file contents
                content = self.fs.read_file(filename)
                lines = content.split('\n')
                
                # Insert contents at cursor position
                buffer = self.current_buffer()
                buffer.add_undo_state()
                
                # Delete selected text if any
                if buffer.selection_start:
                    buffer.delete_selected_text()
                
                if len(lines) == 1:
                    # Single line insert
                    line = buffer.lines[buffer.cursor_y]
                    buffer.lines[buffer.cursor_y] = line[:buffer.cursor_x] + lines[0] + line[buffer.cursor_x:]
                    buffer.cursor_x += len(lines[0])
                else:
                    # Multi-line insert
                    current_line = buffer.lines[buffer.cursor_y]
                    prefix = current_line[:buffer.cursor_x]
                    suffix = current_line[buffer.cursor_x:]
                    
                    # First line joins with current line prefix
                    buffer.lines[buffer.cursor_y] = prefix + lines[0]
                    
                    # Middle lines inserted as-is
                    for i, line in enumerate(lines[1:-1], 1):
                        buffer.lines.insert(buffer.cursor_y + i, line)
                        
                    # Last line joins with current line suffix
                    buffer.lines.insert(buffer.cursor_y + len(lines) - 1, lines[-1] + suffix)
                    
                    # Move cursor to end of inserted text
                    buffer.cursor_y += len(lines) - 1
                    buffer.cursor_x = len(lines[-1])
                
                buffer.modified = True
                self.status_msg = f"Read {len(lines)} lines from {filename}"
                
            except Exception as e:
                self.status_msg = f"Error reading file: {e}"
    
    def _handle_mouse(self) -> None:
        """Handle mouse events"""
        if not hasattr(curses, 'getmouse'):
            return
            
        try:
            _, mx, my, _, button_state = curses.getmouse()
            height, width = self.screen.getmaxyx()
            buffer = self.current_buffer()
            
            # Calculate line number margin width if line numbers are visible
            line_num_width = 0
            if self.line_numbers_visible:
                line_num_width = len(str(len(buffer.lines))) + 2
            
            # Ignore clicks outside text area
            if my >= height - 2 or mx < line_num_width:
                return
                
            # Convert screen coordinates to buffer coordinates
            new_y = my + buffer.offset_y
            new_x = mx - line_num_width + buffer.offset_x
            
            # Ensure coordinates are valid
            if new_y < len(buffer.lines):
                buffer.cursor_y = new_y
                line_length = len(buffer.lines[new_y])
                buffer.cursor_x = min(new_x, line_length)
                
                # Handle selection
                if button_state & curses.BUTTON1_PRESSED:
                    # Start selection
                    buffer.start_selection()
                elif button_state & curses.BUTTON1_RELEASED:
                    # Update selection
                    if buffer.selection_start:
                        buffer.update_selection()
        except Exception:
            pass  # Ignore mouse errors
    
    # Alt key handler methods
    def _handle_toggle_line_numbers(self) -> None:
        """Toggle line numbers display"""
        self.line_numbers_visible = not self.line_numbers_visible
        self.status_msg = f"Line numbers {'enabled' if self.line_numbers_visible else 'disabled'}"
    
    def _handle_toggle_auto_indent(self) -> None:
        """Toggle auto-indentation"""
        self.auto_indent_enabled = not self.auto_indent_enabled
        self.status_msg = f"Auto-indent {'enabled' if self.auto_indent_enabled else 'disabled'}"
    
    def _handle_toggle_backup(self) -> None:
        """Toggle backup file creation"""
        self.create_backup = not self.create_backup
        self.status_msg = f"Backup files {'enabled' if self.create_backup else 'disabled'}"
    
    def _handle_toggle_auto_save(self) -> None:
        """Toggle auto-save"""
        self.auto_save_enabled = not self.auto_save_enabled
        
        if self.auto_save_enabled:
            self._start_auto_save_timer()
            self.status_msg = f"Auto-save enabled ({AUTO_SAVE_INTERVAL}s)"
        else:
            self._stop_auto_save_timer()
            self.status_msg = "Auto-save disabled"
    
    def _handle_prev_buffer(self) -> None:
        """Switch to previous buffer"""
        self.prev_buffer()
        buffer = self.current_buffer()
        self.status_msg = f"Buffer: {os.path.basename(buffer.filename)}"
    
    def _handle_next_buffer(self) -> None:
        """Switch to next buffer"""
        self.next_buffer()
        buffer = self.current_buffer()
        self.status_msg = f"Buffer: {os.path.basename(buffer.filename)}"
    
    def _handle_save_file(self) -> None:
        """Save current file"""
        self._save_file()
    
    def _handle_exit(self) -> None:
        """Exit the editor"""
        self._exit()
    
    def _handle_undo(self) -> None:
        """Undo last edit"""
        buffer = self.current_buffer()
        if buffer.undo():
            self.status_msg = "Undo successful"
        else:
            self.status_msg = "Nothing to undo"
    
    def _handle_redo(self) -> None:
        """Redo previously undone edit"""
        buffer = self.current_buffer()
        if buffer.redo():
            self.status_msg = "Redo successful"
        else:
            self.status_msg = "Nothing to redo"
    
    def _handle_record_macro(self) -> None:
        """Toggle macro recording"""
        if self.recording_macro:
            self.recording_macro = False
            self.status_msg = "Macro recording stopped"
        else:
            self.recording_macro = True
            self.macro = []
            self.status_msg = "Macro recording started"
    
    def _handle_play_macro(self) -> None:
        """Play recorded macro"""
        if not self.macro:
            self.status_msg = "No macro recorded"
            return
            
        # Temporarily disable macro recording during playback
        was_recording = self.recording_macro
        self.recording_macro = False
        
        # Play back each key in the macro
        for key in self.macro:
            # Inject the key into the input system
            # For simplicity, we'll just call the appropriate methods directly
            self._process_macro_key(key)
        
        # Restore recording state
        self.recording_macro = was_recording
        self.status_msg = f"Played macro ({len(self.macro)} keys)"
    
    def _process_macro_key(self, key: int) -> None:
        """Process a key from a macro"""
        # Handle basic editing keys
        if key == curses.KEY_UP:
            self._move_cursor(0, -1)
        elif key == curses.KEY_DOWN:
            self._move_cursor(0, 1)
        elif key == curses.KEY_LEFT:
            self._move_cursor(-1, 0)
        elif key == curses.KEY_RIGHT:
            self._move_cursor(1, 0)
        elif key == 10:  # Enter
            self._insert_newline()
        elif key == 127 or key == 8:  # Backspace
            self._backspace()
        elif 32 <= key <= 126:  # Printable characters
            self._insert_char(chr(key))
        # Add more key handlers as needed
    
    def run(self) -> None:
        """Run the editor"""
        try:
            curses.wrapper(self._main_loop)
        except Exception as e:
            raise KOSError(f"Editor error: {e}")
    
    def _main_loop(self, stdscr) -> None:
        """Main editor loop"""
        self.screen = stdscr
        curses.curs_set(1)  # Show cursor
        self._init_colors()
        
        while not self.quit:
            self._update_display()
            self._process_input()
    
    def _init_colors(self) -> None:
        """Initialize color pairs"""
        if curses.has_colors():
            curses.start_color()
            curses.use_default_colors()
            curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_WHITE)  # Status bar
            curses.init_pair(2, curses.COLOR_WHITE, curses.COLOR_BLUE)   # Help bar
    
    def _update_display(self) -> None:
        """Update the display"""
        if not self.screen:
            return
            
        self.screen.clear()
        height, width = self.screen.getmaxyx()
        
        # Adjust viewport based on cursor position
        self._adjust_viewport(height, width)
        
        # Display file contents
        for i in range(min(len(self.lines) - self.offset_y, height - 2)):
            line = self.lines[i + self.offset_y]
            # Handle line wrapping and horizontal scrolling
            if self.offset_x < len(line):
                display_line = line[self.offset_x:self.offset_x + width]
            else:
                display_line = ""
            
            try:
                self.screen.addstr(i, 0, display_line)
            except curses.error:
                pass  # Ignore errors at the bottom right corner
        
        # Status bar
        status = f' {os.path.basename(self.filename)}' + (' [Modified]' if self.modified else '')
        status += ' ' * (width - len(status) - 1)
        self.screen.addstr(height - 2, 0, status, curses.color_pair(1))
        
        # Help bar
        if self.help_visible and height > 3:
            help_line1 = self.help_text[0][:width-1]
            help_line2 = self.help_text[1][:width-1]
            self.screen.addstr(height - 4, 0, help_line1, curses.color_pair(2))
            self.screen.addstr(height - 3, 0, help_line2, curses.color_pair(2))
        
        # Position cursor
        cursor_y = min(self.cursor_y - self.offset_y, height - 3)
        cursor_x = min(self.cursor_x - self.offset_x, width - 1)
        
        try:
            self.screen.move(cursor_y, cursor_x)
        except curses.error:
            pass
        
        # Status message
        if self.status_msg:
            msg = self.status_msg[:width-1]
            self.screen.addstr(height - 1, 0, msg)
            self.status_msg = ""
        
        self.screen.refresh()
    
    def _adjust_viewport(self, height: int, width: int) -> None:
        """Adjust viewport to keep cursor in view"""
        # Adjust vertical position
        if self.cursor_y < self.offset_y:
            self.offset_y = self.cursor_y
        elif self.cursor_y >= self.offset_y + height - 2:
            self.offset_y = self.cursor_y - (height - 3)
        
        # Adjust horizontal position
        line_length = len(self.lines[self.cursor_y]) if self.cursor_y < len(self.lines) else 0
        if self.cursor_x < self.offset_x:
            self.offset_x = max(0, self.cursor_x - 10)  # Scroll left with some margin
        elif self.cursor_x >= self.offset_x + width - 1:
            self.offset_x = self.cursor_x - width + 11  # Scroll right with some margin
        
        # Ensure offset_x doesn't go beyond line length
        if self.offset_x > line_length:
            self.offset_x = max(0, line_length - 1)
    
    def _process_input(self) -> None:
        """Process user input"""
        if not self.screen:
            return
            
        try:
            key = self.screen.getch()
        except KeyboardInterrupt:
            self.quit = True
            return
        
        # Handle special keys
        if key == curses.KEY_UP:
            self._move_cursor(0, -1)
        elif key == curses.KEY_DOWN:
            self._move_cursor(0, 1)
        elif key == curses.KEY_LEFT:
            self._move_cursor(-1, 0)
        elif key == curses.KEY_RIGHT:
            self._move_cursor(1, 0)
        elif key == curses.KEY_HOME:
            self.cursor_x = 0
        elif key == curses.KEY_END:
            if self.cursor_y < len(self.lines):
                self.cursor_x = len(self.lines[self.cursor_y])
        elif key == curses.KEY_PPAGE:  # Page Up
            self._move_cursor(0, -10)
        elif key == curses.KEY_NPAGE:  # Page Down
            self._move_cursor(0, 10)
        elif key == 10:  # Enter
            self._insert_newline()
        elif key == 127 or key == 8:  # Backspace
            self._backspace()
        elif key == 21:  # ^U - Delete line
            self._delete_line()
        elif key == 23:  # ^W - Search
            self._search()
        elif key == 6:  # ^F - Find next
            self._find_next()
        elif key == 3:  # ^C - Show cursor position
            self._show_cursor_position()
        elif key == 15:  # ^O - Save
            self.save_file()
        elif key == 24:  # ^X - Exit
            if self.modified:
                self.status_msg = "Save modified buffer? (Y/N/C)"
                self.screen.refresh()
                response = chr(self.screen.getch()).upper()
                if response == 'Y':
                    self.save_file()
                    self.quit = True
                elif response == 'N':
                    self.quit = True
            else:
                self.quit = True
        elif key == 7:  # ^G - Toggle help
            self.help_visible = not self.help_visible
        elif 32 <= key <= 126:  # Printable characters
            self._insert_char(chr(key))
    
    def _move_cursor(self, dx: int, dy: int) -> None:
        """Move cursor by dx, dy"""
        new_x = max(0, self.cursor_x + dx)
        new_y = max(0, min(len(self.lines) - 1, self.cursor_y + dy))
        
        # Adjust x position for the new line length
        max_x = len(self.lines[new_y]) if new_y < len(self.lines) else 0
        new_x = min(new_x, max_x)
        
        self.cursor_x, self.cursor_y = new_x, new_y
    
    def _insert_char(self, char: str) -> None:
        """Insert a character at the cursor position"""
        if not self.lines:
            self.lines = [""]
        
        line = self.lines[self.cursor_y]
        new_line = line[:self.cursor_x] + char + line[self.cursor_x:]
        self.lines[self.cursor_y] = new_line
        self.cursor_x += 1
        self.modified = True
    
    def _insert_newline(self) -> None:
        """Insert a newline at the cursor position"""
        if not self.lines:
            self.lines = ["", ""]
            self.cursor_y = 1
            self.cursor_x = 0
        else:
            current_line = self.lines[self.cursor_y]
            line_start = current_line[:self.cursor_x]
            line_end = current_line[self.cursor_x:]
            
            self.lines[self.cursor_y] = line_start
            self.lines.insert(self.cursor_y + 1, line_end)
            self.cursor_y += 1
            self.cursor_x = 0
        
        self.modified = True
    
    def _backspace(self) -> None:
        """Handle backspace key"""
        if self.cursor_x > 0:
            # Delete character before cursor
            line = self.lines[self.cursor_y]
            self.lines[self.cursor_y] = line[:self.cursor_x-1] + line[self.cursor_x:]
            self.cursor_x -= 1
            self.modified = True
        elif self.cursor_y > 0:
            # Join with previous line
            prev_line_len = len(self.lines[self.cursor_y-1])
            self.lines[self.cursor_y-1] += self.lines.pop(self.cursor_y)
            self.cursor_y -= 1
            self.cursor_x = prev_line_len
            self.modified = True
    
    def _delete_line(self) -> None:
        """Delete the current line"""
        if len(self.lines) > 1:
            self.lines.pop(self.cursor_y)
            if self.cursor_y >= len(self.lines):
                self.cursor_y = max(0, len(self.lines) - 1)
            self.cursor_x = 0
            self.modified = True
    
    def _search(self) -> None:
        """Search for text"""
        if not self.screen:
            return
            
        height, width = self.screen.getmaxyx()
        self.screen.addstr(height-1, 0, "Search: ")
        self.screen.refresh()
        
        curses.echo()
        try:
            search_str = self.screen.getstr(height-1, 8).decode('utf-8')
        except Exception:
            search_str = ""
        curses.noecho()
        
        if search_str:
            self.search_str = search_str
            self._find_next()
    
    def _find_next(self) -> None:
        """Find next occurrence of search string"""
        if not hasattr(self, 'search_str') or not self.search_str:
            return
            
        start_y = self.cursor_y
        start_x = self.cursor_x
        
        # Search from current position to end
        for y in range(start_y, len(self.lines)):
            line = self.lines[y]
            start = start_x + 1 if y == start_y else 0
            pos = line.find(self.search_str, start)
            if pos != -1:
                self.cursor_y = y
                self.cursor_x = pos
                return
            start_x = -1  # For subsequent lines, search from start
        
        # If not found, wrap around to start
        for y in range(0, start_y + 1):
            line = self.lines[y]
            end = len(line) if y < start_y else start_x
            pos = line.find(self.search_str, 0, end)
            if pos != -1:
                self.cursor_y = y
                self.cursor_x = pos
                self.status_msg = "Search wrapped"
                return
        
        self.status_msg = f"Not found: {self.search_str}"
    
    def _show_cursor_position(self) -> None:
        """Show cursor position in status bar"""
        self.status_msg = f"Line {self.cursor_y + 1}, Col {self.cursor_x + 1}"

def nano(fs, filename: str, **kwargs) -> None:
    """
    Nano-like text editor command
    
    Args:
        fs: File system instance
        filename: Name of the file to edit
        **kwargs: Optional keyword arguments:
            linenumbers (bool): Show line numbers (default: True)
            autoindent (bool): Enable auto-indentation (default: True)
            backup (bool): Create backup files (default: True)
            autosave (bool): Enable auto-save (default: False)
            syntax (bool): Enable syntax highlighting (default: True)
    
    The editor provides the following keyboard shortcuts:
    
    Navigation:
        Arrow keys - Move cursor
        Home/End - Go to beginning/end of line
        Page Up/Down - Scroll up/down one page
        ^C - Show cursor position
        ^_ - Go to specific line number
    
    File Operations:
        ^O - Save file
        ^R - Read file into current buffer
        ^X - Exit (prompts to save if file modified)
    
    Editing:
        ^K - Cut current line to clipboard
        ^U - Paste clipboard contents
        ^J - Justify paragraph
        ^T - Spell check
        Delete/Backspace - Delete character
    
    Search:
        ^W - Search for text
        ^F - Find next occurrence
        ^\ - Search and replace
    
    Advanced Features (Alt key combinations):
        Alt+N - Toggle line numbers
        Alt+I - Toggle auto-indentation
        Alt+B - Toggle backup files
        Alt+A - Toggle auto-save
        Alt+< - Previous buffer
        Alt+> - Next buffer
        Alt+U - Undo
        Alt+E - Redo
        Alt+Q - Record macro
        Alt+P - Play macro
    """
    try:
        editor = NanoEditor(fs, filename)
        
        # Set editor options from keyword arguments
        if 'linenumbers' in kwargs:
            editor.line_numbers_visible = kwargs['linenumbers']
        if 'autoindent' in kwargs:
            editor.auto_indent_enabled = kwargs['autoindent']
        if 'backup' in kwargs:
            editor.create_backup = kwargs['backup']
        if 'autosave' in kwargs:
            editor.auto_save_enabled = kwargs['autosave']
            if editor.auto_save_enabled:
                editor._start_auto_save_timer()
        
        editor.run()
    except Exception as e:
        raise KOSError(f"Editor error: {e}")
