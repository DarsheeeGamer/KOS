"""
System commands for KOS Shell
"""

import types

def register_commands(shell):
    """Register system commands with shell"""
    
    def do_status(self, arg):
        """Show system status"""
        print("\n" + "="*50)
        print("KOS System Status")
        print("="*50)
        
        # VFS Status
        if self.vfs:
            print("✓ VFS: Active (kaede.kdsk)")
            try:
                entries = len(list(self._walk_vfs('/')))
                print(f"  Files/Dirs: {entries}")
            except:
                pass
        else:
            print("✗ VFS: Not available")
        
        # KLayer Status
        if self.klayer:
            info = self.klayer.get_system_info()
            print(f"✓ KLayer: Active")
            print(f"  Hostname: {info['hostname']}")
            print(f"  Uptime: {info['uptime_str']}")
            print(f"  Processes: {info['process_count']}")
            print(f"  Services: {info['service_count']}")
        else:
            print("✗ KLayer: Not available")
        
        # KADVLayer Status
        if self.kadvlayer:
            adv_info = self.kadvlayer.get_advanced_info()
            print(f"✓ KADVLayer: Active")
            print(f"  Security Events: {adv_info['security']['security_events']}")
            print(f"  Monitoring: {'Enabled' if adv_info['monitoring']['enabled'] else 'Disabled'}")
            print(f"  Containers: {adv_info['containers']['total']} ({adv_info['containers']['running']} running)")
        else:
            print("✗ KADVLayer: Not available")
        
        # Package Manager Status
        if self.kpm:
            packages = self.kpm.list_packages(installed_only=True)
            print(f"✓ KPM: Active")
            print(f"  Installed Packages: {len(packages)}")
        else:
            print("✗ KPM: Not available")
        
        # Python Environment Status
        if self.python_env:
            py_packages = self.python_env.pip_list()
            print(f"✓ Python VFS: Active")
            print(f"  Python Packages: {len(py_packages)}")
        else:
            print("✗ Python VFS: Not available")
        
        print()
    
    def _walk_vfs(self, path):
        """Walk VFS tree (helper for status)"""
        if not self.vfs:
            return
        
        try:
            for name in self.vfs.listdir(path):
                full_path = f"{path}/{name}".replace('//', '/')
                yield full_path
                if self.vfs.isdir(full_path):
                    yield from self._walk_vfs(full_path)
        except:
            pass
    
    def do_info(self, arg):
        """Show system information"""
        if not self.klayer:
            print("System information not available")
            return
        
        info = self.klayer.get_system_info()
        
        print("\n" + "="*50)
        print("System Information")
        print("="*50)
        print(f"Hostname: {info['hostname']}")
        print(f"Kernel: {info['kernel']}")
        print(f"Architecture: {info['architecture']}")
        print(f"Uptime: {info['uptime_str']}")
        print()
        
        print("Resources:")
        mem = info['memory']
        print(f"  Memory: {mem['used_mb']} MB / {mem['total_mb']} MB ({mem['percent']:.1f}%)")
        disk = info['disk']
        print(f"  Disk: {disk['used_mb']} MB / {disk['total_mb']} MB ({disk['percent']:.1f}%)")
        print(f"  Load Average: {', '.join(map(str, info['load_average']))}")
        print()
        
        if self.klayer:
            net_info = self.klayer.get_network_info()
            print("Network:")
            for iface in net_info['interfaces']:
                print(f"  {iface['name']}: {iface['ip']} ({iface['status']})")
    
    def do_ps(self, arg):
        """List processes"""
        if not self.klayer:
            print("Process information not available")
            return
        
        processes = self.klayer.list_processes()
        
        if not processes:
            print("No processes running")
        else:
            print(f"{'PID':<8} {'NAME':<30} {'STATUS':<12} {'CPU%':<8} {'MEM(MB)'}")
            print("-" * 70)
            for proc in processes:
                print(f"{proc.pid:<8} {proc.name:<30} {proc.status:<12} "
                      f"{proc.cpu_percent:<8.1f} {proc.memory_mb:.1f}")
    
    def do_services(self, arg):
        """List or manage services
        Usage:
            services          - List all services
            services start <name>  - Start a service
            services stop <name>   - Stop a service
        """
        if not self.klayer:
            print("Service management not available")
            return
        
        args = arg.split()
        
        if not args:
            # List services
            services = self.klayer.list_services()
            
            print(f"{'SERVICE':<20} {'STATUS':<12} {'ENABLED':<10} {'PID'}")
            print("-" * 50)
            for svc in services:
                enabled = 'Yes' if svc.enabled else 'No'
                pid = str(svc.pid) if svc.pid else '-'
                print(f"{svc.name:<20} {svc.status:<12} {enabled:<10} {pid}")
        
        elif args[0] == 'start' and len(args) > 1:
            if self.klayer.start_service(args[1]):
                print(f"Service '{args[1]}' started")
            else:
                print(f"Failed to start service '{args[1]}'")
        
        elif args[0] == 'stop' and len(args) > 1:
            if self.klayer.stop_service(args[1]):
                print(f"Service '{args[1]}' stopped")
            else:
                print(f"Failed to stop service '{args[1]}'")
        
        else:
            print("Usage: services [start|stop <name>]")
    
    def do_hostname(self, arg):
        """Get or set hostname
        Usage:
            hostname        - Show current hostname
            hostname <name> - Set hostname
        """
        if not self.klayer:
            print("Hostname management not available")
            return
        
        if arg:
            # Set hostname
            self.klayer.set_hostname(arg)
            print(f"Hostname set to: {arg}")
        else:
            # Get hostname
            info = self.klayer.get_system_info()
            print(info['hostname'])
    
    def do_monitor(self, arg):
        """Show system monitoring
        Usage:
            monitor         - Show recent metrics
            monitor alerts  - Show system alerts
        """
        if not self.kadvlayer:
            print("Monitoring not available")
            return
        
        if arg == 'alerts':
            alerts = self.kadvlayer.get_alerts()
            if not alerts:
                print("No alerts")
            else:
                print("Recent Alerts:")
                for alert in alerts[-10:]:  # Show last 10
                    from datetime import datetime
                    timestamp = datetime.fromtimestamp(alert['timestamp'])
                    print(f"  [{timestamp.strftime('%H:%M:%S')}] {alert['type']}: {alert['message']}")
        else:
            # Show metrics
            metrics = self.kadvlayer.get_metrics(last_n=5)
            if not metrics:
                print("No metrics available")
            else:
                print("Recent Performance Metrics:")
                print(f"{'Time':<10} {'CPU%':<8} {'MEM%':<8} {'Disk R':<10} {'Disk W':<10}")
                print("-" * 50)
                for metric in metrics:
                    from datetime import datetime
                    timestamp = datetime.fromtimestamp(metric.timestamp)
                    print(f"{timestamp.strftime('%H:%M:%S'):<10} "
                          f"{metric.cpu_percent:<8.1f} "
                          f"{metric.memory_percent:<8.1f} "
                          f"{metric.disk_io_read:<10.1f} "
                          f"{metric.disk_io_write:<10.1f}")
    
    def do_container(self, arg):
        """Container management
        Usage:
            container list              - List containers
            container create <name>     - Create container
            container start <id>        - Start container
            container stop <id>         - Stop container
        """
        if not self.kadvlayer:
            print("Container management not available")
            return
        
        args = arg.split()
        
        if not args or args[0] == 'list':
            containers = self.kadvlayer.list_containers()
            if not containers:
                print("No containers")
            else:
                print(f"{'ID':<5} {'NAME':<20} {'STATUS':<12} {'IMAGE'}")
                print("-" * 50)
                for cont in containers:
                    print(f"{cont['id']:<5} {cont['name']:<20} {cont['status']:<12} {cont['image']}")
        
        elif args[0] == 'create' and len(args) > 1:
            container_id = self.kadvlayer.create_container(args[1])
            print(f"Container created with ID: {container_id}")
        
        elif args[0] == 'start' and len(args) > 1:
            if self.kadvlayer.start_container(int(args[1])):
                print(f"Container {args[1]} started")
            else:
                print(f"Failed to start container {args[1]}")
        
        elif args[0] == 'stop' and len(args) > 1:
            if self.kadvlayer.stop_container(int(args[1])):
                print(f"Container {args[1]} stopped")
            else:
                print(f"Failed to stop container {args[1]}")
        
        else:
            print("Usage: container [list|create <name>|start <id>|stop <id>]")
    
    # Register commands using MethodType
    shell.do_status = types.MethodType(do_status, shell)
    shell._walk_vfs = types.MethodType(_walk_vfs, shell)
    shell.do_info = types.MethodType(do_info, shell)
    shell.do_ps = types.MethodType(do_ps, shell)
    shell.do_services = types.MethodType(do_services, shell)
    shell.do_hostname = types.MethodType(do_hostname, shell)
    shell.do_monitor = types.MethodType(do_monitor, shell)
    shell.do_container = types.MethodType(do_container, shell)