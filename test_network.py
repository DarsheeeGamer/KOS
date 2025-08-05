#!/usr/bin/env python3
"""
Test network stack implementation
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_network_stack():
    from kos.network.stack import KOSNetworkStack
    
    print("Testing network stack...")
    
    # Create network stack (mock kernel)
    class MockKernel:
        pass
    
    network = KOSNetworkStack(MockKernel())
    network.start()
    
    # Test interface creation
    print("Testing interface creation...")
    lo = network.create_interface('lo', '127.0.0.1')
    eth0 = network.create_interface('eth0', '192.168.1.100')
    network.interface_up('lo')
    network.interface_up('eth0')
    
    interfaces = network.get_interfaces()
    assert 'lo' in interfaces
    assert 'eth0' in interfaces
    assert interfaces['lo'].ip == '127.0.0.1'
    assert interfaces['eth0'].ip == '192.168.1.100'
    print("✓ Interface creation works")
    
    # Test routing
    print("Testing routing...")
    network.add_route('0.0.0.0', '192.168.1.1', '0.0.0.0', 'eth0')
    routes = network.get_routes()
    assert len(routes) >= 2  # Local routes + default route
    print("✓ Routing works")
    
    # Test ping simulation
    print("Testing ping simulation...")
    ping_result = network.ping('127.0.0.1', count=2)
    assert ping_result['target'] == '127.0.0.1'
    assert ping_result['packets_sent'] == 2
    print("✓ Ping simulation works")
    
    # Test DNS resolution
    print("Testing DNS resolution...")
    localhost_ip = network.resolve_hostname('localhost')
    assert localhost_ip == '127.0.0.1'
    google_ip = network.resolve_hostname('google.com')
    assert google_ip == '172.217.14.14'
    print("✓ DNS resolution works")
    
    # Test network stats
    print("Testing network statistics...")
    stats = network.get_network_stats()
    assert 'interfaces' in stats
    assert 'lo' in stats['interfaces']
    assert 'eth0' in stats['interfaces']
    print("✓ Network statistics work")
    
    # Test traceroute
    print("Testing traceroute...")
    trace = network.traceroute('127.0.0.1')
    assert len(trace) >= 1
    assert trace[-1]['ip'] == '127.0.0.1'
    print("✓ Traceroute works")
    
    network.stop()
    print("All network tests passed!")

if __name__ == "__main__":
    test_network_stack()