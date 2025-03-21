
#!/usr/bin/env python3

def add(a, b):
    return a + b

def subtract(a, b):
    return a - b

def multiply(a, b):
    return a * b

def divide(a, b):
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b

def cli_app():
    print("KOS Calculator")
    print("Enter expression (e.g., 2 + 3):")
    while True:
        try:
            expr = input("> ")
            if expr.lower() == 'exit':
                print("Exiting calculator...")
                raise SystemExit(0)

            parts = expr.split()
            if len(parts) != 3:
                print("Invalid expression. Use format: number operator number (or 'exit')")
                continue

            a = float(parts[0])
            op = parts[1]
            b = float(parts[2])

            result = None
            if op == '+':
                result = add(a, b)
            elif op == '-':
                result = subtract(a, b)
            elif op == '*':
                result = multiply(a, b)
            elif op == '/':
                result = divide(a, b)
            else:
                print("Invalid operator. Use +, -, *, or /")
                continue

            print(f"Result: {result}")
        except ValueError as e:
            print(f"Error: {e}")
        except Exception as e:
            print(f"An error occurred: {e}")

if __name__ == "__main__":
    cli_app()
