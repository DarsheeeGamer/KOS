#!/usr/bin/env python3
"""
KOS VFS Explorer - GUI Application
===================================
A Windows Explorer-like GUI for browsing the KOS Virtual File System
"""

import os
import sys
import time
import json
import threading
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
from tkinter import PhotoImage
import tkinter.font as tkfont

# Add KOS to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import KOS VFS
try:
    from kos.vfs import get_vfs
import os
VFS_O_RDONLY = os.O_RDONLY
VFS_O_WRONLY = os.O_WRONLY
VFS_O_CREAT = os.O_CREAT
VFS_O_TRUNC = os.O_TRUNC
    from kos.vfs.vfs_index import get_vfs_index
    VFS_AVAILABLE = True
except ImportError:
    VFS_AVAILABLE = False
    print("Warning: KOS VFS not available. Please ensure KOS is properly installed.")

class VFSExplorerGUI:
    """Main GUI application for VFS Explorer"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("KOS VFS Explorer - kaede.kdsk")
        self.root.geometry("1200x700")
        
        # Initialize VFS
        if VFS_AVAILABLE:
            self.vfs = get_vfs()
            self.index = get_vfs_index(self.vfs) if self.vfs else None
        else:
            self.vfs = None
            self.index = None
        
        # Current state
        self.current_path = "/"
        self.selected_item = None
        self.clipboard = None
        self.clipboard_operation = None  # 'cut' or 'copy'
        
        # Icons (using Unicode symbols as placeholders)
        self.icons = {
            'folder': '📁',
            'folder_open': '📂',
            'file': '📄',
            'text': '📝',
            'image': '🖼️',
            'audio': '🎵',
            'video': '🎬',
            'archive': '📦',
            'code': '💻',
            'binary': '⚙️',
            'unknown': '❓'
        }
        
        # Setup UI
        self.setup_ui()
        
        # Load initial directory
        self.refresh_view()
        
        # Bind keyboard shortcuts
        self.setup_shortcuts()
    
    def setup_ui(self):
        """Setup the user interface"""
        
        # Create menu bar
        self.create_menu_bar()
        
        # Create toolbar
        self.create_toolbar()
        
        # Create main paned window
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True)
        
        # Left panel - Tree view
        left_frame = ttk.Frame(main_paned, width=250)
        main_paned.add(left_frame, weight=1)
        
        # Tree view for directory structure
        tree_frame = ttk.Frame(left_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(tree_frame, text="Folders", font=('Arial', 10, 'bold')).pack(pady=5)
        
        # Treeview with scrollbar
        tree_scroll = ttk.Scrollbar(tree_frame)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.tree = ttk.Treeview(tree_frame, yscrollcommand=tree_scroll.set, selectmode="browse")
        tree_scroll.config(command=self.tree.yview)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=5)
        
        # Configure tree
        self.tree.heading('#0', text='KOS VFS', anchor=tk.W)
        
        # Bind tree events
        self.tree.bind('<<TreeviewSelect>>', self.on_tree_select)
        self.tree.bind('<Double-1>', self.on_tree_double_click)
        
        # Right panel - File list
        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=3)
        
        # Path bar
        path_frame = ttk.Frame(right_frame)
        path_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(path_frame, text="Path:").pack(side=tk.LEFT, padx=5)
        
        self.path_var = tk.StringVar(value="/")
        self.path_entry = ttk.Entry(path_frame, textvariable=self.path_var, font=('Arial', 10))
        self.path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.path_entry.bind('<Return>', self.on_path_change)
        
        ttk.Button(path_frame, text="Go", command=self.on_path_change).pack(side=tk.LEFT)
        
        # File list with columns
        list_frame = ttk.Frame(right_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5)
        
        # Create Treeview for file list
        columns = ('Size', 'Type', 'Modified')
        self.file_list = ttk.Treeview(list_frame, columns=columns, show='tree headings')
        
        # Define columns
        self.file_list.heading('#0', text='Name', anchor=tk.W)
        self.file_list.heading('Size', text='Size', anchor=tk.W)
        self.file_list.heading('Type', text='Type', anchor=tk.W)
        self.file_list.heading('Modified', text='Modified', anchor=tk.W)
        
        # Configure column widths
        self.file_list.column('#0', width=300, minwidth=200)
        self.file_list.column('Size', width=100, minwidth=80)
        self.file_list.column('Type', width=100, minwidth=80)
        self.file_list.column('Modified', width=150, minwidth=120)
        
        # Scrollbars
        vsb = ttk.Scrollbar(list_frame, orient="vertical", command=self.file_list.yview)
        hsb = ttk.Scrollbar(list_frame, orient="horizontal", command=self.file_list.xview)
        self.file_list.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        # Grid layout
        self.file_list.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)
        
        # Bind file list events
        self.file_list.bind('<Double-1>', self.on_file_double_click)
        self.file_list.bind('<Button-3>', self.on_right_click)  # Right-click menu
        self.file_list.bind('<<TreeviewSelect>>', self.on_file_select)
        
        # Status bar
        self.create_status_bar()
        
        # Context menu
        self.create_context_menu()
        
        # Load directory tree
        self.load_tree()
    
    def create_menu_bar(self):
        """Create the menu bar"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="New Folder", command=self.new_folder, accelerator="Ctrl+Shift+N")
        file_menu.add_command(label="New File", command=self.new_file, accelerator="Ctrl+N")
        file_menu.add_separator()
        file_menu.add_command(label="Open", command=self.open_file, accelerator="Enter")
        file_menu.add_command(label="Open in Text Editor", command=self.open_in_editor)
        file_menu.add_separator()
        file_menu.add_command(label="Delete", command=self.delete_item, accelerator="Del")
        file_menu.add_command(label="Rename", command=self.rename_item, accelerator="F2")
        file_menu.add_separator()
        file_menu.add_command(label="Properties", command=self.show_properties, accelerator="Alt+Enter")
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit, accelerator="Alt+F4")
        
        # Edit menu
        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Edit", menu=edit_menu)
        edit_menu.add_command(label="Cut", command=self.cut_item, accelerator="Ctrl+X")
        edit_menu.add_command(label="Copy", command=self.copy_item, accelerator="Ctrl+C")
        edit_menu.add_command(label="Paste", command=self.paste_item, accelerator="Ctrl+V")
        edit_menu.add_separator()
        edit_menu.add_command(label="Select All", command=self.select_all, accelerator="Ctrl+A")
        edit_menu.add_separator()
        edit_menu.add_command(label="Find", command=self.find_files, accelerator="Ctrl+F")
        
        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Refresh", command=self.refresh_view, accelerator="F5")
        view_menu.add_separator()
        view_menu.add_command(label="Show Hidden Files", command=self.toggle_hidden)
        view_menu.add_separator()
        view_menu.add_command(label="Details View", command=lambda: self.change_view('details'))
        view_menu.add_command(label="List View", command=lambda: self.change_view('list'))
        view_menu.add_command(label="Icons View", command=lambda: self.change_view('icons'))
        
        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="VFS Statistics", command=self.show_statistics)
        tools_menu.add_command(label="Rebuild Index", command=self.rebuild_index)
        tools_menu.add_separator()
        tools_menu.add_command(label="Export to Host", command=self.export_to_host)
        tools_menu.add_command(label="Import from Host", command=self.import_from_host)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self.show_about)
        help_menu.add_command(label="Keyboard Shortcuts", command=self.show_shortcuts)
    
    def create_toolbar(self):
        """Create the toolbar"""
        toolbar = ttk.Frame(self.root)
        toolbar.pack(side=tk.TOP, fill=tk.X)
        
        # Navigation buttons
        ttk.Button(toolbar, text="⬅ Back", command=self.go_back).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="➡ Forward", command=self.go_forward).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="⬆ Up", command=self.go_up).pack(side=tk.LEFT, padx=2)
        
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        
        # Action buttons
        ttk.Button(toolbar, text="🔄 Refresh", command=self.refresh_view).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="📁 New Folder", command=self.new_folder).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="📄 New File", command=self.new_file).pack(side=tk.LEFT, padx=2)
        
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        
        # Edit buttons
        ttk.Button(toolbar, text="✂️ Cut", command=self.cut_item).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="📋 Copy", command=self.copy_item).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="📌 Paste", command=self.paste_item).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="🗑️ Delete", command=self.delete_item).pack(side=tk.LEFT, padx=2)
        
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        
        # Search box
        ttk.Label(toolbar, text="🔍 Search:").pack(side=tk.LEFT, padx=5)
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(toolbar, textvariable=self.search_var, width=20)
        search_entry.pack(side=tk.LEFT, padx=2)
        search_entry.bind('<Return>', lambda e: self.find_files())
        ttk.Button(toolbar, text="Find", command=self.find_files).pack(side=tk.LEFT, padx=2)
    
    def create_status_bar(self):
        """Create the status bar"""
        self.status_bar = ttk.Frame(self.root)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Status text
        self.status_text = tk.StringVar(value="Ready")
        ttk.Label(self.status_bar, textvariable=self.status_text, relief=tk.SUNKEN, anchor=tk.W).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        
        # Item count
        self.item_count = tk.StringVar(value="0 items")
        ttk.Label(self.status_bar, textvariable=self.item_count, relief=tk.SUNKEN, width=15).pack(
            side=tk.LEFT, padx=2)
        
        # Selected info
        self.selected_info = tk.StringVar(value="")
        ttk.Label(self.status_bar, textvariable=self.selected_info, relief=tk.SUNKEN, width=20).pack(
            side=tk.LEFT, padx=2)
    
    def create_context_menu(self):
        """Create right-click context menu"""
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Open", command=self.open_file)
        self.context_menu.add_command(label="Open in Editor", command=self.open_in_editor)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Cut", command=self.cut_item)
        self.context_menu.add_command(label="Copy", command=self.copy_item)
        self.context_menu.add_command(label="Paste", command=self.paste_item)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Rename", command=self.rename_item)
        self.context_menu.add_command(label="Delete", command=self.delete_item)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Properties", command=self.show_properties)
    
    def setup_shortcuts(self):
        """Setup keyboard shortcuts"""
        self.root.bind('<F5>', lambda e: self.refresh_view())
        self.root.bind('<F2>', lambda e: self.rename_item())
        self.root.bind('<Delete>', lambda e: self.delete_item())
        self.root.bind('<Control-n>', lambda e: self.new_file())
        self.root.bind('<Control-Shift-N>', lambda e: self.new_folder())
        self.root.bind('<Control-c>', lambda e: self.copy_item())
        self.root.bind('<Control-x>', lambda e: self.cut_item())
        self.root.bind('<Control-v>', lambda e: self.paste_item())
        self.root.bind('<Control-a>', lambda e: self.select_all())
        self.root.bind('<Control-f>', lambda e: self.find_files())
        self.root.bind('<Alt-Return>', lambda e: self.show_properties())
        self.root.bind('<BackSpace>', lambda e: self.go_up())
    
    def load_tree(self):
        """Load the directory tree in the left panel"""
        if not self.index:
            return
        
        # Clear existing tree
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Add root
        root_id = self.tree.insert('', 'end', text='/ (VFS Root)', open=True, tags=('folder',))
        
        # Load subdirectories recursively
        self._load_tree_recursive('/', root_id, depth=0, max_depth=3)
    
    def _load_tree_recursive(self, path, parent_id, depth, max_depth):
        """Recursively load tree nodes"""
        if depth >= max_depth:
            return
        
        if not self.index:
            return
        
        entries = self.index.list_directory(path)
        
        for entry in sorted(entries, key=lambda e: e.name.lower()):
            if entry.is_directory():
                node_id = self.tree.insert(parent_id, 'end', 
                                          text=f"{self.icons['folder']} {entry.name}",
                                          tags=('folder',))
                
                # Load children for shallow depth
                if depth < 2:
                    child_path = os.path.join(path, entry.name).replace('//', '/')
                    self._load_tree_recursive(child_path, node_id, depth + 1, max_depth)
    
    def refresh_view(self):
        """Refresh the current directory view"""
        if not self.index:
            self.status_text.set("VFS not available")
            return
        
        # Clear file list
        for item in self.file_list.get_children():
            self.file_list.delete(item)
        
        # Get directory contents
        entries = self.index.list_directory(self.current_path)
        
        # Sort entries (directories first, then files)
        entries.sort(key=lambda e: (not e.is_directory(), e.name.lower()))
        
        # Add entries to list
        item_count = 0
        for entry in entries:
            if entry.is_directory():
                icon = self.icons['folder']
                file_type = "Folder"
            else:
                icon = self.icons[self.get_file_type(entry.name)]
                file_type = self.get_file_extension(entry.name).upper() or "File"
            
            # Format size
            size = self.format_size(entry.size) if not entry.is_directory() else ""
            
            # Format date
            modified = datetime.fromtimestamp(entry.mtime).strftime("%Y-%m-%d %H:%M")
            
            # Insert item
            self.file_list.insert('', 'end', text=f"{icon} {entry.name}",
                                 values=(size, file_type, modified),
                                 tags=('directory' if entry.is_directory() else 'file',))
            item_count += 1
        
        # Update status
        self.path_var.set(self.current_path)
        self.item_count.set(f"{item_count} items")
        self.status_text.set(f"Loaded {self.current_path}")
    
    def get_file_type(self, filename):
        """Get file type icon based on extension"""
        ext = os.path.splitext(filename)[1].lower()
        
        if ext in ['.txt', '.md', '.log', '.cfg', '.conf', '.ini']:
            return 'text'
        elif ext in ['.py', '.js', '.cpp', '.c', '.h', '.java', '.cs', '.sh']:
            return 'code'
        elif ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.ico']:
            return 'image'
        elif ext in ['.mp3', '.wav', '.ogg', '.m4a', '.flac']:
            return 'audio'
        elif ext in ['.mp4', '.avi', '.mkv', '.mov', '.wmv']:
            return 'video'
        elif ext in ['.zip', '.tar', '.gz', '.bz2', '.7z', '.rar']:
            return 'archive'
        elif ext in ['.exe', '.dll', '.so', '.o']:
            return 'binary'
        else:
            return 'file'
    
    def get_file_extension(self, filename):
        """Get file extension"""
        ext = os.path.splitext(filename)[1]
        return ext[1:] if ext else ""
    
    def format_size(self, size):
        """Format file size"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"
    
    def on_tree_select(self, event):
        """Handle tree selection"""
        selection = self.tree.selection()
        if selection:
            item = selection[0]
            # Get the path from tree
            path_parts = []
            while item:
                text = self.tree.item(item, 'text')
                # Remove icon from text
                for icon in self.icons.values():
                    text = text.replace(icon + ' ', '')
                if text and text != '/ (VFS Root)':
                    path_parts.insert(0, text)
                item = self.tree.parent(item)
            
            # Build path
            if path_parts:
                self.current_path = '/' + '/'.join(path_parts)
            else:
                self.current_path = '/'
            
            self.refresh_view()
    
    def on_tree_double_click(self, event):
        """Handle tree double-click"""
        self.on_tree_select(event)
    
    def on_file_select(self, event):
        """Handle file selection"""
        selection = self.file_list.selection()
        if selection:
            item = selection[0]
            item_text = self.file_list.item(item, 'text')
            # Remove icon
            for icon in self.icons.values():
                item_text = item_text.replace(icon + ' ', '')
            
            self.selected_item = item_text
            
            # Update status
            values = self.file_list.item(item, 'values')
            if values[0]:  # Has size (is a file)
                self.selected_info.set(f"{item_text} ({values[0]})")
            else:
                self.selected_info.set(item_text)
    
    def on_file_double_click(self, event):
        """Handle file double-click"""
        selection = self.file_list.selection()
        if selection:
            item = selection[0]
            tags = self.file_list.item(item, 'tags')
            
            if 'directory' in tags:
                # Navigate into directory
                item_text = self.file_list.item(item, 'text')
                # Remove icon
                for icon in self.icons.values():
                    item_text = item_text.replace(icon + ' ', '')
                
                if self.current_path == '/':
                    self.current_path = '/' + item_text
                else:
                    self.current_path = self.current_path + '/' + item_text
                
                self.refresh_view()
            else:
                # Open file
                self.open_file()
    
    def on_right_click(self, event):
        """Handle right-click"""
        # Select item under cursor
        item = self.file_list.identify_row(event.y)
        if item:
            self.file_list.selection_set(item)
            self.on_file_select(None)
        
        # Show context menu
        self.context_menu.post(event.x_root, event.y_root)
    
    def on_path_change(self, event=None):
        """Handle path bar change"""
        new_path = self.path_var.get()
        
        if self.index and self.index.get_entry(new_path):
            self.current_path = new_path
            self.refresh_view()
        else:
            messagebox.showerror("Error", f"Path not found: {new_path}")
            self.path_var.set(self.current_path)
    
    def go_back(self):
        """Go back in navigation history"""
        # Simple implementation - just go up
        self.go_up()
    
    def go_forward(self):
        """Go forward in navigation history"""
        # Not implemented in simple version
        pass
    
    def go_up(self):
        """Go to parent directory"""
        if self.current_path != '/':
            self.current_path = os.path.dirname(self.current_path) or '/'
            self.refresh_view()
    
    def open_file(self):
        """Open selected file"""
        if not self.selected_item or not self.vfs:
            return
        
        file_path = os.path.join(self.current_path, self.selected_item).replace('//', '/')
        
        # Check if it's a directory
        entry = self.index.get_entry(file_path)
        if entry and entry.is_directory():
            self.current_path = file_path
            self.refresh_view()
            return
        
        # Open file in viewer
        self.open_in_editor()
    
    def open_in_editor(self):
        """Open file in text editor window"""
        if not self.selected_item or not self.vfs:
            return
        
        file_path = os.path.join(self.current_path, self.selected_item).replace('//', '/')
        
        try:
            # Read file content
            with self.vfs.open(file_path, VFS_O_RDONLY) as f:
                content = f.read()
                text_content = content.decode('utf-8', errors='replace')
            
            # Create editor window
            editor_window = tk.Toplevel(self.root)
            editor_window.title(f"Edit: {self.selected_item}")
            editor_window.geometry("800x600")
            
            # Text editor with scrollbar
            text_frame = ttk.Frame(editor_window)
            text_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            
            text_widget = scrolledtext.ScrolledText(text_frame, wrap=tk.WORD, 
                                                   font=('Consolas', 10))
            text_widget.pack(fill=tk.BOTH, expand=True)
            text_widget.insert(1.0, text_content)
            
            # Button frame
            button_frame = ttk.Frame(editor_window)
            button_frame.pack(fill=tk.X, padx=5, pady=5)
            
            def save_file():
                new_content = text_widget.get(1.0, tk.END).encode('utf-8')
                try:
                    flags = VFS_O_WRONLY | VFS_O_CREAT | VFS_O_TRUNC
                    with self.vfs.open(file_path, flags) as f:
                        f.write(new_content)
                    messagebox.showinfo("Success", f"File saved: {self.selected_item}")
                    self.refresh_view()
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to save file: {e}")
            
            ttk.Button(button_frame, text="Save", command=save_file).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Close", 
                      command=editor_window.destroy).pack(side=tk.LEFT, padx=5)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open file: {e}")
    
    def new_folder(self):
        """Create a new folder"""
        if not self.vfs:
            return
        
        # Ask for folder name
        folder_name = tk.simpledialog.askstring("New Folder", "Enter folder name:")
        if not folder_name:
            return
        
        folder_path = os.path.join(self.current_path, folder_name).replace('//', '/')
        
        try:
            self.vfs.mkdir(folder_path, 0o755)
            
            # Update index
            if self.index:
                from kos.vfs.vfs_index import VFSEntry
                entry = VFSEntry(
                    path=folder_path,
                    name=folder_name,
                    type=0o040000,  # Directory
                    size=4096,
                    mode=0o040755,
                    uid=0,
                    gid=0,
                    atime=time.time(),
                    mtime=time.time(),
                    ctime=time.time(),
                    children=[]
                )
                self.index.add_entry(folder_path, entry)
            
            self.refresh_view()
            self.status_text.set(f"Created folder: {folder_name}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create folder: {e}")
    
    def new_file(self):
        """Create a new file"""
        if not self.vfs:
            return
        
        # Ask for file name
        file_name = tk.simpledialog.askstring("New File", "Enter file name:")
        if not file_name:
            return
        
        file_path = os.path.join(self.current_path, file_name).replace('//', '/')
        
        try:
            flags = VFS_O_WRONLY | VFS_O_CREAT | VFS_O_TRUNC
            with self.vfs.open(file_path, flags, 0o644) as f:
                f.write(b'')  # Empty file
            
            # Update index
            if self.index:
                from kos.vfs.vfs_index import VFSEntry
                entry = VFSEntry(
                    path=file_path,
                    name=file_name,
                    type=0o100000,  # Regular file
                    size=0,
                    mode=0o100644,
                    uid=0,
                    gid=0,
                    atime=time.time(),
                    mtime=time.time(),
                    ctime=time.time()
                )
                self.index.add_entry(file_path, entry)
            
            self.refresh_view()
            self.status_text.set(f"Created file: {file_name}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create file: {e}")
    
    def delete_item(self):
        """Delete selected item"""
        if not self.selected_item or not self.vfs:
            return
        
        item_path = os.path.join(self.current_path, self.selected_item).replace('//', '/')
        
        # Confirm deletion
        result = messagebox.askyesno("Confirm Delete", 
                                     f"Are you sure you want to delete '{self.selected_item}'?")
        if not result:
            return
        
        try:
            entry = self.index.get_entry(item_path) if self.index else None
            
            if entry and entry.is_directory():
                self.vfs.rmdir(item_path)
            else:
                self.vfs.unlink(item_path)
            
            # Update index
            if self.index:
                self.index.remove_entry(item_path)
            
            self.refresh_view()
            self.status_text.set(f"Deleted: {self.selected_item}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete: {e}")
    
    def rename_item(self):
        """Rename selected item"""
        if not self.selected_item:
            return
        
        # Ask for new name
        new_name = tk.simpledialog.askstring("Rename", 
                                            f"Enter new name for '{self.selected_item}':",
                                            initialvalue=self.selected_item)
        if not new_name or new_name == self.selected_item:
            return
        
        old_path = os.path.join(self.current_path, self.selected_item).replace('//', '/')
        new_path = os.path.join(self.current_path, new_name).replace('//', '/')
        
        messagebox.showinfo("Info", "Rename operation not yet implemented in VFS")
    
    def cut_item(self):
        """Cut selected item"""
        if self.selected_item:
            self.clipboard = os.path.join(self.current_path, self.selected_item).replace('//', '/')
            self.clipboard_operation = 'cut'
            self.status_text.set(f"Cut: {self.selected_item}")
    
    def copy_item(self):
        """Copy selected item"""
        if self.selected_item:
            self.clipboard = os.path.join(self.current_path, self.selected_item).replace('//', '/')
            self.clipboard_operation = 'copy'
            self.status_text.set(f"Copied: {self.selected_item}")
    
    def paste_item(self):
        """Paste clipboard item"""
        if not self.clipboard:
            return
        
        messagebox.showinfo("Info", "Copy/Move operations not yet implemented in VFS")
    
    def select_all(self):
        """Select all items in current view"""
        for item in self.file_list.get_children():
            self.file_list.selection_add(item)
    
    def find_files(self):
        """Find files dialog"""
        pattern = self.search_var.get()
        if not pattern:
            pattern = tk.simpledialog.askstring("Find Files", "Enter search pattern:")
            if not pattern:
                return
        
        if not self.index:
            return
        
        # Search for files
        results = self.index.search(pattern)
        
        # Show results in new window
        result_window = tk.Toplevel(self.root)
        result_window.title(f"Search Results: {pattern}")
        result_window.geometry("600x400")
        
        # Results list
        result_frame = ttk.Frame(result_window)
        result_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        result_list = tk.Listbox(result_frame, font=('Consolas', 9))
        scrollbar = ttk.Scrollbar(result_frame, command=result_list.yview)
        result_list.config(yscrollcommand=scrollbar.set)
        
        result_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Add results
        for entry in results:
            icon = self.icons['folder'] if entry.is_directory() else self.icons['file']
            result_list.insert(tk.END, f"{icon} {entry.path}")
        
        # Status
        ttk.Label(result_window, text=f"Found {len(results)} matches").pack(pady=5)
        
        # Close button
        ttk.Button(result_window, text="Close", 
                  command=result_window.destroy).pack(pady=5)
    
    def toggle_hidden(self):
        """Toggle showing hidden files"""
        # Not implemented
        pass
    
    def change_view(self, view_type):
        """Change view type"""
        # Not implemented - would change between icon/list/detail views
        pass
    
    def show_properties(self):
        """Show properties of selected item"""
        if not self.selected_item or not self.index:
            return
        
        item_path = os.path.join(self.current_path, self.selected_item).replace('//', '/')
        entry = self.index.get_entry(item_path)
        
        if not entry:
            return
        
        # Properties window
        prop_window = tk.Toplevel(self.root)
        prop_window.title(f"Properties: {self.selected_item}")
        prop_window.geometry("400x450")
        prop_window.resizable(False, False)
        
        # Create notebook for tabs
        notebook = ttk.Notebook(prop_window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # General tab
        general_frame = ttk.Frame(notebook)
        notebook.add(general_frame, text="General")
        
        # Icon and name
        icon = self.icons['folder'] if entry.is_directory() else self.icons[self.get_file_type(entry.name)]
        ttk.Label(general_frame, text=f"{icon} {entry.name}", 
                 font=('Arial', 12, 'bold')).grid(row=0, column=0, columnspan=2, pady=10)
        
        ttk.Separator(general_frame, orient=tk.HORIZONTAL).grid(row=1, column=0, columnspan=2, 
                                                               sticky='ew', pady=5)
        
        # Properties
        props = [
            ("Type:", "Folder" if entry.is_directory() else self.get_file_extension(entry.name).upper() or "File"),
            ("Location:", os.path.dirname(entry.path)),
            ("Size:", self.format_size(entry.size)),
            ("Size on disk:", self.format_size(entry.blocks * 512) if entry.blocks else "N/A"),
            ("Created:", datetime.fromtimestamp(entry.ctime).strftime("%Y-%m-%d %H:%M:%S")),
            ("Modified:", datetime.fromtimestamp(entry.mtime).strftime("%Y-%m-%d %H:%M:%S")),
            ("Accessed:", datetime.fromtimestamp(entry.atime).strftime("%Y-%m-%d %H:%M:%S")),
        ]
        
        for i, (label, value) in enumerate(props, start=2):
            ttk.Label(general_frame, text=label, font=('Arial', 9, 'bold')).grid(
                row=i, column=0, sticky='w', padx=10, pady=2)
            ttk.Label(general_frame, text=value, font=('Arial', 9)).grid(
                row=i, column=1, sticky='w', padx=10, pady=2)
        
        # Permissions tab
        perm_frame = ttk.Frame(notebook)
        notebook.add(perm_frame, text="Permissions")
        
        ttk.Label(perm_frame, text="File Permissions", 
                 font=('Arial', 11, 'bold')).grid(row=0, column=0, columnspan=3, pady=10)
        
        # Parse permissions
        mode = entry.mode & 0o777
        perms = [
            ("Owner:", (mode >> 6) & 7),
            ("Group:", (mode >> 3) & 7),
            ("Others:", mode & 7),
        ]
        
        for i, (label, perm_val) in enumerate(perms, start=1):
            ttk.Label(perm_frame, text=label, font=('Arial', 9, 'bold')).grid(
                row=i, column=0, sticky='w', padx=10, pady=5)
            
            r = "r" if perm_val & 4 else "-"
            w = "w" if perm_val & 2 else "-"
            x = "x" if perm_val & 1 else "-"
            
            ttk.Label(perm_frame, text=f"{r}{w}{x}", font=('Consolas', 10)).grid(
                row=i, column=1, sticky='w', padx=10, pady=5)
        
        ttk.Label(perm_frame, text=f"Octal: {oct(mode)}", font=('Consolas', 10)).grid(
            row=4, column=0, columnspan=2, pady=10)
        
        ttk.Label(perm_frame, text=f"UID: {entry.uid}  GID: {entry.gid}", 
                 font=('Arial', 9)).grid(row=5, column=0, columnspan=2, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(prop_window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(button_frame, text="OK", command=prop_window.destroy).pack(side=tk.RIGHT, padx=5)
    
    def show_statistics(self):
        """Show VFS statistics"""
        if not self.index:
            return
        
        stats = self.index.get_statistics()
        
        # Statistics window
        stat_window = tk.Toplevel(self.root)
        stat_window.title("VFS Statistics")
        stat_window.geometry("400x300")
        stat_window.resizable(False, False)
        
        # Stats frame
        stats_frame = ttk.LabelFrame(stat_window, text="KOS VFS Statistics (kaede.kdsk)")
        stats_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        stats_data = [
            ("Total Entries:", f"{stats['total_entries']}"),
            ("Files:", f"{stats['file_count']}"),
            ("Directories:", f"{stats['directory_count']}"),
            ("Symbolic Links:", f"{stats['symlink_count']}"),
            ("Total Size:", self.format_size(stats['total_size'])),
            ("", ""),
            ("Largest File:", stats.get('largest_file', 'N/A')),
            ("Newest File:", stats.get('newest_file', 'N/A')),
            ("Oldest File:", stats.get('oldest_file', 'N/A')),
        ]
        
        for i, (label, value) in enumerate(stats_data):
            if label:
                ttk.Label(stats_frame, text=label, font=('Arial', 10, 'bold')).grid(
                    row=i, column=0, sticky='w', padx=10, pady=3)
                ttk.Label(stats_frame, text=value, font=('Arial', 10)).grid(
                    row=i, column=1, sticky='w', padx=10, pady=3)
        
        # Close button
        ttk.Button(stat_window, text="Close", command=stat_window.destroy).pack(pady=10)
    
    def rebuild_index(self):
        """Rebuild VFS index"""
        if not self.index:
            return
        
        result = messagebox.askyesno("Rebuild Index", 
                                     "This will rebuild the entire VFS index. Continue?")
        if not result:
            return
        
        try:
            self.status_text.set("Rebuilding index...")
            self.root.update()
            
            self.index.rebuild_index()
            
            self.refresh_view()
            self.load_tree()
            
            messagebox.showinfo("Success", "VFS index rebuilt successfully")
            self.status_text.set("Index rebuilt")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to rebuild index: {e}")
    
    def export_to_host(self):
        """Export file from VFS to host filesystem"""
        if not self.selected_item or not self.vfs:
            return
        
        vfs_path = os.path.join(self.current_path, self.selected_item).replace('//', '/')
        
        # Ask for save location
        host_path = filedialog.asksaveasfilename(
            defaultextension="",
            filetypes=[("All Files", "*.*")],
            initialfile=self.selected_item
        )
        
        if not host_path:
            return
        
        try:
            # Read from VFS
            with self.vfs.open(vfs_path, VFS_O_RDONLY) as vfs_file:
                data = vfs_file.read()
            
            # Write to host
            with open(host_path, 'wb') as host_file:
                host_file.write(data)
            
            messagebox.showinfo("Success", f"Exported to: {host_path}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export: {e}")
    
    def import_from_host(self):
        """Import file from host filesystem to VFS"""
        if not self.vfs:
            return
        
        # Ask for file to import
        host_path = filedialog.askopenfilename(
            title="Select file to import",
            filetypes=[("All Files", "*.*")]
        )
        
        if not host_path:
            return
        
        filename = os.path.basename(host_path)
        vfs_path = os.path.join(self.current_path, filename).replace('//', '/')
        
        try:
            # Read from host
            with open(host_path, 'rb') as host_file:
                data = host_file.read()
            
            # Write to VFS
            flags = VFS_O_WRONLY | VFS_O_CREAT | VFS_O_TRUNC
            with self.vfs.open(vfs_path, flags, 0o644) as vfs_file:
                vfs_file.write(data)
            
            # Update index
            if self.index:
                from kos.vfs.vfs_index import VFSEntry
                stat_info = os.stat(host_path)
                entry = VFSEntry(
                    path=vfs_path,
                    name=filename,
                    type=0o100000,  # Regular file
                    size=len(data),
                    mode=0o100644,
                    uid=0,
                    gid=0,
                    atime=time.time(),
                    mtime=stat_info.st_mtime,
                    ctime=time.time()
                )
                self.index.add_entry(vfs_path, entry)
            
            self.refresh_view()
            messagebox.showinfo("Success", f"Imported: {filename}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to import: {e}")
    
    def show_about(self):
        """Show about dialog"""
        about_text = """KOS VFS Explorer
        
