"""
Kaede Language Exceptions
=========================

Exception hierarchy for Kaede language errors and runtime exceptions.
"""

class KaedeError(Exception):
    """Base exception for all Kaede language errors"""
    def __init__(self, message: str, line: int = 0, column: int = 0, filename: str = "<unknown>"):
        super().__init__(message)
        self.message = message
        self.line = line
        self.column = column
        self.filename = filename
    
    def __str__(self):
        if self.line > 0:
            return f"{self.filename}:{self.line}:{self.column}: {self.message}"
        return self.message

# Lexical errors
class KaedeLexicalError(KaedeError):
    """Lexical analysis errors"""
    pass

class KaedeSyntaxError(KaedeError):
    """Syntax parsing errors"""
    pass

class KaedeIndentationError(KaedeSyntaxError):
    """Indentation errors"""
    pass

# Type system errors
class KaedeTypeError(KaedeError):
    """Type checking and inference errors"""
    pass

class KaedeTypeMismatchError(KaedeTypeError):
    """Type mismatch errors"""
    def __init__(self, expected_type: str, actual_type: str, line: int = 0, column: int = 0, filename: str = "<unknown>"):
        message = f"Type mismatch: expected '{expected_type}', got '{actual_type}'"
        super().__init__(message, line, column, filename)
        self.expected_type = expected_type
        self.actual_type = actual_type

class KaedeUndefinedTypeError(KaedeTypeError):
    """Undefined type errors"""
    def __init__(self, type_name: str, line: int = 0, column: int = 0, filename: str = "<unknown>"):
        message = f"Undefined type: '{type_name}'"
        super().__init__(message, line, column, filename)
        self.type_name = type_name

# Runtime errors
class KaedeRuntimeError(KaedeError):
    """Runtime execution errors"""
    pass

class KaedeNameError(KaedeRuntimeError):
    """Undefined variable/function errors"""
    def __init__(self, name: str, line: int = 0, column: int = 0, filename: str = "<unknown>"):
        message = f"Name '{name}' is not defined"
        super().__init__(message, line, column, filename)
        self.name = name

class KaedeAttributeError(KaedeRuntimeError):
    """Attribute access errors"""
    def __init__(self, obj_type: str, attr_name: str, line: int = 0, column: int = 0, filename: str = "<unknown>"):
        message = f"'{obj_type}' object has no attribute '{attr_name}'"
        super().__init__(message, line, column, filename)
        self.obj_type = obj_type
        self.attr_name = attr_name

class KaedeIndexError(KaedeRuntimeError):
    """Index out of bounds errors"""
    def __init__(self, index: int, size: int, line: int = 0, column: int = 0, filename: str = "<unknown>"):
        message = f"Index {index} out of range (size: {size})"
        super().__init__(message, line, column, filename)
        self.index = index
        self.size = size

class KaedeKeyError(KaedeRuntimeError):
    """Dictionary key errors"""
    def __init__(self, key: str, line: int = 0, column: int = 0, filename: str = "<unknown>"):
        message = f"Key '{key}' not found"
        super().__init__(message, line, column, filename)
        self.key = key

class KaedeZeroDivisionError(KaedeRuntimeError):
    """Division by zero errors"""
    def __init__(self, line: int = 0, column: int = 0, filename: str = "<unknown>"):
        message = "Division by zero"
        super().__init__(message, line, column, filename)

class KaedeOverflowError(KaedeRuntimeError):
    """Arithmetic overflow errors"""
    def __init__(self, operation: str, line: int = 0, column: int = 0, filename: str = "<unknown>"):
        message = f"Arithmetic overflow in {operation}"
        super().__init__(message, line, column, filename)
        self.operation = operation

# Memory management errors
class KaedeMemoryError(KaedeRuntimeError):
    """Memory management errors"""
    pass

