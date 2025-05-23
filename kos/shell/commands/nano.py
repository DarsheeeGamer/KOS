"""
Nano-like text editor implementation for KOS
"""
import os
import sys
import curses
from typing import Optional, List, Tuple
from datetime import datetime
from ...exceptions import KOSError, FileSystemError

class NanoEditor:
    """A simple nano-like text editor for KOS"""
    
    def __init__(self, fs, filename: str):
        """Initialize the editor with file system and filename"""
        self.fs = fs
        self.filename = filename
        self.lines: List[str] = []
        self.cursor_x = 0
        self.cursor_y = 0
        self.offset_x = 0
        self.offset_y = 0
        self.screen = None
        self.status_msg = ""
        self.modified = False
        self.quit = False
        self.help_visible = False
        self.help_text = [
            "^G Get Help    ^O Write Out   ^W Where Is    ^K Cut Text    ^J Justify     ^C Cur Pos",
            "^X Exit        ^R Read File    ^\\ Replace     ^U Uncut Text  ^T To Spell    ^_ Go To Line"
        ]
        
        # Try to load the file if it exists
        self.load_file()
    
    def load_file(self) -> None:
        """Load file contents if it exists"""
        try:
            if self.fs.exists(self.filename):
                content = self.fs.read_file(self.filename)
                self.lines = content.split('\n')
                if not self.lines:  # Empty file
                    self.lines = [""]
            else:
                self.lines = [""]
                self.modified = True
        except FileSystemError as e:
            raise KOSError(f"Error loading file: {e}")
    
    def save_file(self) -> None:
        """Save file contents"""
        try:
            content = '\n'.join(self.lines)
            self.fs.write_file(self.filename, content)
            self.modified = False
            self.status_msg = f'File "{os.path.basename(self.filename)}" written'
        except FileSystemError as e:
            raise KOSError(f"Error saving file: {e}")
    
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

def nano(fs, filename: str) -> None:
    """
    Nano-like text editor command
    
    Args:
        fs: File system instance
        filename: Name of the file to edit
    """
    try:
        editor = NanoEditor(fs, filename)
        editor.run()
    except Exception as e:
        raise KOSError(f"Editor error: {e}")
