# Shell Scripting in KOS

KOS provides a powerful shell scripting environment that allows users to automate tasks, create custom commands, and extend system functionality. This guide covers the basics of shell scripting in KOS.

## Table of Contents
- [Script Basics](#script-basics)
- [Variables](#variables)
- [Control Structures](#control-structures)
- [Functions](#functions)
- [Input/Output](#inputoutput)
- [Error Handling](#error-handling)
- [Best Practices](#best-practices)
- [Examples](#examples)

## Script Basics

### Creating a Script
1. Start your script with a shebang line:
   ```bash
   #!/bin/kos
   ```
2. Make the script executable:
   ```bash
   chmod +x script.ksh
   ```
3. Run the script:
   ```bash
   ./script.ksh
   # Or
   kos script.ksh
   ```

### Comments
```bash
# This is a single-line comment

: ' 
This is a
multi-line comment 
'
```

## Variables

### Variable Assignment
```bash
# Basic assignment
NAME="value"

# Using command output
CURRENT_DATE=$(date)


# Read-only variables
readonly CONSTANT="immutable"
```

### Variable Usage
```bash
echo $NAME
echo "Hello, ${NAME}!"
```

### Special Variables
- `$0`: Script name
- `$1`, `$2`, ...: Positional parameters
- `$#`: Number of arguments
- `$@`: All arguments
- `$?`: Exit status of last command
- `$$`: Process ID

## Control Structures

### If-Else
```bash
if [ condition ]; then
    # commands
elif [ condition ]; then
    # commands
else
    # commands
fi
```

### For Loop
```bash
for i in 1 2 3 4 5; do
    echo "Number: $i"
done

# C-style for loop
for ((i=0; i<5; i++)); do
    echo "Counter: $i"
done
```

### While Loop
```bash
count=1
while [ $count -le 5 ]; do
    echo "Count: $count"
    ((count++))
done
```

### Case Statement
```bash
case $variable in
    pattern1)
        # commands
        ;;
    pattern2)
        # commands
        ;;
    *)
        # default case
        ;;
esac
```

## Functions

### Defining Functions
```bash
function greet {
    echo "Hello, $1!"
}

# Or
greet() {
    echo "Hello, $1!"
}
```

### Using Functions
```bash
greet "World"  # Calls the function with "World" as $1
```

### Returning Values
```bash
add() {
    local sum=$(( $1 + $2 ))
    echo $sum  # Output the result
}

result=$(add 5 3)
echo "5 + 3 = $result"
```

## Input/Output

### Reading Input
```bash
# Read into a variable
read -p "Enter your name: " name
echo "Hello, $name!"

# Read multiple values
read -p "Enter two numbers: " num1 num2
```

### File Operations
```bash
# Read file line by line
while IFS= read -r line; do
    echo "Line: $line"
done < "filename.txt"

# Write to file
echo "Hello, World!" > output.txt

# Append to file
echo "Another line" >> output.txt
```

### Here Documents
```bash
cat << EOF
This is a here document.
It can span multiple lines.
Variables like $HOME will be expanded.
EOF

# To prevent expansion
cat << 'EOF'
This won't expand $variables.
EOF
```

## Error Handling

### Exit Status
```bash
command
if [ $? -ne 0 ]; then
    echo "Command failed"
    exit 1
fi

# Shorter form
if ! command; then
    echo "Command failed"
    exit 1
fi
```

### Traps
```bash
cleanup() {
    echo "Cleaning up..."
    # Cleanup code here
}

trap cleanup EXIT  # Runs on script exit
trap 'echo "Interrupted"; exit 1' INT  # Handle Ctrl+C
```

## Best Practices

1. **Use Shebang**
   Always include `#!/bin/kos` as the first line.

2. **Enable Error Checking**
   ```bash
   set -e  # Exit on error
   set -u  # Exit on undefined variables
   set -o pipefail  # Catch pipe failures
   ```

3. **Quote Variables**
   ```bash
   # Bad
   echo $VAR
   
   # Good
   echo "$VAR"
   ```

4. **Use Functions**
   Break down scripts into reusable functions.

5. **Add Comments**
   Document what the script does and how to use it.

6. **Check Dependencies**
   ```bash
   command -v jq >/dev/null 2>&1 || { 
       echo "jq is required but not installed. Aborting." >&2
       exit 1
   }
   ```

7. **Use Local Variables**
   ```bash
   my_function() {
       local var="local variable"
       # ...
   }
   ```

## Examples

### Backup Script
```bash
#!/bin/kos
set -euo pipefail

BACKUP_DIR="/backups/$(date +%Y%m%d)"
SOURCE_DIR="/data"

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Create backup
tar -czf "$BACKUP_DIR/backup_$(date +%H%M%S).tar.gz" "$SOURCE_DIR"

echo "Backup created: $BACKUP_DIR"
```

### System Monitoring
```bash
#!/bin/kos

# Check disk usage
disk_usage() {
    df -h | grep -v "tmpfs"
}

# Check memory usage
memory_usage() {
    free -h
}

# Main function
main() {
    echo "=== System Status ==="
    echo "\nDisk Usage:"
    disk_usage
    
    echo "\nMemory Usage:"
    memory_usage
}

main "$@"
```

### Interactive Menu
```bash
#!/bin/kos

show_menu() {
    clear
    echo "=== KOS System Menu ==="
    echo "1. Show System Info"
    echo "2. List Users"
    echo "3. Check Disk Space"
    echo "4. Exit"
    echo "======================="
}

while true; do
    show_menu
    read -p "Enter your choice [1-4]: " choice
    
    case $choice in
        1)
            uname -a
            ;;
        2)
            cut -d: -f1 /etc/passwd | sort
            ;;
        3)
            df -h
            ;;
        4)
            echo "Goodbye!"
            exit 0
            ;;
        *)
            echo "Invalid option!"
            ;;
    esac
    
    read -p "Press [Enter] to continue..."
done
```

## Advanced Topics

### Arrays
```bash
# Declare an array
fruits=("Apple" "Banana" "Cherry")

# Access elements
echo "First fruit: ${fruits[0]}"

# Loop through array
for fruit in "${fruits[@]}"; do
    echo "Fruit: $fruit"
done
```

### Associative Arrays
```bash
# Declare associative array
declare -A colors
colors["red"]="#FF0000"
colors["green"]="#00FF00"

# Access elements
echo "Red: ${colors[red]}"

# Loop through keys and values
for key in "${!colors[@]}"; do
    echo "$key: ${colors[$key]}"
done
```

### Process Substitution
```bash
# Compare two files
diff <(sort file1.txt) <(sort file2.txt)
```

### Debugging
```bash
# Enable debug mode
set -x
# Your script here
set +x

# Or run script with debug flag
kos -x script.ksh
```

## Conclusion

KOS shell scripting provides a powerful way to automate tasks and extend system functionality. By following best practices and leveraging the full range of shell features, you can create robust and maintainable scripts for your KOS system.
