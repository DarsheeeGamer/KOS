"""KOS GUI Framework"""
import curses
from typing import List, Dict, Any, Optional, Callable

class KosWindow:
    def __init__(self, height: int, width: int, y: int, x: int):
        self.height = height
        self.width = width
        self.y = y
        self.x = x
        self.window = curses.newwin(height, width, y, x)
        self.window.keypad(True)
        self.window.box()

    def refresh(self):
        self.window.refresh()

    def clear(self):
        self.window.clear()
        self.window.box()

    def write(self, y: int, x: int, text: str, attr=curses.A_NORMAL):
        self.window.addstr(y, x, text, attr)

class KosMenu:
    def __init__(self, window: KosWindow, items: List[str]):
        self.window = window
        self.items = items
        self.selected = 0

    def draw(self):
        self.window.clear()
        for i, item in enumerate(self.items):
            attr = curses.A_REVERSE if i == self.selected else curses.A_NORMAL
            self.window.write(i + 1, 2, item, attr)
        self.window.refresh()

    def handle_input(self, key: int) -> Optional[str]:
        if key == curses.KEY_UP and self.selected > 0:
            self.selected -= 1
        elif key == curses.KEY_DOWN and self.selected < len(self.items) - 1:
            self.selected += 1
        elif key in [curses.KEY_ENTER, ord('\n')]:
            return self.items[self.selected]
        return None

class KosDesktop:
    def __init__(self):
        self.screen = curses.initscr()
        curses.start_color()
        curses.noecho()
        curses.cbreak()
        self.screen.keypad(True)
        self.windows: Dict[str, KosWindow] = {}
        self.current_window = None

        # Initialize color pairs
        curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLUE)  # Window borders
        curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_WHITE)  # Menu items
        curses.init_pair(3, curses.COLOR_WHITE, curses.COLOR_RED)   # Error messages

    def create_window(self, name: str, height: int, width: int, y: int, x: int) -> KosWindow:
        window = KosWindow(height, width, y, x)
        self.windows[name] = window
        return window

    def switch_window(self, name: str):
        if name in self.windows:
            self.current_window = name
            self.windows[name].refresh()

    def cleanup(self):
        curses.nocbreak()
        self.screen.keypad(False)
        curses.echo()
        curses.endwin()

class KosGUI:
    def __init__(self):
        self.desktop = KosDesktop()
        self.setup_windows()

    def setup_windows(self):
        # Create main windows
        height, width = self.desktop.screen.getmaxyx()
        
        # Main menu window (left side)
        self.desktop.create_window("menu", height, 20, 0, 0)
        
        # Content window (right side)
        self.desktop.create_window("content", height, width - 20, 0, 20)
        
        # Status bar (bottom)
        self.desktop.create_window("status", 1, width, height - 1, 0)

    def run(self):
        try:
            menu_items = ["Apps", "Files", "Settings", "Exit"]
            menu = KosMenu(self.desktop.windows["menu"], menu_items)
            
            while True:
                menu.draw()
                key = self.desktop.screen.getch()
                
                if key == ord('q'):
                    break
                    
                selection = menu.handle_input(key)
                if selection:
                    self.handle_menu_selection(selection)
                
        finally:
            self.desktop.cleanup()

    def handle_menu_selection(self, selection: str):
        content_window = self.desktop.windows["content"]
        content_window.clear()
        
        if selection == "Apps":
            self.show_apps()
        elif selection == "Files":
            self.show_files()
        elif selection == "Settings":
            self.show_settings()
        elif selection == "Exit":
            return True
            
        content_window.refresh()
        return False

    def show_apps(self):
        # Show installed applications
        pass

    def show_files(self):
        # Show file manager
        pass

    def show_settings(self):
        # Show system settings
        pass
