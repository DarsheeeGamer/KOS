#!/usr/bin/env python3
"""
Quote of the Day (QOTD) - A KOS application for managing and displaying inspirational quotes
"""
import json
import os
import random
from datetime import datetime
from typing import Dict, List, Optional

class QuoteManager:
    def __init__(self):
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
quote                   Show a random quote
quote add              Add a new quote
quote list             List all quotes
quote help             Show this help message
    """)

def cli_app(args=None):
    """Command-line interface for the quote manager"""
    
    manager = QuoteManager()
    
    # If args is None, get from sys.argv, otherwise use provided args
    # This allows KOS to call the function directly with arguments
    if args is None:
        import sys
        args = sys.argv[1:] if len(sys.argv) > 1 else []

    if not args or args[0] == 'help':
        print_help()
        return True  # Indicate successful execution

    if args[0] == 'add':
        print("\nAdd a new quote:")
        try:
            text = input("Enter the quote text: ").strip()
            author = input("Enter the author name: ").strip()
            
            if manager.add_quote(text, author):
                print("\nQuote added successfully!")
            else:
                print("\nFailed to add quote. Make sure both text and author are provided.")
        except KeyboardInterrupt:
            print("\nQuote addition cancelled.")
        except Exception as e:
            print(f"\nError adding quote: {str(e)}")
        return True  # Indicate successful execution
    
    elif args[0] == 'list':
        quotes = manager.list_quotes()
        print(f"\nFound {len(quotes)} quotes:")
        for quote in quotes:
            print_quote(quote)
        return True  # Indicate successful execution
    
    else:  # Default: show random quote
        quote = manager.get_random_quote()
        if quote:
            print_quote(quote)
        else:
            print("No quotes found!")
        return True  # Indicate successful execution

if __name__ == '__main__':
    cli_app()
