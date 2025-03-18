"""KOS System Monitor App"""
import time
import json
from rich.console import Console
from rich.table import Table

class SystemMonitor:
    def __init__(self, filesystem):
        self.fs = filesystem
        self.console = Console()

    def show_system_stats(self):
        # Get filesystem stats
        stats = self.fs.get_stats()
        
        # Create stats table
        table = Table(title="System Resources")
        table.add_column("Resource")
        table.add_column("Usage")
        
        # Add disk stats
        total_mb = stats['total_size'] / (1024*1024)
        used_mb = stats['used_size'] / (1024*1024)
        free_mb = stats['free_size'] / (1024*1024)
        
        table.add_row(
            "Disk Total", 
            f"{total_mb:.1f}MB"
        )
        table.add_row(
            "Disk Used",
            f"{used_mb:.1f}MB ({(used_mb/total_mb*100):.1f}%)"
        )
        table.add_row(
            "Disk Free",
            f"{free_mb:.1f}MB"
        )
        
        # Add inode stats
        table.add_row(
            "Total Inodes",
            str(stats['total_inodes'])
        )
        table.add_row(
            "Used Inodes",
            str(stats['used_inodes'])
        )
        
        self.console.print(table)

    def show_process_list(self):
        table = Table(title="Process List")
        table.add_column("PID")
        table.add_column("User")
        table.add_column("CPU%")
        table.add_column("MEM%")
        table.add_column("Command")
        
        # Simulate process data
        processes = [
            {"pid": 1, "user": "root", "cpu": 0.1, "mem": 1.0, "cmd": "init"},
            {"pid": 2, "user": "root", "cpu": 0.5, "mem": 2.0, "cmd": "kos_kernel"},
            {"pid": 100, "user": "user", "cpu": 1.4, "mem": 7.0, "cmd": "kos_shell"}
        ]
        
        for proc in processes:
            table.add_row(
                str(proc["pid"]),
                proc["user"],
                f"{proc['cpu']:.1f}",
                f"{proc['mem']:.1f}",
                proc["cmd"]
            )
            
        self.console.print(table)

    def run(self):
        try:
            while True:
                self.console.clear()
                print(f"KOS System Monitor - {time.strftime('%H:%M:%S')}")
                print("Press Ctrl+C to exit\n")
                
                self.show_system_stats()
                print()
                self.show_process_list()
                
                time.sleep(2)  # Update every 2 seconds
        except KeyboardInterrupt:
            print("\nExiting System Monitor")

def main(filesystem):
    monitor = SystemMonitor(filesystem)
    monitor.run()

if __name__ == "__main__":
    print("This app must be run through the KOS app manager")
