# Networking in KOS

This guide covers network configuration, troubleshooting, and common networking tasks in KOS.

## Table of Contents
- [Network Configuration](#network-configuration)
- [Network Interfaces](#network-interfaces)
- [IP Addressing](#ip-addressing)
- [DNS Configuration](#dns-configuration)
- [Network Testing](#network-testing)
- [Firewall Configuration](#firewall-configuration)
- [VPN and Tunneling](#vpn-and-tunneling)
- [Troubleshooting](#troubleshooting)
- [Best Practices](#best-practices)

## Network Configuration

### Viewing Network Configuration
```bash
# Show all network interfaces
$ ip a
$ ifconfig

# Show routing table
$ ip route
$ route -n

# Show network statistics
$ ss -tulnp
$ netstat -tulnp

# Show active connections
$ ss -tup
$ netstat -tup
```

### Network Manager
```bash
# Check status
$ nmcli general status

# List connections
$ nmcli connection show

# Connect to a network
$ nmcli device wifi connect SSID password PASSWORD

# Disconnect
$ nmcli device disconnect ifname eth0
```

## Network Interfaces

### Managing Interfaces
```bash
# Bring interface up/down
$ sudo ip link set eth0 up
$ sudo ip link set eth0 down

# Assign IP address
$ sudo ip addr add 192.168.1.100/24 dev eth0

# Remove IP address
$ sudo ip addr del 192.168.1.100/24 dev eth0
```

### Interface Configuration Files
```bash
# Static IP configuration (Debian/Ubuntu)
/etc/network/interfaces
auto eth0
iface eth0 inet static
    address 192.168.1.100
    netmask 255.255.255.0
    gateway 192.168.1.1
    dns-nameservers 8.8.8.8 8.8.4.4
```

## IP Addressing

### Static IP Configuration
```bash
# Set static IP
$ sudo ip addr add 192.168.1.100/24 dev eth0

# Set default gateway
$ sudo ip route add default via 192.168.1.1

# Make changes persistent (Debian/Ubuntu)
$ sudo nano /etc/network/interfaces
```

### DHCP Configuration
```bash
# Request IP via DHCP
$ sudo dhclient eth0

# Release DHCP lease
$ sudo dhclient -r eth0
```

## DNS Configuration

### Viewing DNS Settings
```bash
# View DNS configuration
$ cat /etc/resolv.conf

# Test DNS resolution
$ nslookup example.com
$ dig example.com
$ host example.com
```

### Configuring DNS
```bash
# Edit resolv.conf (temporary)
$ sudo nano /etc/resolv.conf
nameserver 8.8.8.8
nameserver 8.8.4.4

# Make DNS changes persistent (Debian/Ubuntu)
$ sudo nano /etc/resolvconf/resolv.conf.d/head
```

## Network Testing

### Basic Connectivity
```bash
# Ping test
$ ping -c 4 8.8.8.8
$ ping -c 4 example.com

# Traceroute
$ traceroute example.com
$ tracepath example.com

# MTR (traceroute + ping)
$ mtr example.com
```

### Port Testing
```bash
# Check if port is open
$ nc -zv example.com 80
$ telnet example.com 80

# Listen on port (for testing)
$ nc -l 1234
```

## Firewall Configuration

### UFW (Uncomplicated Firewall)
```bash
# Install UFW
$ sudo apt install ufw

# Enable/disable firewall
$ sudo ufw enable
$ sudo ufw disable

# Allow/deny services
$ sudo ufw allow ssh
$ sudo ufw allow 80/tcp
$ sudo ufw deny 22/tcp

# View status
$ sudo ufw status
```

### iptables
```bash
# View rules
$ sudo iptables -L -v

# Allow incoming SSH
$ sudo iptables -A INPUT -p tcp --dport 22 -j ACCEPT

# Save rules (Debian/Ubuntu)
$ sudo iptables-save > /etc/iptables/rules.v4
```

## VPN and Tunneling

### OpenVPN
```bash
# Install OpenVPN
$ sudo apt install openvpn

# Connect to VPN
$ sudo openvpn --config client.ovpn
```

### SSH Tunneling
```bash
# Local port forwarding
$ ssh -L 8080:localhost:80 user@example.com

# Remote port forwarding
$ ssh -R 2222:localhost:22 user@example.com

# Dynamic port forwarding (SOCKS proxy)
$ ssh -D 1080 user@example.com
```

## Troubleshooting

### Common Issues

1. **No Network Connectivity**
   ```bash
   # Check physical connection
   $ ip link show
   
   # Check interface status
   $ ip addr show eth0
   
   # Test connectivity
   $ ping 8.8.8.8
   $ ping example.com
   ```

2. **DNS Resolution Issues**
   ```bash
   # Check DNS servers
   $ cat /etc/resolv.conf
   
   # Test DNS resolution
   $ nslookup example.com
   $ dig @8.8.8.8 example.com
   ```

3. **Firewall Blocking Traffic**
   ```bash
   # Check firewall status
   $ sudo ufw status
   $ sudo iptables -L -v
   
   # Check if port is open
   $ nc -zv example.com 80
   ```

4. **Slow Network Performance**
   ```bash
   # Test bandwidth
   $ speedtest-cli
   $ iperf3 -c server-ip
   
   # Check for packet loss
   $ mtr example.com
   ```

## Best Practices

### Network Security
1. Use strong passwords for network services
2. Keep system and network services updated
3. Use SSH key-based authentication
4. Disable root login over SSH
5. Use a firewall to restrict access

### Performance Tuning
```bash
# Increase TCP buffer sizes
$ sudo sysctl -w net.core.rmem_max=26214400
$ sudo sysctl -w net.core.wmem_max=26214400

# Enable TCP window scaling
$ sudo sysctl -w net.ipv4.tcp_window_scaling=1

# Make changes persistent
$ sudo nano /etc/sysctl.conf
```

### Monitoring
```bash
# Monitor network traffic
$ iftop
$ nethogs
$ bmon

# Log network statistics
$ vnstat -l
$ bwm-ng
```

## Advanced Topics

### Network Namespaces
```bash
# Create network namespace
$ sudo ip netns add ns1

# List namespaces
$ ip netns list

# Run command in namespace
$ sudo ip netns exec ns1 ip addr show
```

### VLAN Configuration
```bash
# Create VLAN interface
$ sudo ip link add link eth0 name eth0.100 type vlan id 100

# Bring up VLAN interface
$ sudo ip link set eth0.100 up
$ sudo ip addr add 192.168.100.1/24 dev eth0.100
```

### Bonding (Link Aggregation)
```bash
# Load bonding module
$ sudo modprobe bonding

# Create bond interface
$ sudo ip link add bond0 type bond

# Add slaves
$ sudo ip link set eth0 master bond0
$ sudo ip link set eth1 master bond0

# Configure bond mode
$ echo 4 | sudo tee /sys/class/net/bond0/bonding/mode  # 802.3ad (LACP)
```

## See Also
- [Process Management](./process-management.md)
- [User Management](./user-management.md)
- [File System Guide](./filesystem.md)
