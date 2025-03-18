"""KOS Calendar App"""
from rich.console import Console
from rich.table import Table
from rich import print as rprint
from datetime import datetime, timedelta
import calendar
import json
import os

class CalendarApp:
    def __init__(self, filesystem):
        self.fs = filesystem
        self.console = Console()
        self.current_date = datetime.now()
        self.events = {}
        self.load_events()

    def load_events(self):
        try:
            content = self.fs.read_file("/events.json")
            self.events = json.loads(content.decode('utf-8'))
        except:
            self.events = {}

    def save_events(self):
        try:
            content = json.dumps(self.events, indent=2).encode('utf-8')
            self.fs.write_file("/events.json", content)
        except Exception as e:
            print(f"Error saving events: {e}")

    def display_menu(self):
        print("\nKOS Calendar")
        print("1. View Calendar")
        print("2. Add Event")
        print("3. List Events")
        print("4. Delete Event")
        print("5. Change Month")
        print("6. Exit")

    def display_calendar(self):
        cal = calendar.monthcalendar(self.current_date.year, self.current_date.month)
        
        # Create calendar table
        table = Table(title=f"{calendar.month_name[self.current_date.month]} {self.current_date.year}")
        for day in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]:
            table.add_column(day, justify="center")

        # Add calendar days with events highlighted
        for week in cal:
            row = []
            for day in week:
                if day == 0:
                    cell = ""
                else:
                    date_key = f"{self.current_date.year}-{self.current_date.month:02d}-{day:02d}"
                    if date_key in self.events:
                        cell = Text(str(day), style="bold red")
                    else:
                        cell = str(day)
                row.append(cell)
            table.add_row(*row)

        self.console.print(table)

    def add_event(self):
        try:
            date_str = input("Enter date (YYYY-MM-DD): ")
            event_date = datetime.strptime(date_str, "%Y-%m-%d")
            time_str = input("Enter time (HH:MM): ")
            event_time = datetime.strptime(time_str, "%H:%M").time()
            title = input("Enter event title: ")
            description = input("Enter event description: ")

            date_key = event_date.strftime("%Y-%m-%d")
            if date_key not in self.events:
                self.events[date_key] = []

            self.events[date_key].append({
                "time": time_str,
                "title": title,
                "description": description
            })

            self.save_events()
            print("Event added successfully")

        except Exception as e:
            print(f"Error adding event: {e}")

    def list_events(self):
        table = Table(show_header=True)
        table.add_column("Date")
        table.add_column("Time")
        table.add_column("Title")
        table.add_column("Description")

        for date_key in sorted(self.events.keys()):
            for event in sorted(self.events[date_key], key=lambda x: x['time']):
                table.add_row(
                    date_key,
                    event['time'],
                    event['title'],
                    event['description']
                )

        self.console.print(table)

    def delete_event(self):
        try:
            date_str = input("Enter date (YYYY-MM-DD): ")
            if date_str not in self.events:
                print("No events on this date")
                return

            print("\nEvents on this date:")
            for i, event in enumerate(self.events[date_str], 1):
                print(f"{i}. {event['time']} - {event['title']}")

            event_num = int(input("Enter event number to delete: "))
            if 1 <= event_num <= len(self.events[date_str]):
                self.events[date_str].pop(event_num - 1)
                if not self.events[date_str]:
                    del self.events[date_str]
                self.save_events()
                print("Event deleted successfully")
            else:
                print("Invalid event number")

        except Exception as e:
            print(f"Error deleting event: {e}")

    def change_month(self):
        try:
            direction = input("Previous or Next month? (p/n): ").lower()
            if direction == 'p':
                if self.current_date.month == 1:
                    self.current_date = self.current_date.replace(year=self.current_date.year - 1, month=12)
                else:
                    self.current_date = self.current_date.replace(month=self.current_date.month - 1)
            elif direction == 'n':
                if self.current_date.month == 12:
                    self.current_date = self.current_date.replace(year=self.current_date.year + 1, month=1)
                else:
                    self.current_date = self.current_date.replace(month=self.current_date.month + 1)
        except Exception as e:
            print(f"Error changing month: {e}")

    def run(self):
        while True:
            self.display_menu()
            choice = input("Choose option (1-6): ")

            if choice == '1':
                self.display_calendar()
            elif choice == '2':
                self.add_event()
            elif choice == '3':
                self.list_events()
            elif choice == '4':
                self.delete_event()
            elif choice == '5':
                self.change_month()
            elif choice == '6':
                break

def main(filesystem):
    calendar_app = CalendarApp(filesystem)
    calendar_app.run()

if __name__ == "__main__":
    print("This app must be run through the KOS app manager")