A graphical file explorer for the KOS Virtual File System (kaede.kdsk)

Version: 1.0
Author: KOS Development Team

This explorer allows you to browse, view, and manage files
stored in the KOS Virtual File System without entering the
KOS shell environment."""
        
        messagebox.showinfo("About KOS VFS Explorer", about_text)
    
    def show_shortcuts(self):
        """Show keyboard shortcuts"""
        shortcuts = """Keyboard Shortcuts:

F5          - Refresh view
F2          - Rename selected item
Delete      - Delete selected item
Ctrl+N      - New file
Ctrl+Shift+N - New folder
Ctrl+C      - Copy
Ctrl+X      - Cut
Ctrl+V      - Paste
Ctrl+A      - Select all
Ctrl+F      - Find files
Alt+Enter   - Properties
Backspace   - Go up one level
Enter       - Open file/folder"""
        
        messagebox.showinfo("Keyboard Shortcuts", shortcuts)

def main():
    """Main entry point"""
    # Try to import tkinter.simpledialog for dialogs
    try:
        import tkinter.simpledialog
        tk.simpledialog = tkinter.simpledialog
    except ImportError:
        print("Warning: simpledialog not available")
    
    # Create main window
    root = tk.Tk()
    
    # Set window icon (if available)
    try:
        # You can add a custom icon here
        pass
    except:
        pass
    
    # Create and run application
    app = VFSExplorerGUI(root)
    
    # Center window on screen
    root.update_idletasks()
    width = root.winfo_width()
    height = root.winfo_height()
    x = (root.winfo_screenwidth() // 2) - (width // 2)
    y = (root.winfo_screenheight() // 2) - (height // 2)
    root.geometry(f"{width}x{height}+{x}+{y}")
    
    # Run main loop
    root.mainloop()

if __name__ == "__main__":
    main()