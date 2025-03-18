"""KOS File Manager App"""
from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich import print as rprint
from datetime import datetime
import os

class FileManager:
    def __init__(self, filesystem):
        self.fs = filesystem
        self.console = Console()
        self.current_path = "/"
        self.selected_items = set()

    def display_menu(self):
        print("\nKOS File Manager")
        print("1. List Files")
        print("2. Navigate Directory")
        print("3. Copy/Move Files")
        print("4. Delete Files")
        print("5. File Properties")
        print("6. Create Directory")
        print("7. Exit")

    def list_files(self):
        table = Table(show_header=True)
        table.add_column("Type")
        table.add_column("Name")
        table.add_column("Size")
        table.add_column("Modified")
        table.add_column("Permissions")

        try:
            files = self.fs.ls(self.current_path)
            for file in files:
                file_path = os.path.join(self.current_path, file)
                inode = self.fs.get_inode_by_path(file_path)
                
                type_icon = "📁" if inode.file_type == 'dir' else "📄"
                size = str(inode.size) + " B"
                modified = datetime.fromtimestamp(inode.modified_at).strftime('%Y-%m-%d %H:%M')
                perms = oct(inode.permissions)[2:]

                style = "bold" if file in self.selected_items else ""
                table.add_row(
                    type_icon,
                    Text(file, style=style),
                    size,
                    modified,
                    perms
                )

            self.console.print(table)
        except Exception as e:
            print(f"Error listing files: {e}")

    def navigate(self):
        path = input("Enter path (.. for parent directory): ")
        try:
            if path == "..":
                self.current_path = os.path.dirname(self.current_path) or "/"
            else:
                new_path = os.path.join(self.current_path, path)
                self.fs.cd(new_path)  # This will validate the path
                self.current_path = new_path
        except Exception as e:
            print(f"Error navigating: {e}")

    def copy_move(self):
        try:
            if not self.selected_items:
                print("No items selected. Use 'Select' option first.")
                return

            action = input("Copy or Move? (c/m): ").lower()
            if action not in ['c', 'm']:
                print("Invalid action")
                return

            dest = input("Enter destination path: ")
            for item in self.selected_items:
                src_path = os.path.join(self.current_path, item)
                dest_path = os.path.join(dest, item)
                
                if action == 'c':
                    # Copy implementation
                    content = self.fs.read_file(src_path)
                    self.fs.write_file(dest_path, content)
                else:
                    # Move implementation
                    content = self.fs.read_file(src_path)
                    self.fs.write_file(dest_path, content)
                    self.fs.rm(src_path)

            self.selected_items.clear()
            print("Operation completed successfully")
        except Exception as e:
            print(f"Error during operation: {e}")

    def delete_files(self):
        try:
            if not self.selected_items:
                print("No items selected. Use 'Select' option first.")
                return

            confirm = input(f"Delete {len(self.selected_items)} items? (y/n): ").lower()
            if confirm == 'y':
                for item in self.selected_items:
                    path = os.path.join(self.current_path, item)
                    self.fs.rm(path)
                self.selected_items.clear()
                print("Items deleted successfully")
        except Exception as e:
            print(f"Error deleting files: {e}")

    def show_properties(self):
        name = input("Enter file name: ")
        try:
            path = os.path.join(self.current_path, name)
            inode = self.fs.get_inode_by_path(path)
            
            table = Table(show_header=False)
            table.add_column("Property")
            table.add_column("Value")

            table.add_row("Name", name)
            table.add_row("Type", inode.file_type)
            table.add_row("Size", f"{inode.size} bytes")
            table.add_row("Permissions", oct(inode.permissions)[2:])
            table.add_row("Owner", f"{inode.uid}:{inode.gid}")
            table.add_row("Created", datetime.fromtimestamp(inode.created_at).strftime('%Y-%m-%d %H:%M:%S'))
            table.add_row("Modified", datetime.fromtimestamp(inode.modified_at).strftime('%Y-%m-%d %H:%M:%S'))
            table.add_row("Accessed", datetime.fromtimestamp(inode.accessed_at).strftime('%Y-%m-%d %H:%M:%S'))

            self.console.print(table)
        except Exception as e:
            print(f"Error getting properties: {e}")

    def create_directory(self):
        name = input("Enter directory name: ")
        try:
            path = os.path.join(self.current_path, name)
            self.fs.mkdir(path)
            print(f"Directory '{name}' created successfully")
        except Exception as e:
            print(f"Error creating directory: {e}")

    def run(self):
        while True:
            self.display_menu()
            choice = input("Choose option (1-7): ")

            if choice == '1':
                self.list_files()
            elif choice == '2':
                self.navigate()
            elif choice == '3':
                self.copy_move()
            elif choice == '4':
                self.delete_files()
            elif choice == '5':
                self.show_properties()
            elif choice == '6':
                self.create_directory()
            elif choice == '7':
                break

def main(filesystem):
    manager = FileManager(filesystem)
    manager.run()

if __name__ == "__main__":
    print("This app must be run through the KOS app manager")
