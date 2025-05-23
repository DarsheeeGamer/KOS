# Networking Guide

This guide covers networking configuration, management, and troubleshooting in KOS.

## Network Configuration

### View Network Interfaces

List all network interfaces:

```bash
ifconfig
```

Or use the newer command:

```bash
ip addr show
```

### Configure Network Interface

Temporarily configure an interface:

```bash
ifconfig eth0 192.168.1.100 netmask 255.255.255.0 up
```

Or using the ip command:

```bash
ip addr add 192.168.1.100/24 dev eth0
ip link set eth0 up
```

### Set Default Gateway

```bash
route add default gw 192.168.1.1
```

Or:

```bash
ip route add default via 192.168.1.1
```

### Configure DNS

Edit the resolv.conf file:

```bash
echo "nameserver 8.8.8.8" > /etc/resolv.conf
```

## Network Testing

### Test Connectivity

Ping a host:

```bash
ping example.com
```

### Trace Route

Trace the route to a host:

```bash
traceroute example.com
```

Or:

```bash
tracepath example.com
```

### Check Open Ports

List open ports and listening services:

```bash
netstat -tuln
```

Or:

```bash
ss -tuln
```

### Test Port Connectivity

Test if a port is open:

```bash
nc -zv example.com 80
```

## Network Services

### Restart Network Service

Restart the networking service:

```bash
service networking restart
```

### View Service Status

Check status of network services:

```bash
service networking status
```

## Firewall Configuration

### View Firewall Status

```bash
ufw status
```

### Enable/Disable Firewall

```bash
ufw enable
ufw disable
```

### Allow/Deny Ports

```bash
ufw allow 22/tcp
ufw deny 23/tcp
```

## Wireless Networking

### Scan for Networks

```bash
iwlist wlan0 scan
```

### Connect to WPA/WPA2 Network

Using wpa_supplicant:

```bash
wpa_supplicant -i wlan0 -c /etc/wpa_supplicant.conf &
dhclient wlan0
```

## Network Troubleshooting

### Check Network Configuration

```bash
ip a
ip route
cat /etc/resolv.conf
```

### Check Network Connectivity

```bash
ping -c 4 8.8.8.8
ping -c 4 example.com
```

### Check DNS Resolution

```bash
nslookup example.com
dig example.com
```

### Check Network Latency

```bash
mtr example.com
```

## Advanced Networking

### Create Network Bridge

```bash
ip link add name br0 type bridge
ip link set eth0 master br0
ip addr add 192.168.1.100/24 dev br0
ip link set br0 up
```

### Configure VLAN

```bash
ip link add link eth0 name eth0.100 type vlan id 100
ip addr add 192.168.100.100/24 dev eth0.100
ip link set eth0.100 up
```

### Set Up IP Forwarding

Enable IP forwarding:

```bash
echo 1 > /proc/sys/net/ipv4/ip_forward
```

Make it persistent by editing /etc/sysctl.conf:
```
net.ipv4.ip_forward = 1
```

## Network Security

### Check Open Ports

```bash
nmap -sS -O 192.168.1.0/24
```

### Monitor Network Traffic

```bash
tcpdump -i eth0 -n
```

### Check SSL Certificate

```bash
openssl s_client -connect example.com:443 -showcerts
```

## Network Performance

### Test Network Throughput

```bash
iperf -s  # On server
iperf -c server_ip  # On client
```

### Check Bandwidth Usage

```bash
iftop -i eth0
```

## Network Configuration Files

### Important Configuration Files

- `/etc/network/interfaces` - Network interface configuration
- `/etc/resolv.conf` - DNS configuration
- `/etc/hosts` - Static hostname resolution
- `/etc/hostname` - System hostname
- `/etc/iptables/rules.v4` - IPv4 firewall rules
- `/etc/iptables/rules.v6` - IPv6 firewall rules
- `/etc/wpa_supplicant/wpa_supplicant.conf` - WiFi configuration

## Network Time Protocol (NTP)

### Sync System Time

```bash
ntpdate pool.ntp.org
```

### Configure NTP Client

Edit `/etc/ntp.conf` and restart the NTP service:

```bash
service ntp restart
```