class KaedeNullPointerError(KaedeMemoryError):
    """Null pointer dereference errors"""
    def __init__(self, line: int = 0, column: int = 0, filename: str = "<unknown>"):
        message = "Null pointer dereference"
        super().__init__(message, line, column, filename)

class KaedeMemoryLeakError(KaedeMemoryError):
    """Memory leak detection errors"""
    def __init__(self, allocated_bytes: int, line: int = 0, column: int = 0, filename: str = "<unknown>"):
        message = f"Memory leak detected: {allocated_bytes} bytes not freed"
        super().__init__(message, line, column, filename)
        self.allocated_bytes = allocated_bytes

class KaedeDoubleFreeError(KaedeMemoryError):
    """Double free errors"""
    def __init__(self, line: int = 0, column: int = 0, filename: str = "<unknown>"):
        message = "Attempt to free already freed memory"
        super().__init__(message, line, column, filename)

class KaedeUseAfterFreeError(KaedeMemoryError):
    """Use after free errors"""
    def __init__(self, line: int = 0, column: int = 0, filename: str = "<unknown>"):
        message = "Use of freed memory"
        super().__init__(message, line, column, filename)

# Control flow errors
class KaedeControlFlowError(KaedeRuntimeError):
    """Control flow errors"""
    pass

class KaedeBreakError(KaedeControlFlowError):
    """Break statement outside loop"""
    def __init__(self, line: int = 0, column: int = 0, filename: str = "<unknown>"):
        message = "'break' outside loop"
        super().__init__(message, line, column, filename)

class KaedeContinueError(KaedeControlFlowError):
    """Continue statement outside loop"""
    def __init__(self, line: int = 0, column: int = 0, filename: str = "<unknown>"):
        message = "'continue' not properly in loop"
        super().__init__(message, line, column, filename)

class KaedeReturnError(KaedeControlFlowError):
    """Return statement outside function"""
    def __init__(self, line: int = 0, column: int = 0, filename: str = "<unknown>"):
        message = "'return' outside function"
        super().__init__(message, line, column, filename)

# Function and method errors
class KaedeFunctionError(KaedeRuntimeError):
    """Function-related errors"""
    pass

class KaedeArgumentError(KaedeFunctionError):
    """Function argument errors"""
    def __init__(self, function_name: str, expected: int, actual: int, line: int = 0, column: int = 0, filename: str = "<unknown>"):
        message = f"Function '{function_name}' expects {expected} arguments, got {actual}"
        super().__init__(message, line, column, filename)
        self.function_name = function_name
        self.expected = expected
        self.actual = actual

class KaedeRecursionError(KaedeFunctionError):
    """Maximum recursion depth exceeded"""
    def __init__(self, max_depth: int, line: int = 0, column: int = 0, filename: str = "<unknown>"):
        message = f"Maximum recursion depth exceeded (limit: {max_depth})"
        super().__init__(message, line, column, filename)
        self.max_depth = max_depth

# Import and module errors
class KaedeImportError(KaedeError):
    """Module import errors"""
    def __init__(self, module_name: str, line: int = 0, column: int = 0, filename: str = "<unknown>"):
        message = f"Cannot import module '{module_name}'"
        super().__init__(message, line, column, filename)
        self.module_name = module_name

class KaedeModuleNotFoundError(KaedeImportError):
    """Module not found errors"""
    def __init__(self, module_name: str, line: int = 0, column: int = 0, filename: str = "<unknown>"):
        message = f"Module '{module_name}' not found"
        super().__init__(message, line, column, filename)

# Compilation errors
class KaedeCompilationError(KaedeError):
    """Compilation errors"""
    pass

class KaedeTemplateError(KaedeCompilationError):
    """Template instantiation errors"""
    def __init__(self, template_name: str, type_args: str, line: int = 0, column: int = 0, filename: str = "<unknown>"):
        message = f"Cannot instantiate template '{template_name}' with types '{type_args}'"
        super().__init__(message, line, column, filename)
        self.template_name = template_name
        self.type_args = type_args

