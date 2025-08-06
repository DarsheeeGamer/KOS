#!/usr/bin/env python3
"""
KOS Demo - Showcase all functionality
"""

import sys
import os
import time

# Add KOS to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def demo_klayer():
    """Demonstrate KLayer functionality"""
    print("\n" + "="*60)
    print("KLayer Demo - Core OS Services")
    print("="*60)
    
    from kos.layers.klayer import KLayer
    
    # Initialize KLayer
    klayer = KLayer(disk_file='demo.kdsk')
    
    # 1. User Management
    print("\n1. User Management:")
    print("   Creating users...")
    klayer.user_create('admin', 'admin123', 'admin')
    klayer.user_create('user', 'user123', 'user')
    print("   ✓ Created admin and user accounts")
    
    # 2. File System Operations
    print("\n2. File System Operations:")
    klayer.fs_mkdir('/home/admin')
    klayer.fs_write('/home/admin/test.txt', b'Hello from KLayer!')
    data = klayer.fs_read('/home/admin/test.txt')
    print(f"   ✓ Created file: {data.decode()}")
    
    # 3. Process Management
    print("\n3. Process Management:")
    pid = klayer.process_create('echo', ['Hello World'])
    result = klayer.process_execute(pid)
    print(f"   ✓ Process {pid} executed: {result[1]}")
    
    # 4. System Information
    print("\n4. System Information:")
    sys_info = klayer.sys_info()
    mem_info = klayer.sys_memory_info()
    cpu_info = klayer.sys_cpu_info()
    print(f"   OS: {sys_info['name']} {sys_info['version']}")
    print(f"   Kernel: {sys_info['kernel']}")
    print(f"   CPU: {cpu_info['cores']} cores, {cpu_info['usage']}% usage")
    print(f"   Memory: {mem_info['used']/1024/1024:.0f}MB / {mem_info['total']/1024/1024:.0f}MB")
    
    # 5. Environment Variables
    print("\n5. Environment Variables:")
    klayer.env_set('MY_VAR', 'test_value')
    value = klayer.env_get('MY_VAR')
    print(f"   ✓ Set MY_VAR={value}")
    
    # 6. Permissions
    print("\n6. File Permissions:")
    klayer.perm_chmod('/home/admin/test.txt', 0o644)
    print("   ✓ Changed permissions to 644")
    
    # Cleanup
    klayer.shutdown()
    os.remove('demo.kdsk')
    
    return True

def demo_kadvlayer():
    """Demonstrate KADVLayer functionality"""
    print("\n" + "="*60)
    print("KADVLayer Demo - Advanced Services")
    print("="*60)
    
    from kos.layers.klayer import KLayer
    from kos.layers.kadvlayer import KADVLayer
    
    # Initialize layers
    klayer = KLayer(disk_file='demo_adv.kdsk')
    kadvlayer = KADVLayer(klayer=klayer)
    
    # 1. Network Operations
    print("\n1. Network Operations:")
    print("   Configuring network...")
    kadvlayer.net_configure('eth0', '192.168.1.100', '255.255.255.0')
    print("   ✓ Configured eth0 with IP 192.168.1.100")
    
    # 2. Service Management
    print("\n2. Service Management:")
    kadvlayer.service_create('demo-service', '/usr/bin/demo', 'Demo Service')
    print("   ✓ Created demo-service")
    status = kadvlayer.service_status('demo-service')
    print(f"   Status: {status}")
    
    # 3. Security
    print("\n3. Security Features:")
    kadvlayer.security_firewall_enable()
    kadvlayer.net_firewall_rule('allow', 'tcp', 80, '0.0.0.0/0')
    print("   ✓ Firewall enabled")
    print("   ✓ Added rule: Allow TCP port 80")
    
    # 4. Monitoring
    print("\n4. System Monitoring:")
    cpu = kadvlayer.monitor_cpu()
    memory = kadvlayer.monitor_memory()
    disk = kadvlayer.monitor_disk()
    print(f"   CPU Usage: {cpu['usage']}%")
    print(f"   Memory: {memory['percent']}% used")
    print(f"   Disk: {disk['percent']}% used")
    
    # 5. Application Management
    print("\n5. Application Framework:")
    from kos.apps.framework import AppManifest, CalculatorApp
    
    manifest = AppManifest(
        app_id='calculator',
        name='Calculator',
        version='1.0',
        author='KOS',
        description='Simple calculator',
        main='calculator'
    )
    
    kadvlayer.app_install('calculator', CalculatorApp)
    kadvlayer.app_start('calculator')
    apps = kadvlayer.app_list()
    print(f"   ✓ Installed apps: {apps}")
    
    # 6. Container Support
    print("\n6. Container Operations:")
    container_id = kadvlayer.container_create('test-container', 'base')
    kadvlayer.container_start('test-container')
    containers = kadvlayer.container_list()
    print(f"   ✓ Created container: {container_id}")
    print(f"   Running containers: {len(containers)}")
    
    # 7. Backup Operations
    print("\n7. Backup & Recovery:")
    backup_id = kadvlayer.backup_create(['/home'], 'Home directory backup')
    backups = kadvlayer.backup_list()
    print(f"   ✓ Created backup: {backup_id}")
    print(f"   Total backups: {len(backups)}")
    
    # 8. Package Management
    print("\n8. Package Repository:")
    from kos.package.repository import Package, PackageVersion
    
    package = Package(
        name='demo-pkg',
        version=PackageVersion(1, 0, 0),
        description='Demo package',
        author='KOS',
        license='MIT',
        size=1024,
        checksum='abcd1234'
    )
    
    kadvlayer.repository.add_package(package, b'package data')
    packages = kadvlayer.pkg_search('demo')
    print(f"   ✓ Added package: demo-pkg")
    print(f"   Found packages: {packages}")
    
    # 9. Database Operations
    print("\n9. Database Support:")
    kadvlayer.db_connect()
    kadvlayer.db_execute("CREATE TABLE IF NOT EXISTS users (id INTEGER, name TEXT)")
    kadvlayer.db_execute("INSERT INTO users VALUES (1, 'Alice')")
    results = kadvlayer.db_query("SELECT * FROM users")
    print(f"   ✓ Database query results: {results}")
    
    # 10. AI/ML Engine
    print("\n10. AI/ML Integration:")
    kadvlayer.ai_train('demo-model', [[1,2], [3,4]], [0, 1])
    prediction = kadvlayer.ai_predict('demo-model', [[2,3]])
    print(f"   ✓ Model trained, prediction: {prediction}")
    
    # Cleanup
    klayer.shutdown()
    os.remove('demo_adv.kdsk')
    
    return True

