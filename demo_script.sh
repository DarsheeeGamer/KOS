#!/bin/bash
# Demo script for KOS shell emulation

echo "=== KOS Shell Emulation Demo ==="
echo "Setting environment variables..."

export DEMO_VAR="Hello from KOS!"
export PATH="/usr/local/bin:$PATH"

echo "Environment variables set:"
echo "DEMO_VAR = $DEMO_VAR"

echo ""
echo "Creating alias..."
alias myls="ls -la"

echo "Testing directory operations..."
pwd
echo "Current directory contents:"
ls

echo ""
echo "Demo script completed successfully!"