class KaedeConstViolationError(KaedeCompilationError):
    """Const correctness violation"""
    def __init__(self, variable_name: str, line: int = 0, column: int = 0, filename: str = "<unknown>"):
        message = f"Cannot modify const variable '{variable_name}'"
        super().__init__(message, line, column, filename)
        self.variable_name = variable_name

# Concurrency errors
class KaedeConcurrencyError(KaedeRuntimeError):
    """Concurrency-related errors"""
    pass

class KaedeDeadlockError(KaedeConcurrencyError):
    """Deadlock detection"""
    def __init__(self, line: int = 0, column: int = 0, filename: str = "<unknown>"):
        message = "Deadlock detected"
        super().__init__(message, line, column, filename)

class KaedeRaceConditionError(KaedeConcurrencyError):
    """Race condition detection"""
    def __init__(self, variable_name: str, line: int = 0, column: int = 0, filename: str = "<unknown>"):
        message = f"Race condition detected on variable '{variable_name}'"
        super().__init__(message, line, column, filename)
        self.variable_name = variable_name

# System integration errors
class KaedeSystemError(KaedeRuntimeError):
    """System integration errors"""
    pass

class KaedePermissionError(KaedeSystemError):
    """Permission denied errors"""
    def __init__(self, operation: str, line: int = 0, column: int = 0, filename: str = "<unknown>"):
        message = f"Permission denied: {operation}"
        super().__init__(message, line, column, filename)
        self.operation = operation

class KaedeIOError(KaedeSystemError):
    """I/O operation errors"""
    def __init__(self, operation: str, details: str, line: int = 0, column: int = 0, filename: str = "<unknown>"):
        message = f"I/O error in {operation}: {details}"
        super().__init__(message, line, column, filename)
        self.operation = operation
        self.details = details

# Warning classes (for non-fatal issues)
class KaedeWarning(Warning):
    """Base warning for Kaede language"""
    def __init__(self, message: str, line: int = 0, column: int = 0, filename: str = "<unknown>"):
        super().__init__(message)
        self.message = message
        self.line = line
        self.column = column
        self.filename = filename

class KaedeDeprecationWarning(KaedeWarning):
    """Deprecation warnings"""
    pass

class KaedePerformanceWarning(KaedeWarning):
    """Performance-related warnings"""
    pass

class KaedeMemoryWarning(KaedeWarning):
    """Memory usage warnings"""
    pass

class KaedeSecurityWarning(KaedeWarning):
    """Security-related warnings"""
    pass

# Exception utilities
def create_traceback(error: KaedeError, call_stack: list) -> str:
    """Create a formatted traceback for Kaede errors"""
    lines = []
    lines.append("Traceback (most recent call last):")
    
    for frame in call_stack:
        lines.append(f'  File "{frame.get("filename", "<unknown>")}", line {frame.get("line", 0)}, in {frame.get("function", "<unknown>")}')
        if "code" in frame:
            lines.append(f"    {frame['code']}")
    
    lines.append(f"{error.__class__.__name__}: {error}")
    return "\n".join(lines)

def format_error_context(error: KaedeError, source_lines: list) -> str:
    """Format error with surrounding source code context"""
    if not source_lines or error.line <= 0:
        return str(error)
    
    lines = []
    start_line = max(1, error.line - 2)
    end_line = min(len(source_lines), error.line + 2)
    
    for i in range(start_line, end_line + 1):
        line_num = i
        line_content = source_lines[i - 1] if i <= len(source_lines) else ""
        marker = ">>> " if i == error.line else "    "
        lines.append(f"{marker}{line_num:4d}: {line_content}")
        
        if i == error.line and error.column > 0:
            # Add pointer to error column
            pointer = " " * (len(marker) + 6 + error.column - 1) + "^"
            lines.append(pointer)
    
    lines.append(f"\n{error.__class__.__name__}: {error.message}")
    return "\n".join(lines) 