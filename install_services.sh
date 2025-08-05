#!/bin/bash
#
# KOS Services Installation Script
# Installs KADCM and KAIM systemd services
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}This script must be run as root${NC}"
   exit 1
fi

echo -e "${GREEN}KOS Services Installation Script${NC}"
echo "================================="

# Function to check command existence
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Step 1: Install dependencies
echo -e "\n${YELLOW}Step 1: Installing dependencies...${NC}"
if command_exists apt-get; then
    apt-get update
    apt-get install -y python3 python3-pip build-essential linux-headers-$(uname -r) gcc g++ make
elif command_exists yum; then
    yum install -y python3 python3-pip kernel-devel gcc gcc-c++ make
else
    echo -e "${RED}Unsupported package manager. Please install dependencies manually.${NC}"
    exit 1
fi

# Install Python dependencies
pip3 install systemd-python || echo -e "${YELLOW}Warning: systemd-python not available${NC}"

# Step 2: Create system users and groups
echo -e "\n${YELLOW}Step 2: Creating system users and groups...${NC}"

# Create kaim group and user
groupadd -f kaim
useradd -r -g kaim -d /var/lib/kaim -s /bin/false _kaim || true

# Create kos group and user
groupadd -f kos
useradd -r -g kos -d /var/lib/kos -s /bin/false kos || true

# Add users to appropriate groups
usermod -a -G kaim kos || true

echo -e "${GREEN}Users and groups created${NC}"

# Step 3: Create directories
echo -e "\n${YELLOW}Step 3: Creating directories...${NC}"

# KADCM directories
mkdir -p /var/run/kos/runtime/kadcm
mkdir -p /var/lib/kos/kadcm
mkdir -p /var/lib/kos/secure
mkdir -p /etc/kos

# KAIM directories
mkdir -p /var/run/kos/runtime/kaim
mkdir -p /var/lib/kaim

# Log directory
mkdir -p /var/log/kos

# Set permissions
chown -R kos:kos /var/run/kos
chown -R kos:kos /var/lib/kos
chown -R _kaim:kaim /var/lib/kaim
chown -R kos:kos /var/log/kos

chmod 750 /var/run/kos
chmod 750 /var/lib/kos
chmod 700 /var/lib/kos/secure
chmod 750 /var/lib/kaim
chmod 755 /var/log/kos

echo -e "${GREEN}Directories created${NC}"

# Step 4: Build and install KAIM kernel module
echo -e "\n${YELLOW}Step 4: Building KAIM kernel module...${NC}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KAIM_DIR="$SCRIPT_DIR/kos/kaim/kernel"

if [ -d "$KAIM_DIR" ]; then
    cd "$KAIM_DIR"
    
    # Clean any previous builds
    make clean || true
    
    # Build the module
    echo "Building kernel module..."
    make module
    
    # Install module
    echo "Installing kernel module..."
    make install_module
    
    # Install libraries
    echo "Installing libraries..."
    make install_library
    
    # Install headers
    echo "Installing headers..."
    make install_headers
    
    # Install udev rules
    echo "Installing udev rules..."
    make install_udev
    
    # Create device if module loaded successfully
    if lsmod | grep -q kaim; then
        echo -e "${GREEN}KAIM kernel module installed successfully${NC}"
    else
        echo -e "${YELLOW}Warning: KAIM module not loaded. You may need to reboot.${NC}"
    fi
    
    cd "$SCRIPT_DIR"
else
    echo -e "${RED}KAIM kernel directory not found at $KAIM_DIR${NC}"
    echo -e "${YELLOW}Skipping kernel module installation${NC}"
fi

# Step 5: Install systemd service files
echo -e "\n${YELLOW}Step 5: Installing systemd service files...${NC}"

# Copy service files
cp "$SCRIPT_DIR/kos/services/kadcm.service" /etc/systemd/system/
cp "$SCRIPT_DIR/kos/services/kaim.service" /etc/systemd/system/

# Set permissions
chmod 644 /etc/systemd/system/kadcm.service
chmod 644 /etc/systemd/system/kaim.service

# Reload systemd
systemctl daemon-reload

echo -e "${GREEN}Service files installed${NC}"

# Step 6: Create default configuration files
echo -e "\n${YELLOW}Step 6: Creating configuration files...${NC}"

# KADCM config
cat > /etc/kos/kadcm.conf << EOF
{
    "listen_address": "localhost",
    "port_range": [9876, 9878],
    "pipe_name": "/var/run/kos/runtime/kadcm/kadcm.pipe",
    "tls_enabled": true,
    "cert_file": "/etc/kos/kadcm.crt",
    "key_file": "/etc/kos/kadcm.key",
    "heartbeat_interval": 30,
    "session_timeout": 300,
    "max_connections": 100
}
EOF

# KAIM config
cat > /etc/kos/kaim.conf << EOF
{
    "max_elevation_duration": 3600,
    "require_fingerprint": true,
    "allowed_devices": ["null", "zero", "random", "urandom"],
    "restricted_flags": ["KROOT"],
    "audit_all": true,
    "socket_path": "/var/run/kaim.sock"
}
EOF

# Set permissions
chmod 600 /etc/kos/kadcm.conf
chmod 600 /etc/kos/kaim.conf
chown kos:kos /etc/kos/kadcm.conf
chown _kaim:kaim /etc/kos/kaim.conf

echo -e "${GREEN}Configuration files created${NC}"

# Step 7: Generate self-signed certificates for KADCM
echo -e "\n${YELLOW}Step 7: Generating TLS certificates...${NC}"

if ! [ -f /etc/kos/kadcm.crt ]; then
    openssl req -x509 -newkey rsa:4096 -keyout /etc/kos/kadcm.key -out /etc/kos/kadcm.crt \
        -days 365 -nodes -subj "/C=US/ST=State/L=City/O=KOS/CN=kadcm.kos.local"
    
    chmod 600 /etc/kos/kadcm.key
    chmod 644 /etc/kos/kadcm.crt
    chown kos:kos /etc/kos/kadcm.key /etc/kos/kadcm.crt
    
    echo -e "${GREEN}TLS certificates generated${NC}"
else
    echo -e "${YELLOW}Certificates already exist, skipping...${NC}"
fi

# Step 8: Enable and start services
echo -e "\n${YELLOW}Step 8: Service management...${NC}"

echo "Enabling services..."
systemctl enable kadcm.service
systemctl enable kaim.service

echo -e "\n${GREEN}Installation complete!${NC}"
echo -e "\nTo start the services, run:"
echo -e "  ${YELLOW}systemctl start kaim${NC}"
echo -e "  ${YELLOW}systemctl start kadcm${NC}"
echo -e "\nTo check service status:"
echo -e "  ${YELLOW}systemctl status kaim${NC}"
echo -e "  ${YELLOW}systemctl status kadcm${NC}"
echo -e "\nTo view logs:"
echo -e "  ${YELLOW}journalctl -u kaim -f${NC}"
echo -e "  ${YELLOW}journalctl -u kadcm -f${NC}"

# Optional: Start services now
read -p "Start services now? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Starting KAIM..."
    systemctl start kaim
    sleep 2
    
    echo "Starting KADCM..."
    systemctl start kadcm
    sleep 2
    
    echo -e "\n${YELLOW}Service Status:${NC}"
    systemctl status kaim --no-pager || true
    echo
    systemctl status kadcm --no-pager || true
fi

echo -e "\n${GREEN}Installation script completed!${NC}"