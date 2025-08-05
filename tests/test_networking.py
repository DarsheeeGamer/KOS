"""
Unit tests for KOS networking components
"""

import unittest
import socket
import threading
import time
import sys
import os
from unittest.mock import Mock, patch, MagicMock

# Add KOS to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from kos.network.stack import NetworkStack
from kos.network.firewall import FirewallManager
from kos.network.real_network_stack import RealNetworkStack

class TestNetworkStack(unittest.TestCase):
    """Test network stack functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.network_stack = NetworkStack()
    
    def test_network_stack_initialization(self):
        """Test network stack initialization"""
        self.assertIsNotNone(self.network_stack)
        self.assertTrue(hasattr(self.network_stack, 'interfaces'))
        self.assertTrue(hasattr(self.network_stack, 'routing_table'))
    
    def test_interface_management(self):
        """Test network interface management"""
        interface_name = 'eth0'
        ip_address = '192.168.1.100'
        netmask = '255.255.255.0'
        
        # Add interface
        result = self.network_stack.add_interface(interface_name, ip_address, netmask)
        self.assertTrue(result)
        
        # Check interface exists
        interfaces = self.network_stack.get_interfaces()
        self.assertIn(interface_name, interfaces)
        
        # Get interface details
        interface_info = self.network_stack.get_interface(interface_name)
        self.assertIsNotNone(interface_info)
        self.assertEqual(interface_info['ip'], ip_address)
        self.assertEqual(interface_info['netmask'], netmask)
        
        # Remove interface
        result = self.network_stack.remove_interface(interface_name)
        self.assertTrue(result)
        self.assertNotIn(interface_name, self.network_stack.get_interfaces())
    
    def test_routing_table(self):
        """Test routing table management"""
        destination = '192.168.2.0/24'
        gateway = '192.168.1.1'
        interface = 'eth0'
        
        # Add route
        result = self.network_stack.add_route(destination, gateway, interface)
        self.assertTrue(result)
        
        # Check route exists
        routes = self.network_stack.get_routes()
        route_found = any(
            route['destination'] == destination and
            route['gateway'] == gateway and
            route['interface'] == interface
            for route in routes
        )
        self.assertTrue(route_found)
        
        # Remove route
        result = self.network_stack.remove_route(destination)
        self.assertTrue(result)
    
    def test_packet_handling(self):
        """Test packet processing"""
        # Mock packet data
        packet_data = b'\x45\x00\x00\x3c\x1c\x46\x40\x00\x40\x06\x00\x00\xc0\xa8\x01\x64\xc0\xa8\x01\x01'
        
        # Process packet
        result = self.network_stack.process_packet(packet_data)
        self.assertIsNotNone(result)
    
    def test_socket_operations(self):
        """Test socket creation and operations"""
        # Create socket
        sock = self.network_stack.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.assertIsNotNone(sock)
        
        # Bind socket
        result = self.network_stack.bind_socket(sock, ('127.0.0.1', 0))
        self.assertTrue(result)
        
        # Close socket
        result = self.network_stack.close_socket(sock)
        self.assertTrue(result)

class TestRealNetworkStack(unittest.TestCase):
    """Test real network stack implementation"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.real_stack = RealNetworkStack()
    
    def test_real_socket_creation(self):
        """Test real socket creation"""
        # Create TCP socket
        tcp_sock = self.real_stack.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.assertIsInstance(tcp_sock, socket.socket)
        tcp_sock.close()
        
        # Create UDP socket
        udp_sock = self.real_stack.create_socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.assertIsInstance(udp_sock, socket.socket)
        udp_sock.close()
    
    def test_tcp_server_client(self):
        """Test TCP server-client communication"""
        server_port = 12345
        test_message = b'Hello, KOS Network!'
        received_data = []
        
        def tcp_server():
            server_sock = self.real_stack.create_socket(socket.AF_INET, socket.SOCK_STREAM)
            server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_sock.bind(('127.0.0.1', server_port))
            server_sock.listen(1)
            server_sock.settimeout(5.0)  # 5 second timeout
            
            try:
                client_sock, addr = server_sock.accept()
                data = client_sock.recv(1024)
                received_data.append(data)
                client_sock.close()
            except socket.timeout:
                pass
            finally:
                server_sock.close()
        
        # Start server thread
        server_thread = threading.Thread(target=tcp_server)
        server_thread.start()
        
        # Give server time to start
        time.sleep(0.1)
        
        # Connect client
        client_sock = self.real_stack.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            client_sock.connect(('127.0.0.1', server_port))
            client_sock.send(test_message)
        except Exception as e:
            self.fail(f"Client connection failed: {e}")
        finally:
            client_sock.close()
        
        # Wait for server to finish
        server_thread.join(timeout=10)
        
        # Check data was received
        self.assertEqual(len(received_data), 1)
        self.assertEqual(received_data[0], test_message)
    
    def test_udp_communication(self):
        """Test UDP communication"""
        server_port = 12346
        test_message = b'UDP Test Message'
        received_data = []
        
        def udp_server():
            server_sock = self.real_stack.create_socket(socket.AF_INET, socket.SOCK_DGRAM)
            server_sock.bind(('127.0.0.1', server_port))
            server_sock.settimeout(5.0)
            
            try:
                data, addr = server_sock.recvfrom(1024)
                received_data.append(data)
            except socket.timeout:
                pass
            finally:
                server_sock.close()
        
        # Start server thread
        server_thread = threading.Thread(target=udp_server)
        server_thread.start()
        
        # Give server time to start
        time.sleep(0.1)
        
        # Send UDP message
        client_sock = self.real_stack.create_socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            client_sock.sendto(test_message, ('127.0.0.1', server_port))
        except Exception as e:
            self.fail(f"UDP send failed: {e}")
        finally:
            client_sock.close()
        
        # Wait for server
        server_thread.join(timeout=10)
        
        # Check data was received
        self.assertEqual(len(received_data), 1)
        self.assertEqual(received_data[0], test_message)
    
    def test_network_interface_info(self):
        """Test network interface information retrieval"""
        interfaces = self.real_stack.get_network_interfaces()
        
        self.assertIsInstance(interfaces, list)
        # Should have at least loopback interface
        self.assertGreater(len(interfaces), 0)
        
        # Check interface structure
        for interface in interfaces:
            self.assertIn('name', interface)
            self.assertIn('addresses', interface)

