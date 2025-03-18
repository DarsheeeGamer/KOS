"""KOS Text Editor App"""
from rich.console import Console
from rich.text import Text
from rich import print as rprint

class TextEditor:
    def __init__(self, filesystem):
        self.fs = filesystem
        self.console = Console()
        self.current_file = None
        self.content = []
        self.cursor_pos = [0, 0]  # [line, column]

    def display_menu(self):
        print("\nKOS Text Editor")
        print("1. New File")
        print("2. Open File")
        print("3. Save File")
        print("4. Edit Current Line")
        print("5. Show Content")
        print("6. Exit")

    def show_content(self):
        if not self.content:
            print("(Empty File)")
            return

        for i, line in enumerate(self.content):
            if i == self.cursor_pos[0]:
                rprint(f"[green]>{i+1:3d}[/green] {line}")
            else:
                print(f"{i+1:4d} {line}")

    def edit_line(self, line_num, new_content):
        if 0 <= line_num < len(self.content):
            self.content[line_num] = new_content
        else:
            self.content.append(new_content)

    def save_file(self):
        if not self.current_file:
            print("No file opened")
            return
        try:
            content = "\n".join(self.content)
            self.fs.write_file(self.current_file, content.encode('utf-8'))
            print(f"Saved {self.current_file}")
        except Exception as e:
            print(f"Error saving file: {e}")

    def open_file(self, filename):
        try:
            content = self.fs.read_file(filename)
            self.content = content.decode('utf-8').split('\n')
            self.current_file = filename
            print(f"Opened {filename}")
        except Exception as e:
            print(f"Error opening file: {e}")

    def run(self):
        while True:
            self.display_menu()
            choice = input("Choose option (1-6): ")

            if choice == '1':
                self.current_file = input("Enter new file name: ")
                self.content = []
            elif choice == '2':
                filename = input("Enter file name to open: ")
                self.open_file(filename)
            elif choice == '3':
                self.save_file()
            elif choice == '4':
                try:
                    line_num = int(input("Enter line number: ")) - 1
                    content = input("Enter new content: ")
                    self.edit_line(line_num, content)
                except ValueError:
                    print("Invalid line number")
            elif choice == '5':
                self.show_content()
            elif choice == '6':
                break

def main(filesystem):
    editor = TextEditor(filesystem)
    editor.run()

if __name__ == "__main__":
    print("This app must be run through the KOS app manager")