def demo_integration():
    """Demonstrate full integration"""
    print("\n" + "="*60)
    print("Full Integration Demo")
    print("="*60)
    
    from kos.layers.klayer import KLayer
    from kos.layers.kadvlayer import KADVLayer
    
    # Initialize full system
    klayer = KLayer(disk_file='integration.kdsk')
    kadvlayer = KADVLayer(klayer=klayer)
    
    print("\n1. Complete OS Stack:")
    print("   KLayer:")
    print("     - Virtual File System")
    print("     - Process Management")
    print("     - User Authentication")
    print("     - Device Abstraction")
    print("     - Memory Management")
    print("     - I/O Operations")
    
    print("\n   KADVLayer:")
    print("     - Network Stack")
    print("     - Service Management")
    print("     - Security (Firewall, VPN, SSL)")
    print("     - Monitoring & Metrics")
    print("     - Application Framework")
    print("     - Container Support")
    print("     - Database & Web Services")
    print("     - AI/ML Integration")
    
    print("\n2. Workflow Example:")
    
    # Login
    print("   → Logging in as root...")
    klayer.user_login('root', 'root')
    
    # Create application directory
    print("   → Creating application...")
    klayer.fs_mkdir('/apps')
    klayer.fs_mkdir('/apps/webapp')
    
    # Write application code
    app_code = b"""
def main():
    print("Web Application Running")
    return 0
"""
    klayer.fs_write('/apps/webapp/main.py', app_code)
    
    # Create service for app
    kadvlayer.service_create('webapp', 'python /apps/webapp/main.py', 'Web Application Service')
    
    # Configure network
    kadvlayer.net_configure('eth0', '10.0.0.100', '255.255.255.0')
    
    # Add firewall rules
    kadvlayer.net_firewall_rule('allow', 'tcp', 8080)
    
    # Start web server
    kadvlayer.web_start(8080)
    
    # Create backup
    backup_id = kadvlayer.backup_create(['/apps'], 'Application backup')
    
    print("   ✓ Application deployed successfully!")
    print(f"   ✓ Service created: webapp")
    print(f"   ✓ Network configured: 10.0.0.100")
    print(f"   ✓ Firewall rule added: TCP 8080")
    print(f"   ✓ Web server started on port 8080")
    print(f"   ✓ Backup created: {backup_id}")
    
    # Show system stats
    print("\n3. System Statistics:")
    uptime = klayer.sys_uptime()
    processes = klayer.process_list()
    containers = kadvlayer.container_list()
    
    print(f"   Uptime: {int(uptime)} seconds")
    print(f"   Processes: {len(processes)}")
    print(f"   Containers: {len(containers)}")
    print(f"   Services: {len(kadvlayer.systemd.services) if hasattr(kadvlayer.systemd, 'services') else 0}")
    
    # Cleanup
    klayer.shutdown()
    os.remove('integration.kdsk')
    
    return True

def main():
    """Run all demos"""
    print("KOS Complete Demo")
    print("=" * 60)
    
    try:
        # Demo KLayer
        if demo_klayer():
            print("\n✓ KLayer demo completed successfully!")
        
        # Demo KADVLayer
        if demo_kadvlayer():
            print("\n✓ KADVLayer demo completed successfully!")
        
        # Demo Integration
        if demo_integration():
            print("\n✓ Integration demo completed successfully!")
        
        print("\n" + "="*60)
        print("All demos completed successfully!")
        print("KOS is fully functional with both KLayer and KADVLayer")
        print("="*60)
        
    except Exception as e:
        print(f"\nDemo error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == '__main__':
    sys.exit(main())