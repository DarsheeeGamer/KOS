#!/usr/bin/env python3
"""
Test KOS interactive mode with simulated input
"""

import sys
import os
import subprocess
import tempfile

def test_interactive_mode():
    """Test KOS interactive mode"""
    
    # Create test script with commands
    script_content = """
python kos_launcher.py --interactive --memory 1GB --cpus 1 << 'EOF'
status
network
memory
processes
shutdown
EOF
"""
    
    # Write to temporary script
    with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
        f.write(script_content)
        script_path = f.name
    
    try:
        # Run the script
        result = subprocess.run(['bash', script_path], 
                              capture_output=True, 
                              text=True, 
                              timeout=30,
                              cwd='/home/kaededev/KOS')
        
        print("KOS Interactive Mode Test Output:")
        print("=" * 50)
        print(result.stdout)
        
        if result.stderr:
            print("STDERR:")
            print(result.stderr)
            
        print("Return code:", result.returncode)
        
    finally:
        # Clean up
        os.unlink(script_path)

if __name__ == "__main__":
    test_interactive_mode()