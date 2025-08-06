"""
Text editor for KOS Shell - nano-like interface
"""

import types
import curses
import os
from typing import List, Optional

class TextEditor:
    """Simple text editor for VFS files"""
    
    def __init__(self, vfs, filepath: str, content: str = ""):
        self.vfs = vfs
        self.filepath = filepath
        self.lines = content.split('\n') if content else ['']
        self.cursor_x = 0
        self.cursor_y = 0
        self.scroll_y = 0
        self.modified = False
        self.status_message = ""
        
    def run(self, stdscr):
        """Run the editor with curses"""
        curses.curs_set(1)  # Show cursor
        stdscr.keypad(True)
        
        while True:
            self.display(stdscr)
            key = stdscr.getch()
            
            if not self.handle_key(key):
                break
        
        return self.modified
    
    def display(self, stdscr):
        """Display the editor interface"""
        height, width = stdscr.getmaxyx()
        
        # Clear screen
        stdscr.clear()
        
        # Draw title bar
        title = f" KOS Editor - {self.filepath} {'[Modified]' if self.modified else ''}"
        stdscr.attron(curses.A_REVERSE)
        stdscr.addstr(0, 0, title.ljust(width)[:width-1])
        stdscr.attroff(curses.A_REVERSE)
        
        # Draw text content
        text_height = height - 3  # Title, status, command bars
        for i in range(text_height):
            line_num = i + self.scroll_y
            if line_num < len(self.lines):
                line = self.lines[line_num][:width-1]
                try:
                    stdscr.addstr(i + 1, 0, line)
                except:
                    pass
        
        # Draw status bar
        status = f" Line {self.cursor_y + 1}/{len(self.lines)} Col {self.cursor_x + 1}"
        stdscr.attron(curses.A_REVERSE)
        try:
            stdscr.addstr(height - 2, 0, status.ljust(width)[:width-1])
        except:
            pass
        stdscr.attroff(curses.A_REVERSE)
        
        # Draw command bar
        commands = " ^X Exit  ^O Save  ^K Cut  ^U Paste"
        try:
            stdscr.addstr(height - 1, 0, commands[:width-1])
        except:
            pass
        
        # Show status message if any
        if self.status_message:
            try:
                stdscr.addstr(height - 1, width - len(self.status_message) - 1, 
                            self.status_message)
            except:
                pass
            self.status_message = ""
        
        # Position cursor
        screen_y = self.cursor_y - self.scroll_y + 1
        if 0 <= screen_y < height - 2:
            try:
                stdscr.move(screen_y, min(self.cursor_x, width - 1))
            except:
                pass
        
        stdscr.refresh()
    
    def handle_key(self, key):
        """Handle keyboard input"""
        # Navigation
        if key == curses.KEY_UP:
            self.move_cursor(0, -1)
        elif key == curses.KEY_DOWN:
            self.move_cursor(0, 1)
        elif key == curses.KEY_LEFT:
            self.move_cursor(-1, 0)
        elif key == curses.KEY_RIGHT:
            self.move_cursor(1, 0)
        elif key == curses.KEY_HOME:
            self.cursor_x = 0
        elif key == curses.KEY_END:
            self.cursor_x = len(self.lines[self.cursor_y])
        
        # Page navigation
        elif key == curses.KEY_PPAGE:  # Page Up
            self.move_cursor(0, -10)
        elif key == curses.KEY_NPAGE:  # Page Down
            self.move_cursor(0, 10)
        
        # Text editing
        elif key == ord('\n') or key == 13:  # Enter
            self.insert_newline()
        elif key == curses.KEY_BACKSPACE or key == 127:
            self.backspace()
        elif key == curses.KEY_DC:  # Delete
            self.delete()
        elif 32 <= key <= 126:  # Printable characters
            self.insert_char(chr(key))
        
        # Commands
        elif key == 24:  # Ctrl+X - Exit
            if self.modified:
                # Ask for confirmation (simplified)
                return False
            return False
        elif key == 15:  # Ctrl+O - Save
            self.save_file()
        elif key == 11:  # Ctrl+K - Cut line
            self.cut_line()
        
        return True
    
    def move_cursor(self, dx, dy):
        """Move cursor with bounds checking"""
        # Vertical movement
        self.cursor_y = max(0, min(len(self.lines) - 1, self.cursor_y + dy))
        
        # Horizontal movement
        if dx != 0:
            self.cursor_x = max(0, min(len(self.lines[self.cursor_y]), 
                                      self.cursor_x + dx))
        else:
            # When moving vertically, adjust x to line length
            self.cursor_x = min(self.cursor_x, len(self.lines[self.cursor_y]))
        
        # Adjust scroll
        height = 20  # Approximate height
        if self.cursor_y < self.scroll_y:
            self.scroll_y = self.cursor_y
        elif self.cursor_y >= self.scroll_y + height - 3:
            self.scroll_y = self.cursor_y - height + 4
    
    def insert_char(self, char):
        """Insert a character at cursor position"""
        line = self.lines[self.cursor_y]
        self.lines[self.cursor_y] = (line[:self.cursor_x] + char + 
                                     line[self.cursor_x:])
        self.cursor_x += 1
        self.modified = True
    
    def insert_newline(self):
        """Insert a new line at cursor position"""
        line = self.lines[self.cursor_y]
        self.lines[self.cursor_y] = line[:self.cursor_x]
        self.lines.insert(self.cursor_y + 1, line[self.cursor_x:])
        self.cursor_y += 1
        self.cursor_x = 0
        self.modified = True
    
    def backspace(self):
        """Delete character before cursor"""
        if self.cursor_x > 0:
            line = self.lines[self.cursor_y]
            self.lines[self.cursor_y] = (line[:self.cursor_x-1] + 
                                        line[self.cursor_x:])
            self.cursor_x -= 1
            self.modified = True
        elif self.cursor_y > 0:
            # Join with previous line
            prev_line = self.lines[self.cursor_y - 1]
            curr_line = self.lines[self.cursor_y]
            self.cursor_x = len(prev_line)
            self.lines[self.cursor_y - 1] = prev_line + curr_line
            del self.lines[self.cursor_y]
            self.cursor_y -= 1
            self.modified = True
    
    def delete(self):
        """Delete character at cursor"""
        line = self.lines[self.cursor_y]
        if self.cursor_x < len(line):
            self.lines[self.cursor_y] = (line[:self.cursor_x] + 
                                        line[self.cursor_x+1:])
            self.modified = True
        elif self.cursor_y < len(self.lines) - 1:
            # Join with next line
            self.lines[self.cursor_y] += self.lines[self.cursor_y + 1]
            del self.lines[self.cursor_y + 1]
            self.modified = True
    
    def cut_line(self):
        """Cut current line"""
        if len(self.lines) > 1:
            del self.lines[self.cursor_y]
            if self.cursor_y >= len(self.lines):
                self.cursor_y = len(self.lines) - 1
            self.cursor_x = 0
            self.modified = True
        else:
            self.lines[0] = ""
            self.cursor_x = 0
            self.modified = True
    
    def save_file(self):
        """Save file to VFS"""
        try:
            content = '\n'.join(self.lines)
            if self.vfs:
                with self.vfs.open(self.filepath, 'w') as f:
                    f.write(content.encode())
            self.modified = False
            self.status_message = "Saved!"
        except Exception as e:
            self.status_message = f"Error: {str(e)[:20]}"
    
    def get_content(self):
        """Get the current content"""
        return '\n'.join(self.lines)


