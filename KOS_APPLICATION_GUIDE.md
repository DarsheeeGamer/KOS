# KOS Application Development Guide

This guide provides detailed instructions for developing applications for the Kaede Operating System (KOS).

## Table of Contents

- [Application Structure](#application-structure)
- [Package Manifest for Applications](#package-manifest-for-applications)
- [CLI Integration](#cli-integration)
- [Data Storage and Management](#data-storage-and-management)
- [Best Practices](#best-practices)
- [Example Application](#example-application)

---

## Application Structure

A basic KOS application has the following structure:

```
app_name/
├── package.json     # Package manifest
├── main.py          # Main entry point
└── ...              # Additional files
```

### Key Components

1. **Entry Point**: The main Python file (typically `main.py`) that contains your application logic
2. **Package Manifest**: A `package.json` file describing your application and its dependencies
3. **Resource Files**: Any additional files your application needs (data files, configuration, etc.)

Applications should be self-contained within their directory for easier installation and management.

## Package Manifest for Applications

Create a `package.json` file with the following structure:

```json
{
  "name": "your_app_name",
  "version": "1.0.0",
  "description": "Description of your application",
  "author": "Your Name",
  "main": "main.py",
  "dependencies": [
    "dependency1",
    "dependency2"
  ],
  "cli_aliases": ["command1", "command2"],
  "cli_function": "cli_app"
}
```

### Key Fields

| Field | Description |
|-------|-------------|
| name | Application name (use lowercase and underscores) |
| version | Application version (follow semantic versioning) |
| description | Brief description of your application |
| author | Your name or organization |
| main | The entry point file for your application |
| dependencies | Array of other KOS packages your app depends on |
| cli_aliases | Command names to invoke your application |
| cli_function | The function to call when running from CLI |

## CLI Integration

To integrate your application with the KOS shell:

1. Define a main CLI entry point function (e.g., `cli_app()`)
2. Specify this function in the `cli_function` field of your `package.json`
3. Define command aliases in the `cli_aliases` field

### CLI Function Example

```python
def cli_app():
    """Main CLI application entry point"""
    import sys
    
    args = sys.argv[1:] if len(sys.argv) > 1 else []

    if not args or args[0] == 'help':
        print_help()
        return

    # Command parsing logic
    if args[0] == 'command1':
        # Handle command1
        pass
    elif args[0] == 'command2':
        # Handle command2
        pass
    else:
        print(f"Unknown command: {args[0]}")
        print_help()
```

## Data Storage and Management

### File Paths

Always use OS-independent path operations:

```python
import os

# File in the same directory as your script
data_file = os.path.join(os.path.dirname(__file__), 'data.json')

# Configuration file
config_file = os.path.join(os.path.dirname(__file__), 'config.json')
```

### Data Persistence

For storing application data:

```python
import json

def save_data(data, filename):
    """Save data to a JSON file"""
    try:
        with open(filename, 'w') as f:
            json.dump(data, f, indent=4)
        return True
    except Exception as e:
        print(f"Error saving data: {e}")
        return False

def load_data(filename):
    """Load data from a JSON file"""
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading data: {e}")
        return {}
```

## Best Practices

1. **Error Handling**: Always use try-except blocks for I/O operations and external API calls
2. **Path Handling**: Use `os.path.join()` for file paths to maintain cross-platform compatibility
3. **Documentation**: Include docstrings for functions and classes, and add a help command
4. **Dependencies**: Specify all dependencies in your package.json
5. **Version Control**: Use semantic versioning (MAJOR.MINOR.PATCH) for your applications
6. **User Feedback**: Provide clear feedback for user actions and errors
7. **Modularity**: Break down your application into logical components
8. **Testing**: Test your application thoroughly before distribution

## Example Application

Here's an example of a complete Quote of the Day (QOTD) application:

### Structure

```
qotd/
├── package.json
├── qotd.py         # Main application file
└── quotes.json     # Data file
```

### package.json

```json
{
  "name": "qotd",
  "version": "1.0.0",
  "description": "Quote of the Day - Displays inspirational quotes",
  "author": "KOS Developer",
  "main": "qotd.py",
  "dependencies": [],
  "cli_aliases": ["quote", "qotd"],
  "cli_function": "cli_app",
  "tags": ["utility", "inspiration"]
}
```

### qotd.py

```python
#!/usr/bin/env python3
"""
Quote of the Day (QOTD) - A KOS application for managing and displaying 
inspirational quotes
"""
import json
import os
import random
from datetime import datetime
from typing import Dict, List, Optional

class QuoteManager:
    def __init__(self):
        # Use os.path.join for cross-platform compatibility
        self.quotes_file = os.path.join(os.path.dirname(__file__), 'quotes.json')
        self.quotes = []
        self.load_quotes()

    def load_quotes(self) -> None:
        """Load quotes from the JSON file"""
        try:
            with open(self.quotes_file, 'r') as f:
                data = json.load(f)
                self.quotes = data['quotes']
        except Exception as e:
            print(f"Error loading quotes: {e}")
            self.quotes = []

    def save_quotes(self) -> None:
        """Save quotes to the JSON file"""
        try:
            with open(self.quotes_file, 'w') as f:
                json.dump({
                    'quotes': self.quotes,
                    'last_updated': datetime.now().strftime('%Y-%m-%d')
                }, f, indent=4)
        except Exception as e:
            print(f"Error saving quotes: {e}")

    def get_random_quote(self) -> Optional[Dict]:
        """Get a random quote from the collection"""
        if not self.quotes:
            return None
        return random.choice(self.quotes)

    def add_quote(self, text: str, author: str) -> bool:
        """Add a new quote to the collection"""
        if not text or not author:
            return False
        
        # Check for duplicates
        if any(q['text'].lower() == text.lower() for q in self.quotes):
            print("This quote already exists!")
            return False

        self.quotes.append({
            'text': text,
            'author': author
        })
        self.save_quotes()
        return True

    def list_quotes(self) -> List[Dict]:
        """List all quotes"""
        return self.quotes

def print_quote(quote: Dict) -> None:
    """Pretty print a quote"""
    print("\n" + "="*60)
    print(f"\"{quote['text']}\"")
    print(f"  - {quote['author']}")
    print("="*60 + "\n")

def print_help() -> None:
    """Print help message"""
    print("""
Quote of the Day - Commands:
---------------------------
quote                  Show a random quote
quote add              Add a new quote
quote list             List all quotes
quote help             Show this help message
    """)

def cli_app() -> None:
    """Main CLI application entry point"""
    import sys
    
    manager = QuoteManager()
    args = sys.argv[1:] if len(sys.argv) > 1 else []

    if not args or args[0] == 'help':
        print_help()
        return

    if args[0] == 'add':
        print("\nAdd a new quote:")
        text = input("Enter the quote text: ").strip()
        author = input("Enter the author name: ").strip()
        
        if manager.add_quote(text, author):
            print("\nQuote added successfully!")
        else:
            print("\nFailed to add quote. Make sure both text and author are provided.")
    
    elif args[0] == 'list':
        quotes = manager.list_quotes()
        print(f"\nFound {len(quotes)} quotes:")
        for quote in quotes:
            print_quote(quote)
    
    else:  # Default: show random quote
        quote = manager.get_random_quote()
        if quote:
            print_quote(quote)
        else:
            print("No quotes found!")

if __name__ == '__main__':
    cli_app()
```

### quotes.json

```json
{
  "quotes": [
    {
      "text": "The only way to do great work is to love what you do.",
      "author": "Steve Jobs"
    },
    {
      "text": "Life is what happens when you're busy making other plans.",
      "author": "John Lennon"
    }
  ],
  "last_updated": "2025-05-21"
}
```

This example demonstrates a complete, functional KOS application with proper error handling, file path management, and CLI integration.
