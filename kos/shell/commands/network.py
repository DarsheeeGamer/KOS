"""
Network commands for KOS Shell
"""

import types
import time
from typing import Optional

def register_commands(shell):
    """Register network commands with shell"""
    
    # Initialize network components if needed
    def _init_network(self):
        if not hasattr(self, 'network_manager'):
            from kos.network import NetworkManager, DNSResolver, HTTPClient
            self.network_manager = NetworkManager(self.vfs)
            self.dns_resolver = DNSResolver(self.vfs)
            self.http_client = HTTPClient(self.dns_resolver)
    
    def do_ifconfig(self, arg):
        """Configure network interface
        Usage: 
            ifconfig              - Show all interfaces
            ifconfig <interface>  - Show specific interface
            ifconfig <interface> <ip> <netmask> - Set IP address"""
        
        _init_network(self)
        
        args = arg.split()
        
        if not args:
            # Show all interfaces
            interfaces = self.network_manager.list_interfaces()
            for iface in interfaces:
                print(f"{iface.name}: flags=<{iface.state.value.upper()}> mtu {iface.mtu}")
                if iface.mac_address != "00:00:00:00:00:00":
                    print(f"        ether {iface.mac_address}")
                if iface.ip_address != "0.0.0.0":
                    print(f"        inet {iface.ip_address} netmask {iface.netmask}")
                if iface.gateway:
                    print(f"        gateway {iface.gateway}")
                print(f"        RX packets {iface.rx_packets} bytes {iface.rx_bytes}")
                print(f"        TX packets {iface.tx_packets} bytes {iface.tx_bytes}")
                print()
        
        elif len(args) == 1:
            # Show specific interface
            iface = self.network_manager.get_interface(args[0])
            if iface:
                print(f"{iface.name}: flags=<{iface.state.value.upper()}> mtu {iface.mtu}")
                print(f"        inet {iface.ip_address} netmask {iface.netmask}")
                if iface.gateway:
                    print(f"        gateway {iface.gateway}")
            else:
                print(f"ifconfig: interface {args[0]} does not exist")
        
        elif len(args) >= 3:
            # Set IP address
            interface = args[0]
            ip = args[1]
            netmask = args[2] if len(args) > 2 else "255.255.255.0"
            
            if self.network_manager.set_ip(interface, ip, netmask):
                print(f"Interface {interface} configured")
            else:
                print(f"Failed to configure {interface}")
    
    def do_ip(self, arg):
        """IP configuration utility
        Usage:
            ip addr          - Show addresses
            ip route         - Show routes
            ip link          - Show links"""
        
        _init_network(self)
        
        if arg.startswith("addr"):
            # Show addresses
            interfaces = self.network_manager.list_interfaces()
            for i, iface in enumerate(interfaces, 1):
                print(f"{i}: {iface.name}: <{iface.state.value.upper()}> mtu {iface.mtu}")
                if iface.mac_address != "00:00:00:00:00:00":
                    print(f"    link/ether {iface.mac_address}")
                if iface.ip_address != "0.0.0.0":
                    print(f"    inet {iface.ip_address}/{self._netmask_to_cidr(iface.netmask)}")
        
        elif arg.startswith("route"):
            # Show routes
            routes = self.network_manager.get_routes()
            print("Destination     Gateway         Netmask         Interface")
            for route in routes:
                print(f"{route.destination:<15} {route.gateway:<15} {route.netmask:<15} {route.interface}")
        
        elif arg.startswith("link"):
            # Show links
            interfaces = self.network_manager.list_interfaces()
            for iface in interfaces:
                state = "UP" if iface.state.value == "up" else "DOWN"
                print(f"{iface.name}: <{state}> mtu {iface.mtu}")
        
        else:
            print("Usage: ip [addr|route|link]")
    
    def _netmask_to_cidr(self, netmask):
        """Convert netmask to CIDR notation"""
        cidr_map = {
            "255.255.255.255": "32",
            "255.255.255.0": "24", 
            "255.255.0.0": "16",
            "255.0.0.0": "8",
            "0.0.0.0": "0"
        }
        return cidr_map.get(netmask, "24")
    
    def do_ping(self, arg):
        """Ping a host
        Usage: ping [-c count] <host>"""
        
        _init_network(self)
        
        if not arg:
            print("Usage: ping [-c count] <host>")
            return
        
        args = arg.split()
        count = 4
        host = args[-1]
        
        # Parse options
        if len(args) > 1 and args[0] == "-c":
            try:
                count = int(args[1])
                host = args[2] if len(args) > 2 else ""
            except:
                print("ping: invalid count")
                return
        
        if not host:
            print("Usage: ping [-c count] <host>")
            return
        
        # Resolve hostname if needed
        ip = host
        if not self.network_manager._is_ip(host):
            ip = self.dns_resolver.resolve(host)
            if not ip:
                print(f"ping: cannot resolve {host}: Unknown host")
                return
            print(f"PING {host} ({ip}): 56 data bytes")
        else:
            print(f"PING {ip}: 56 data bytes")
        
        # Perform ping
        success, times = self.network_manager.ping(host, count)
        
        if success:
            for i, rtt in enumerate(times):
                print(f"64 bytes from {ip}: icmp_seq={i} ttl=64 time={rtt*1000:.1f} ms")
            
            # Statistics
            print(f"\n--- {host} ping statistics ---")
            print(f"{count} packets transmitted, {len(times)} packets received, 0.0% packet loss")
            if times:
                avg_time = sum(times) / len(times) * 1000
                min_time = min(times) * 1000
                max_time = max(times) * 1000
                print(f"round-trip min/avg/max = {min_time:.1f}/{avg_time:.1f}/{max_time:.1f} ms")
        else:
            for i in range(count):
                print(f"Request timeout for icmp_seq {i}")
            print(f"\n--- {host} ping statistics ---")
            print(f"{count} packets transmitted, 0 packets received, 100.0% packet loss")
    
    def do_traceroute(self, arg):
        """Trace route to host
        Usage: traceroute <host>"""
        
        _init_network(self)
        
        if not arg:
            print("Usage: traceroute <host>")
            return
        
        host = arg.strip()
        
        # Resolve hostname
        ip = host
        if not self.network_manager._is_ip(host):
            ip = self.dns_resolver.resolve(host)
            if not ip:
                print(f"traceroute: cannot resolve {host}: Unknown host")
                return
        
        print(f"traceroute to {host} ({ip}), 30 hops max")
        
        # Simulate traceroute
        hops = [
            ("192.168.1.1", "gateway.local", [1.2, 1.1, 1.3]),
            ("10.0.0.1", "isp-router.net", [5.2, 5.5, 5.1]),
            ("172.16.0.1", "core-router.net", [10.3, 10.1, 10.5]),
            (ip, host, [15.2, 15.5, 15.1])
        ]
        
        for i, (hop_ip, hop_name, times) in enumerate(hops, 1):
            times_str = " ".join(f"{t:.1f} ms" for t in times)
            print(f" {i}  {hop_name} ({hop_ip})  {times_str}")
            time.sleep(0.1)
    
    def do_nslookup(self, arg):
        """DNS lookup
        Usage: nslookup <hostname>"""
        
        _init_network(self)
        
        if not arg:
            print("Usage: nslookup <hostname>")
            return
        
        hostname = arg.strip()
        
        print(f"Server:     {self.dns_resolver.nameservers[0]}")
        print(f"Address:    {self.dns_resolver.nameservers[0]}#53")
        print()
        
        # Perform lookup
        ip = self.dns_resolver.resolve(hostname)
        
        if ip:
            print(f"Name:       {hostname}")
            print(f"Address:    {ip}")
        else:
            print(f"** server can't find {hostname}: NXDOMAIN")
    
    def do_dig(self, arg):
        """DNS lookup tool
        Usage: dig <hostname> [type]"""
        
        _init_network(self)
        
        if not arg:
            print("Usage: dig <hostname> [type]")
            return
        
        args = arg.split()
        hostname = args[0]
        record_type = args[1] if len(args) > 1 else "A"
        
        print(f"; <<>> KOS-Dig 1.0 <<>> {hostname}")
        print(f";; global options: +cmd")
        
        # Perform lookup
        ip = self.dns_resolver.resolve(hostname, record_type)
        
        if ip:
            print(f";; ANSWER SECTION:")
            print(f"{hostname}.\t\t300\tIN\t{record_type}\t{ip}")
            print()
            print(f";; Query time: 25 msec")
            print(f";; SERVER: {self.dns_resolver.nameservers[0]}#53")
            print(f";; MSG SIZE  rcvd: 44")
        else:
            print(f";; connection timed out; no servers could be reached")
    
    def do_host(self, arg):
        """DNS lookup utility
        Usage: host <hostname|ip>"""
        
        _init_network(self)
        
        if not arg:
            print("Usage: host <hostname|ip>")
            return
        
        target = arg.strip()
        
        # Check if it's an IP (reverse lookup)
        if self.network_manager._is_ip(target):
            hostname = self.dns_resolver.reverse_lookup(target)
            if hostname:
                print(f"{target} domain name pointer {hostname}")
            else:
                print(f"Host {target} not found: 3(NXDOMAIN)")
        else:
            # Forward lookup
            ip = self.dns_resolver.resolve(target)
            if ip:
                print(f"{target} has address {ip}")
            else:
                print(f"Host {target} not found: 3(NXDOMAIN)")
    
    def do_curl(self, arg):
        """Transfer data from URL
        Usage: curl [-o output] <url>"""
        
        _init_network(self)
        
        if not arg:
            print("Usage: curl [-o output] <url>")
            return
        
        args = arg.split()
        output_file = None
        url = args[-1]
        
        # Parse options
        if len(args) > 1 and args[0] == "-o":
            output_file = args[1]
            url = args[2] if len(args) > 2 else ""
        
        if not url:
            print("curl: no URL specified")
            return
        
        # Add http:// if no scheme
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "http://" + url
        
        # Make request
        print(f"  % Total    % Received  Time")
        print(f"  0          0          --:--:--")
        
        response = self.http_client.get(url)
        
        if response.status_code == 200:
            if output_file:
                # Save to file
                try:
                    with self.vfs.open(output_file, 'w') as f:
                        f.write(response.body.encode())
                    print(f"100        100        {response.elapsed:.2f}s")
                    print(f"Saved to {output_file}")
                except Exception as e:
                    print(f"curl: {e}")
            else:
                # Print to stdout
                print(response.body)
        else:
            print(f"curl: HTTP {response.status_code}")
    
    def do_wget(self, arg):
        """Download files from web
        Usage: wget [-O output] <url>"""
        
        _init_network(self)
        
        if not arg:
            print("Usage: wget [-O output] <url>")
            return
        
        args = arg.split()
        output_file = None
        url = args[-1]
        
        # Parse options
        if len(args) > 1 and args[0] == "-O":
            output_file = args[1]
            url = args[2] if len(args) > 2 else ""
        
        if not url:
            print("wget: missing URL")
            return
        
        # Add http:// if no scheme
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "http://" + url
        
        # Determine output filename
        if not output_file:
            # Extract filename from URL
            parts = url.split("/")
            output_file = parts[-1] if parts[-1] else "index.html"
        
        print(f"--{time.strftime('%Y-%m-%d %H:%M:%S')}--  {url}")
        print(f"Resolving {url.split('/')[2]}...")
        print(f"Connecting to {url.split('/')[2]}... connected.")
        print(f"HTTP request sent, awaiting response...")
        
        # Download
        response = self.http_client.get(url)
        
        if response.status_code == 200:
            try:
                with self.vfs.open(output_file, 'w') as f:
                    f.write(response.body.encode())
                print(f"200 OK")
                print(f"Length: {len(response.body)} [{response.headers.get('Content-Type', 'text/html')}]")
                print(f"Saving to: '{output_file}'")
                print(f"\n100%[{'='*50}>] {len(response.body):,}  --.-KB/s    in {response.elapsed:.1f}s")
                print(f"\n'{output_file}' saved [{len(response.body)}/{len(response.body)}]")
            except Exception as e:
                print(f"wget: {e}")
        else:
            print(f"HTTP {response.status_code}")
            print(f"ERROR {response.status_code}: Download failed.")
    
    def do_netstat(self, arg):
        """Network connections and statistics
        Usage: netstat [-a] [-n] [-t] [-u]"""
        
        _init_network(self)
        
        print("Active Internet connections")
        print("Proto  Local Address          Foreign Address        State")
        
        # Simulate some connections
        connections = [
            ("tcp", "0.0.0.0:22", "0.0.0.0:*", "LISTEN"),
            ("tcp", "127.0.0.1:3306", "0.0.0.0:*", "LISTEN"),
            ("tcp", "192.168.1.100:43212", "142.250.185.46:443", "ESTABLISHED"),
            ("udp", "0.0.0.0:53", "0.0.0.0:*", ""),
            ("udp", "0.0.0.0:68", "0.0.0.0:*", "")
        ]
        
        for proto, local, foreign, state in connections:
            print(f"{proto:<6} {local:<22} {foreign:<22} {state}")
    
    def do_ss(self, arg):
        """Socket statistics
        Usage: ss [-t] [-u] [-l] [-a]"""
        
        _init_network(self)
        
        print("State      Recv-Q Send-Q  Local Address:Port   Peer Address:Port")
        
        # Simulate socket info
        sockets = [
            ("LISTEN", 0, 128, "*:22", "*:*"),
            ("LISTEN", 0, 128, "127.0.0.1:3306", "*:*"),
            ("ESTAB", 0, 0, "192.168.1.100:43212", "142.250.185.46:443")
        ]
        
        for state, recv_q, send_q, local, peer in sockets:
            print(f"{state:<10} {recv_q:<6} {send_q:<6}  {local:<20} {peer}")
    
    def do_route(self, arg):
        """Show/manipulate routing table
        Usage:
            route              - Show routing table
            route add <dest> gw <gateway>  - Add route
            route del <dest>               - Delete route"""
        
        _init_network(self)
        
        args = arg.split()
        
        if not args:
            # Show routes
            print("Kernel IP routing table")
            print("Destination     Gateway         Genmask         Flags Metric Ref    Use Iface")
            
            routes = self.network_manager.get_routes()
            for route in routes:
                flags = "UG" if route.gateway != "0.0.0.0" else "U"
                print(f"{route.destination:<15} {route.gateway:<15} {route.netmask:<15} {flags:<5} "
                      f"{route.metric:<6} 0      0 {route.interface}")
        
        elif args[0] == "add" and len(args) >= 4:
            # Add route
            dest = args[1]
            if args[2] == "gw":
                gateway = args[3]
                interface = args[4] if len(args) > 4 else "eth0"
                
                if self.network_manager.add_route(dest, gateway, interface=interface):
                    print(f"Route added: {dest} via {gateway}")
                else:
                    print("Failed to add route")
        
        elif args[0] == "del" and len(args) >= 2:
            # Delete route
            dest = args[1]
            if self.network_manager.delete_route(dest):
                print(f"Route deleted: {dest}")
            else:
                print("Failed to delete route")
        
        else:
            print("Usage: route [add <dest> gw <gateway>|del <dest>]")
    
    def do_arp(self, arg):
        """ARP table manipulation
        Usage: arp [-a]"""
        
        _init_network(self)
        
        print("Address                  HWtype  HWaddress           Flags Mask            Iface")
        
        # Simulate ARP entries
        arp_entries = [
            ("192.168.1.1", "ether", "00:11:22:33:44:55", "C", "eth0"),
            ("192.168.1.50", "ether", "aa:bb:cc:dd:ee:ff", "C", "eth0")
        ]
        
        for ip, hwtype, mac, flags, iface in arp_entries:
            print(f"{ip:<24} {hwtype:<7} {mac:<19} {flags:<5}               {iface}")
    
    def do_hostname(self, arg):
        """Show or set system hostname
        Usage:
            hostname          - Show hostname
            hostname <name>   - Set hostname"""
        
        _init_network(self)
        
        if arg:
            # Set hostname
            if self.network_manager.set_hostname(arg):
                print(f"Hostname set to: {arg}")
            else:
                print("Failed to set hostname")
        else:
            # Get hostname
            print(self.network_manager.hostname)
    
    # Register commands using MethodType
    shell.do_ifconfig = types.MethodType(do_ifconfig, shell)
    shell.do_ip = types.MethodType(do_ip, shell)
    shell._netmask_to_cidr = types.MethodType(_netmask_to_cidr, shell)
    shell.do_ping = types.MethodType(do_ping, shell)
    shell.do_traceroute = types.MethodType(do_traceroute, shell)
    shell.do_nslookup = types.MethodType(do_nslookup, shell)
    shell.do_dig = types.MethodType(do_dig, shell)
    shell.do_host = types.MethodType(do_host, shell)
    shell.do_curl = types.MethodType(do_curl, shell)
    shell.do_wget = types.MethodType(do_wget, shell)
    shell.do_netstat = types.MethodType(do_netstat, shell)
    shell.do_ss = types.MethodType(do_ss, shell)
    shell.do_route = types.MethodType(do_route, shell)
    shell.do_arp = types.MethodType(do_arp, shell)
    
    # Note: hostname already registered in system commands, so skip it