# NANO Text Editor

The NANO text editor is a lightweight, user-friendly editor integrated into KOS. It provides an intuitive interface for creating and editing text files directly from the command line.

## Basic Usage

```bash
nano filename.txt
```

If the file exists, NANO will open it for editing. If the file doesn't exist, NANO will create a new file that will be saved when you exit.

## Interface

The NANO editor interface consists of:

- **Main editing area**: Where you edit your text
- **Status bar**: Shows the current filename and modification status
- **Shortcut menu**: Shows available keyboard commands (toggle with ^G)
- **Command line**: Shows prompts and messages at the bottom of the screen

## Keyboard Shortcuts

### Navigation

| Shortcut | Description |
|----------|-------------|
| Arrow keys | Move the cursor |
| Home | Go to beginning of line |
| End | Go to end of line |
| Page Up | Scroll up one page |
| Page Down | Scroll down one page |
| ^C | Show cursor position |
| ^_ | Go to specific line number |

### File Operations

| Shortcut | Description |
|----------|-------------|
| ^O | Save file |
| ^R | Read file into current buffer |
| ^X | Exit (prompts to save if file modified) |

### Editing

| Shortcut | Description |
|----------|-------------|
| ^K | Cut current line to clipboard |
| ^U | Paste clipboard contents |
| ^J | Justify paragraph |
| ^T | Spell check |
| ^\ | Replace text |
| Delete | Delete character under cursor |
| Backspace | Delete character before cursor |
| ^D | Delete character under cursor |

### Search

| Shortcut | Description |
|----------|-------------|
| ^W | Search for text |
| ^F | Find next occurrence |
| ^\ | Search and replace |

### Other

| Shortcut | Description |
|----------|-------------|
| ^G | Show help menu |
| ^L | Refresh screen |
| ^Z | Suspend editor (resume with 'fg') |
| ^Y | Scroll up one line |
| ^V | Scroll down one line |

## Advanced Features

### Syntax Highlighting

NANO automatically highlights syntax for many file types including:
- Python (.py)
- JavaScript (.js)
- HTML (.html, .htm)
- CSS (.css)
- Markdown (.md)
- XML (.xml)
- JSON (.json)
- Shell scripts (.sh)

The editor detects file types based on file extensions.

### Line Numbering

Toggle line numbers with Alt+N. This makes it easier to navigate large files and reference specific sections.

### Auto-indentation

Auto-indentation helps maintain consistent code formatting. Enable/disable with Alt+I.

### Multiple Buffers

Work with multiple files simultaneously:
- ^O to open a new file
- Alt+< and Alt+> to switch between open buffers
- ^X to close the current buffer

### Macros

Record and play keyboard macros:
- ^Q to start/stop recording
- ^E to play back the recorded macro

### Backup Files

NANO automatically creates backup files with the extension `.bak` to prevent data loss. This feature can be toggled with Alt+B.

### Auto-save

Enable auto-save with Alt+A to automatically save your work at regular intervals.

## Configuration

NANO can be configured through command-line options:

```bash
nano --linenumbers --autoindent filename.txt
```

Common options:
- `--linenumbers`: Display line numbers
- `--autoindent`: Enable auto-indentation
- `--mouse`: Enable mouse support
- `--backup`: Create backup files
- `--syntax=FORMAT`: Force a specific syntax highlighting

## Example Workflows

### Creating a New Python Script

```bash
nano myscript.py
```

The editor will automatically enable Python syntax highlighting. Type your Python code, then press ^O to save and ^X to exit.

### Searching and Replacing Text

1. Press ^\ to enter search and replace mode
2. Enter the search term and press Enter
3. Enter the replacement text and press Enter
4. Choose whether to replace all occurrences (A) or confirm each replacement (Y/N)

### Working with Multiple Files

1. Open the first file with `nano file1.txt`
2. Press Alt+> to open a new buffer
3. Press ^O to open another file (file2.txt)
4. Use Alt+< and Alt+> to switch between the files
5. Edit both files as needed
6. Save with ^O and exit with ^X for each buffer

## Best Practices

1. Save your work frequently with ^O
2. Use line numbers for better navigation in large files
3. Learn keyboard shortcuts to increase efficiency
4. Use syntax highlighting for code files
5. Take advantage of search and replace for bulk changes
6. Use auto-indentation for consistent code formatting
