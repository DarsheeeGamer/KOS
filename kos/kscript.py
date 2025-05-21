"""KOS Script - Simple scripting support for KOS"""

def run_kscript_file(filepath: str, context: dict = None) -> bool:
    """Execute a KOS script file
    
    Args:
        filepath: Path to the script file
        context: Optional execution context
    
    Returns:
        bool: True if execution successful, False otherwise
    """
    try:
        with open(filepath, 'r') as f:
            code = compile(f.read(), filepath, 'exec')
            exec(code, context or {})
        return True
    except Exception as e:
        print(f"Script execution error: {str(e)}")
        return False