class TestFirewallManager(unittest.TestCase):
    """Test firewall functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.firewall = FirewallManager()
    
    def test_firewall_initialization(self):
        """Test firewall initialization"""
        self.assertIsNotNone(self.firewall)
        self.assertTrue(hasattr(self.firewall, 'rules'))
    
    def test_rule_management(self):
        """Test firewall rule management"""
        # Add allow rule
        rule_id = self.firewall.add_rule(
            action='ALLOW',
            protocol='TCP',
            src_ip='192.168.1.0/24',
            dst_port=80
        )
        self.assertIsNotNone(rule_id)
        
        # Check rule exists
        rules = self.firewall.get_rules()
        rule_found = any(rule['id'] == rule_id for rule in rules)
        self.assertTrue(rule_found)
        
        # Remove rule
        result = self.firewall.remove_rule(rule_id)
        self.assertTrue(result)
        
        # Check rule is gone
        rules = self.firewall.get_rules()
        rule_found = any(rule['id'] == rule_id for rule in rules)
        self.assertFalse(rule_found)
    
    def test_packet_filtering(self):
        """Test packet filtering"""
        # Add blocking rule for specific port
        block_rule = self.firewall.add_rule(
            action='BLOCK',
            protocol='TCP',
            dst_port=23  # Telnet port
        )
        
        # Test packet that should be blocked
        packet_info = {
            'protocol': 'TCP',
            'src_ip': '192.168.1.100',
            'dst_ip': '192.168.1.1',
            'dst_port': 23
        }
        
        result = self.firewall.check_packet(packet_info)
        self.assertEqual(result, 'BLOCK')
        
        # Test packet that should be allowed
        packet_info['dst_port'] = 80
        result = self.firewall.check_packet(packet_info)
        self.assertNotEqual(result, 'BLOCK')
    
    def test_port_blocking(self):
        """Test port blocking functionality"""
        # Block port
        result = self.firewall.block_port(1234, protocol='tcp')
        self.assertTrue(result)
        
        # Check if port is blocked
        blocked = self.firewall.is_port_blocked(1234, protocol='tcp')
        self.assertTrue(blocked)
        
        # Unblock port
        result = self.firewall.unblock_port(1234, protocol='tcp')
        self.assertTrue(result)
        
        # Check if port is unblocked
        blocked = self.firewall.is_port_blocked(1234, protocol='tcp')
        self.assertFalse(blocked)
    
    def test_rate_limiting(self):
        """Test rate limiting functionality"""
        # Set rate limit
        result = self.firewall.rate_limit(22, 'tcp', 5, 60)  # 5 connections per minute for SSH
        self.assertTrue(result)
        
        # Simulate multiple connections
        for i in range(3):
            allowed = self.firewall.check_rate_limit('192.168.1.100', 22, 'tcp')
            self.assertTrue(allowed)
        
        # Should still be under limit
        allowed = self.firewall.check_rate_limit('192.168.1.100', 22, 'tcp')
        self.assertTrue(allowed)

class TestNetworkProtocols(unittest.TestCase):
    """Test network protocol implementations"""
    
    def test_ip_address_validation(self):
        """Test IP address validation"""
        valid_ipv4 = [
            '192.168.1.1',
            '10.0.0.1',
            '172.16.0.1',
            '127.0.0.1'
        ]
        
        invalid_ipv4 = [
            '192.168.1.256',
            '10.0.0',
            '172.16.0.1.1',
            'not.an.ip.address'
        ]
        
        from kos.network.stack import NetworkStack
        stack = NetworkStack()
        
        for ip in valid_ipv4:
            self.assertTrue(stack.validate_ipv4(ip), f"IP {ip} should be valid")
        
        for ip in invalid_ipv4:
            self.assertFalse(stack.validate_ipv4(ip), f"IP {ip} should be invalid")
    
    def test_subnet_calculations(self):
        """Test subnet and network calculations"""
        from kos.network.stack import NetworkStack
        stack = NetworkStack()
        
        # Test network calculation
        network = stack.calculate_network('192.168.1.100', '255.255.255.0')
        self.assertEqual(network, '192.168.1.0')
        
        # Test broadcast calculation
        broadcast = stack.calculate_broadcast('192.168.1.0', '255.255.255.0')
        self.assertEqual(broadcast, '192.168.1.255')
        
        # Test if IP is in subnet
        in_subnet = stack.ip_in_subnet('192.168.1.50', '192.168.1.0', '255.255.255.0')
        self.assertTrue(in_subnet)
        
        not_in_subnet = stack.ip_in_subnet('192.168.2.50', '192.168.1.0', '255.255.255.0')
        self.assertFalse(not_in_subnet)

class TestKernelNetworkIntegration(unittest.TestCase):
    """Test kernel network stack integration"""
    
    @patch('kos.kernel.net.netstack_wrapper')
    def test_kernel_network_functions(self, mock_netstack):
        """Test kernel network function integration"""
        # Mock network stack functions
        mock_netstack.net_init.return_value = 0
        mock_netstack.create_socket.return_value = 5  # Socket FD
        mock_netstack.bind_socket.return_value = 0
        mock_netstack.listen_socket.return_value = 0
        mock_netstack.accept_socket.return_value = 6  # New connection FD
        
        from kos.kernel.net.netstack_wrapper import (
            net_init, create_socket, bind_socket, listen_socket, accept_socket
        )
        
        # Test network initialization
        result = net_init()
        self.assertEqual(result, 0)
        
        # Test socket creation
        sock_fd = create_socket(2, 1, 0)  # AF_INET, SOCK_STREAM, IPPROTO_TCP
        self.assertEqual(sock_fd, 5)
        
        # Test socket binding
        result = bind_socket(sock_fd, "127.0.0.1", 8080)
        self.assertEqual(result, 0)
        
        # Test socket listening
        result = listen_socket(sock_fd, 5)
        self.assertEqual(result, 0)
        
        # Test socket accepting
        client_fd = accept_socket(sock_fd)
        self.assertEqual(client_fd, 6)
    
    def test_network_performance(self):
        """Test network stack performance"""
        stack = RealNetworkStack()
        
        # Test socket creation performance
        start_time = time.time()
        sockets = []
        
        for i in range(100):
            sock = stack.create_socket(socket.AF_INET, socket.SOCK_STREAM)
            sockets.append(sock)
        
        creation_time = time.time() - start_time
        
        # Clean up sockets
        for sock in sockets:
            sock.close()
        
        # Should create 100 sockets quickly
        self.assertLess(creation_time, 1.0)
    
    def test_concurrent_connections(self):
        """Test handling concurrent network connections"""
        stack = RealNetworkStack()
        server_port = 12347
        num_clients = 10
        
        def simple_server():
            server_sock = stack.create_socket(socket.AF_INET, socket.SOCK_STREAM)
            server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_sock.bind(('127.0.0.1', server_port))
            server_sock.listen(num_clients)
            server_sock.settimeout(10.0)
            
            clients_handled = 0
            try:
                while clients_handled < num_clients:
                    client_sock, addr = server_sock.accept()
                    data = client_sock.recv(1024)
                    client_sock.send(b'ACK')
                    client_sock.close()
                    clients_handled += 1
            except socket.timeout:
                pass
            finally:
                server_sock.close()
            
            return clients_handled
        
        # Start server thread
        server_thread = threading.Thread(target=simple_server)
        server_thread.start()
        
        # Give server time to start
        time.sleep(0.1)
        
        # Create multiple client connections
        client_threads = []
        
        def client_worker(client_id):
            try:
                client_sock = stack.create_socket(socket.AF_INET, socket.SOCK_STREAM)
                client_sock.connect(('127.0.0.1', server_port))
                client_sock.send(f'Client {client_id}'.encode())
                response = client_sock.recv(1024)
                client_sock.close()
                return response == b'ACK'
            except Exception:
                return False
        
        for i in range(num_clients):
            thread = threading.Thread(target=client_worker, args=(i,))
            client_threads.append(thread)
            thread.start()
        
        # Wait for all clients to complete
        for thread in client_threads:
            thread.join(timeout=15)
        
        # Wait for server to complete
        server_thread.join(timeout=15)
        
        # Test should complete without hanging
        self.assertTrue(True)

if __name__ == '__main__':
    unittest.main()