#!/usr/bin/env python3
"""
Calendar - A KOS application that shows the current month
"""

import sys
import calendar

class CalendarManager:
    def __init__(self):
        self.now = calendar.datetime.datetime.now()
        self.year = self.now.year
        self.month = self.now.month
    
    def get_current_month(self):
        "Get the current month as a calendar"

        return calendar.month(self.year, self.month)

def print_current_month(cal_instance):
    print(cal_instance.get_current_month())

def print_help():
    print("""
    Calendar - Commands:
    ====================
    cal current        - Print the calender for the current month
    cal help    - show this help message
    """)

def cli_app():
    """ Main CLI application entry point """
    cal = CalendarManager()
    args = sys.argv[1:] if len(sys.argv) > 1 else []

    if not args or args[0] == 'help':
        print_help()
        return

    if args[0] == 'current':
        print_current_month(cal)

if __name__ == '__main__':
    cli_app()
