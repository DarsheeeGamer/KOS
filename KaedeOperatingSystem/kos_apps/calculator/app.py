"""KOS Calculator App"""
from rich.console import Console
from rich.table import Table

class Calculator:
    def __init__(self):
        self.console = Console()
        self.memory = 0

    def display_menu(self):
        print("\nKOS Calculator")
        print("1. Basic Operation (+, -, *, /)")
        print("2. Scientific Functions (sqrt, pow)")
        print("3. Memory Operations")
        print("4. Exit")

    def basic_operation(self):
        try:
            num1 = float(input("Enter first number: "))
            op = input("Enter operation (+,-,*,/): ")
            num2 = float(input("Enter second number: "))

            result = None
            if op == '+':
                result = num1 + num2
            elif op == '-':
                result = num1 - num2
            elif op == '*':
                result = num1 * num2
            elif op == '/':
                result = num1 / num2

            if result is not None:
                print(f"\nResult: {result}")
                return result
        except Exception as e:
            print(f"Error: {e}")

    def scientific(self):
        try:
            print("\n1. Square Root")
            print("2. Power")
            choice = input("Choose operation: ")

            if choice == '1':
                num = float(input("Enter number: "))
                result = pow(num, 0.5)
                print(f"Square root: {result}")
                return result
            elif choice == '2':
                base = float(input("Enter base: "))
                exp = float(input("Enter exponent: "))
                result = pow(base, exp)
                print(f"Result: {result}")
                return result
        except Exception as e:
            print(f"Error: {e}")

    def memory_ops(self):
        print("\nMemory:", self.memory)
        print("1. Store")
        print("2. Recall")
        print("3. Clear")
        print("4. Add to Memory")
        choice = input("Choose operation: ")

        if choice == '1':
            value = float(input("Enter value to store: "))
            self.memory = value
        elif choice == '2':
            print(f"Memory value: {self.memory}")
        elif choice == '3':
            self.memory = 0
        elif choice == '4':
            value = float(input("Enter value to add: "))
            self.memory += value

    def run(self):
        while True:
            self.display_menu()
            choice = input("Choose option (1-4): ")

            if choice == '1':
                self.basic_operation()
            elif choice == '2':
                self.scientific()
            elif choice == '3':
                self.memory_ops()
            elif choice == '4':
                break

def main(filesystem):
    calc = Calculator()
    calc.run()

if __name__ == "__main__":
    print("This app must be run through the KOS app manager")