def register_commands(shell):
    """Register editor commands with shell"""
    
    def do_edit(self, arg):
        """Edit a file
        Usage: edit <filename>"""
        if not arg:
            print("Usage: edit <filename>")
            return
        
        if not self.vfs:
            print("VFS not available")
            return
        
        filepath = arg.strip()
        
        # Resolve relative path
        if not filepath.startswith('/'):
            filepath = os.path.join(self.cwd, filepath)
            filepath = os.path.normpath(filepath)
        
        # Load existing content if file exists
        content = ""
        if self.vfs.exists(filepath):
            if self.vfs.isdir(filepath):
                print(f"edit: {filepath} is a directory")
                return
            try:
                with self.vfs.open(filepath, 'r') as f:
                    content = f.read().decode()
            except Exception as e:
                print(f"Error reading file: {e}")
                return
        
        # Run editor
        try:
            editor = TextEditor(self.vfs, filepath, content)
            modified = curses.wrapper(editor.run)
            
            if modified:
                print(f"File saved: {filepath}")
            
        except Exception as e:
            print(f"Editor error: {e}")
    
    def do_nano(self, arg):
        """Alias for edit command"""
        self.do_edit(arg)
    
    def do_vi(self, arg):
        """Alias for edit command"""
        self.do_edit(arg)
    
    # Simple non-interactive editor for quick edits
    def do_echo(self, arg):
        """Echo text or write to file
        Usage: 
            echo <text>           - Print text
            echo <text> > file    - Write text to file
            echo <text> >> file   - Append text to file"""
        
        if not arg:
            print()
            return
        
        # Check for redirection
        if ' > ' in arg:
            parts = arg.split(' > ', 1)
            text = parts[0]
            filepath = parts[1].strip()
            mode = 'w'
        elif ' >> ' in arg:
            parts = arg.split(' >> ', 1)
            text = parts[0]
            filepath = parts[1].strip()
            mode = 'a'
        else:
            # Just echo to screen
            print(arg)
            return
        
        # Remove quotes if present
        if (text.startswith('"') and text.endswith('"')) or \
           (text.startswith("'") and text.endswith("'")):
            text = text[1:-1]
        
        # Write to file
        if not self.vfs:
            print("VFS not available")
            return
        
        # Resolve path
        if not filepath.startswith('/'):
            filepath = os.path.join(self.cwd, filepath)
            filepath = os.path.normpath(filepath)
        
        try:
            # Create parent directories if needed
            parent = os.path.dirname(filepath)
            if parent and parent != '/' and not self.vfs.exists(parent):
                self.vfs.mkdir(parent)
            
            # Write content
            with self.vfs.open(filepath, mode) as f:
                f.write((text + '\n').encode())
            
        except Exception as e:
            print(f"echo: {e}")
    
    # Register commands using MethodType
    shell.do_edit = types.MethodType(do_edit, shell)
    shell.do_nano = types.MethodType(do_nano, shell)
    shell.do_vi = types.MethodType(do_vi, shell)
    shell.do_echo = types.MethodType(do_echo, shell)