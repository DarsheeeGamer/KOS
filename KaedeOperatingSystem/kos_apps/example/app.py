#!/usr/bin/env python3
"""Example KOS Application"""
import sys
import argparse

def main():
    """Main application entry point"""
    parser = argparse.ArgumentParser(description='Example KOS application')
    parser.add_argument('--name', default='World', help='Name to greet')
    args = parser.parse_args()

    print(f"Hello, {args.name}!")
    print(f"This is an example KOS app running with arguments: {sys.argv[1:]}")
    return 0

if __name__ == "__main__":
    sys.exit(main())