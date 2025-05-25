"""
Hardware Utilities Commands for KOS Shell

This module provides Linux-style hardware utilities that leverage
the Hardware Abstraction Layer (HAL) for comprehensive hardware management.
"""

import os
import sys
import json
import logging
import time
import argparse
from datetime import datetime
from typing import Dict, List, Any, Optional

# Import KOS components
from kos.core import hal
from kos.core.hal import devices

# Set up logging
logger = logging.getLogger('KOS.shell.commands.hardware_utils')

class HardwareUtilitiesCommands:
    """Hardware utilities commands for KOS shell"""
    
    @staticmethod
    def do_lshw(fs, cwd, arg):
        """
        List hardware devices
        
        Usage: lshw [options]
        
        Options:
          --type=<type>        Filter by device type (disk, network, usb, etc.)
          --class=<class>      Filter by device class (storage, network, input, etc.)
          --bus=<bus>          Filter by bus (pci, usb, etc.)
          --json               Output in JSON format
          --short              Short format (name and type only)
        """
        args = arg.split()
        
        # Parse options
        json_output = '--json' in args
        short_format = '--short' in args
        
        # Parse type filter
        device_type = None
        for opt in args:
            if opt.startswith('--type='):
                device_type = opt[7:]
        
        # Parse class filter
        device_class = None
        for opt in args:
            if opt.startswith('--class='):
                device_class = opt[8:]
        
        # Parse bus filter
        device_bus = None
        for opt in args:
            if opt.startswith('--bus='):
                device_bus = opt[6:]
        
        # Initialize HAL if not already initialized
        if not hal._hal_state['initialized']:
            hal.initialize()
        
        # Get hardware devices
        device_list = hal.list_devices()
        
        # Convert DeviceInfo objects to dictionaries
        devices = [d.to_dict() for d in device_list]
        
        # Apply filters
        if device_type:
            devices = [d for d in devices if d.get('device_type', '').lower() == device_type.lower()]
        
        if device_class:
            devices = [d for d in devices if d.get('device_type', '').lower() == device_class.lower()]
        
        if device_bus:
            devices = [d for d in devices if d.get('properties', {}).get('bus', '').lower() == device_bus.lower()]
        
        # Format output
        if json_output:
            return json.dumps(devices, indent=2)
        else:
            if short_format:
                output = ["Hardware Devices:"]
                for device in devices:
                    output.append(f"  {device.get('name', 'Unknown')} [{device.get('device_type', 'Unknown')}]")
                return "\n".join(output)
            else:
                output = ["Hardware Devices:"]
                
                for device in devices:
                    output.append(f"  {device.get('name', 'Unknown')}:")
                    output.append(f"    Type: {device.get('device_type', 'Unknown')}")
                    
                    if 'device_id' in device:
                        output.append(f"    ID: {device.get('device_id')}")
                    
                    if 'bus' in device:
                        output.append(f"    Bus: {device.get('bus')}")
                    
                    if 'vendor' in device:
                        output.append(f"    Vendor: {device.get('vendor')}")
                    
                    if 'model' in device:
                        output.append(f"    Model: {device.get('model')}")
                    
                    if 'serial' in device:
                        output.append(f"    Serial: {device.get('serial')}")
                    
                    if 'status' in device:
                        output.append(f"    Status: {device.get('status')}")
                    
                    if 'properties' in device:
                        output.append("    Properties:")
                        for key, value in device['properties'].items():
                            output.append(f"      {key}: {value}")
                    
                    output.append("")
                
                return "\n".join(output)
    
    @staticmethod
    def do_lsblk(fs, cwd, arg):
        """
        List block devices
        
        Usage: lsblk [options]
        
        Options:
          --all                Show all devices, including empty ones
          --bytes              Print SIZE in bytes
          --json               Output in JSON format
          --output=<list>      Comma-separated list of columns to output
        """
        args = arg.split()
        
        # Parse options
        json_output = '--json' in args
        show_all = '--all' in args
        show_bytes = '--bytes' in args
        
        # Parse output columns
        output_columns = ['name', 'size', 'type', 'mountpoint']
        for opt in args:
            if opt.startswith('--output='):
                output_columns = opt[9:].split(',')
        
        # Initialize HAL if not already initialized
        if not hal._hal_state['initialized']:
            hal.initialize()
        
        # Get storage devices
        storage_devices = hal.list_devices(hal.DeviceType.STORAGE)
        
        # Convert to dictionaries and format for block device display
        block_devices = []
        for device in storage_devices:
            driver = hal.get_driver(device.device_id)
            if driver:
                status = driver.get_status()
                block_devices.append({
                    'name': device.name,
                    'device': device.properties.get('device', ''),
                    'mountpoint': device.properties.get('mountpoint', ''),
                    'fstype': device.properties.get('fstype', ''),
                    'size': status.get('usage', {}).get('total', 0),
                    'used': status.get('usage', {}).get('used', 0),
                    'avail': status.get('usage', {}).get('free', 0),
                    'use%': status.get('usage', {}).get('percent', 0)
                })
        
        # Filter devices
        if not show_all:
            block_devices = [d for d in block_devices if d.get('size', 0) > 0]
        
        # Format output
        if json_output:
            # Filter devices to only include requested columns
            filtered_devices = []
            for device in block_devices:
                filtered_device = {col: device.get(col, '') for col in output_columns if col in device}
                filtered_devices.append(filtered_device)
            
            return json.dumps(filtered_devices, indent=2)
        else:
            # Create header
            output = []
            header = []
            for col in output_columns:
                if col == 'name':
                    header.append('NAME')
                elif col == 'size':
                    header.append('SIZE')
                elif col == 'type':
                    header.append('TYPE')
                elif col == 'mountpoint':
                    header.append('MOUNTPOINT')
                elif col == 'fstype':
                    header.append('FSTYPE')
                elif col == 'label':
                    header.append('LABEL')
                elif col == 'uuid':
                    header.append('UUID')
                else:
                    header.append(col.upper())
            
            output.append(' '.join(f"{h:<15}" for h in header))
            
            # Add device rows
            for device in block_devices:
                row = []
                for col in output_columns:
                    if col == 'size':
                        size = device.get('size', 0)
                        if show_bytes:
                            row.append(f"{size}")
                        else:
                            # Convert to human-readable format
                            if size < 1024:
                                row.append(f"{size}B")
                            elif size < 1024 ** 2:
                                row.append(f"{size/1024:.1f}K")
                            elif size < 1024 ** 3:
                                row.append(f"{size/(1024**2):.1f}M")
                            elif size < 1024 ** 4:
                                row.append(f"{size/(1024**3):.1f}G")
                            else:
                                row.append(f"{size/(1024**4):.1f}T")
                    else:
                        row.append(f"{device.get(col, '')}")
                
                output.append(' '.join(f"{cell:<15}" for cell in row))
            
            return "\n".join(output)
    
    @staticmethod
    def do_lsusb(fs, cwd, arg):
        """
        List USB devices
        
        Usage: lsusb [options]
        
        Options:
          --verbose            Show detailed information
          --tree               Show device hierarchy as a tree
          --json               Output in JSON format
        """
        args = arg.split()
        
        # Parse options
        json_output = '--json' in args
        verbose = '--verbose' in args
        tree_format = '--tree' in args
        
        # Initialize HAL if not already initialized
        if not hal._hal_state['initialized']:
            hal.initialize()
        
        # Note: HAL doesn't specifically identify USB devices yet
        # This is a placeholder implementation that will show any available devices
        # Get hardware information
        hardware_info = hal.get_hardware_info()
        
        # Create a list of USB devices (placeholder implementation)
        usb_devices = []
        
        # In a real implementation, we would filter the devices by USB bus
        # For now, this is a placeholder that just indicates USB functionality exists
        
        # Format output
        if json_output:
            return json.dumps(usb_devices, indent=2)
        elif tree_format:
            output = ["USB Device Hierarchy:"]
            
            # Build device tree
            root_devices = [d for d in usb_devices if not d.get('parent_id')]
            
            def add_device_to_tree(device, level=0):
                device_id = device.get('device_id', '')
                vendor_id = device.get('vendor_id', '')
                product_id = device.get('product_id', '')
                name = device.get('name', 'Unknown Device')
                
                line = '  ' * level
                line += f"{device_id} {vendor_id}:{product_id} {name}"
                output.append(line)
                
                # Add children
                for child in [d for d in usb_devices if d.get('parent_id') == device_id]:
                    add_device_to_tree(child, level + 1)
            
            # Add each root device and its children
            for root_device in root_devices:
                add_device_to_tree(root_device)
            
            return "\n".join(output)
        else:
            output = ["USB Devices:"]
            
            for device in usb_devices:
                device_id = device.get('device_id', '')
                vendor_id = device.get('vendor_id', '')
                product_id = device.get('product_id', '')
                name = device.get('name', 'Unknown Device')
                
                line = f"Bus {device.get('bus_number', '??')} Device {device.get('device_number', '??')}: "
                line += f"ID {vendor_id}:{product_id} {name}"
                output.append(line)
                
                if verbose:
                    output.append(f"  Device ID: {device_id}")
                    
                    if 'manufacturer' in device:
                        output.append(f"  Manufacturer: {device.get('manufacturer')}")
                    
                    if 'product' in device:
                        output.append(f"  Product: {device.get('product')}")
                    
                    if 'serial' in device:
                        output.append(f"  Serial: {device.get('serial')}")
                    
                    if 'speed' in device:
                        output.append(f"  Speed: {device.get('speed')}")
                    
                    if 'interfaces' in device:
                        output.append("  Interfaces:")
                        for interface in device['interfaces']:
                            output.append(f"    {interface.get('number', '?')}: {interface.get('class', '?')} - {interface.get('description', '?')}")
                    
                    output.append("")
            
            return "\n".join(output)
    
    @staticmethod
    def do_lspci(fs, cwd, arg):
        """
        List PCI devices
        
        Usage: lspci [options]
        
        Options:
          --verbose            Show detailed information
          --kernel             Show kernel drivers for each device
          --json               Output in JSON format
        """
        args = arg.split()
        
        # Parse options
        json_output = '--json' in args
        verbose = '--verbose' in args
        show_kernel = '--kernel' in args
        
        # Initialize HAL if not already initialized
        if not hal._hal_state['initialized']:
            hal.initialize()
        
        # Note: HAL doesn't specifically identify PCI devices yet
        # This is a placeholder implementation that will show any available devices
        # Get hardware information
        hardware_info = hal.get_hardware_info()
        
        # Create a list of PCI devices (placeholder implementation)
        pci_devices = []
        
        # In a real implementation, we would filter the devices by PCI bus
        # For now, this is a placeholder that just indicates PCI functionality exists
        
        # Format output
        if json_output:
            return json.dumps(pci_devices, indent=2)
        else:
            output = []
            
            for device in devices:
                bus = device.get('bus_address', '')
                vendor_id = device.get('vendor_id', '')
                product_id = device.get('product_id', '')
                class_id = device.get('class_id', '')
                name = device.get('name', 'Unknown Device')
                
                line = f"{bus} {class_id}: {vendor_id}:{product_id} {name}"
                output.append(line)
                
                if verbose:
                    if 'vendor' in device:
                        output.append(f"\tVendor: {device.get('vendor')}")
                    
                    if 'device' in device:
                        output.append(f"\tDevice: {device.get('device')}")
                    
                    if 'subsystem_vendor' in device:
                        output.append(f"\tSubsystem Vendor: {device.get('subsystem_vendor')}")
                    
                    if 'subsystem' in device:
                        output.append(f"\tSubsystem: {device.get('subsystem')}")
                    
                    if 'revision' in device:
                        output.append(f"\tRevision: {device.get('revision')}")
                
                if show_kernel and 'driver' in device:
                    output.append(f"\tKernel driver in use: {device.get('driver')}")
                    
                    if 'modules' in device:
                        output.append(f"\tKernel modules: {', '.join(device.get('modules', []))}")
            
            return "\n".join(output)
    
    @staticmethod
    def do_sensors(fs, cwd, arg):
        """
        Display hardware sensors information
        
        Usage: sensors [options]
        
        Options:
          --fahrenheit         Display temperatures in Fahrenheit
          --json               Output in JSON format
        """
        args = arg.split()
        
        # Parse options
        json_output = '--json' in args
        fahrenheit = '--fahrenheit' in args
        
        # Initialize HAL if not already initialized
        if not hal._hal_state['initialized']:
            hal.initialize()
        
        # Get CPU and memory information for sensor data
        cpu_device = hal.get_driver('cpu0')
        memory_device = hal.get_driver('mem0')
        
        # Create sensors data
        sensors = []
        
        if cpu_device:
            cpu_status = cpu_device.get_status()
            
            # Add CPU temperature sensor (simulated)
            sensors.append({
                'chip': 'CPU',
                'name': 'Temperature',
                'type': 'temperature',
                'value': 45.0,  # Simulated value
                'unit': '°C',
                'min': 0,
                'max': 100,
                'critical': 90
            })
            
            # Add CPU usage sensor
            sensors.append({
                'chip': 'CPU',
                'name': 'Usage',
                'type': 'usage',
                'value': cpu_status.get('percent', 0),
                'unit': '%',
                'min': 0,
                'max': 100
            })
        
        if memory_device:
            memory_status = memory_device.get_status()
            
            # Add memory usage sensor
            sensors.append({
                'chip': 'Memory',
                'name': 'Usage',
                'type': 'usage',
                'value': memory_status.get('virtual', {}).get('percent', 0),
                'unit': '%',
                'min': 0,
                'max': 100
            })
        
        # Format output
        if json_output:
            # Convert temperature to Fahrenheit if requested
            if fahrenheit:
                for sensor in sensors:
                    if sensor.get('type') == 'temperature' and 'value' in sensor:
                        # Convert from Celsius to Fahrenheit
                        sensor['value'] = (sensor['value'] * 9/5) + 32
                        sensor['unit'] = '°F'
            
            return json.dumps(sensors, indent=2)
        else:
            output = ["Hardware Sensors:"]
            
            # Group sensors by chip
            chips = {}
            for sensor in sensors:
                chip = sensor.get('chip', 'Unknown')
                if chip not in chips:
                    chips[chip] = []
                chips[chip].append(sensor)
            
            for chip, chip_sensors in chips.items():
                output.append(f"  {chip}:")
                
                for sensor in chip_sensors:
                    name = sensor.get('name', 'Unknown')
                    value = sensor.get('value', 'N/A')
                    unit = sensor.get('unit', '')
                    
                    # Convert temperature to Fahrenheit if requested
                    if fahrenheit and sensor.get('type') == 'temperature' and value != 'N/A':
                        value = (value * 9/5) + 32
                        unit = '°F'
                    
                    output.append(f"    {name}: {value}{unit}")
                    
                    if 'min' in sensor and 'max' in sensor:
                        min_val = sensor.get('min', 'N/A')
                        max_val = sensor.get('max', 'N/A')
                        output.append(f"      (min = {min_val}{unit}, max = {max_val}{unit})")
                    
                    if 'critical' in sensor:
                        crit = sensor.get('critical', 'N/A')
                        output.append(f"      (critical = {crit}{unit})")
                
                output.append("")
            
            return "\n".join(output)
            
    @staticmethod
    def do_hal(fs, cwd, arg):
        """
        Hardware Abstraction Layer (HAL) interface
        
        Usage: hal [command] [options]
        
        Commands:
          status              Show HAL status and initialized devices
          info                Show detailed hardware information
          device <id>         Show detailed information about a specific device
          drivers             List all available device drivers
          initialize          Initialize the HAL if not already initialized
          refresh             Re-detect hardware and refresh device information
        """
        # Initialize argument parser
        parser = argparse.ArgumentParser(prog='hal', add_help=False)
        subparsers = parser.add_subparsers(dest='command')
        
        # Status command
        status_parser = subparsers.add_parser('status', add_help=False)
        status_parser.add_argument('--json', action='store_true', help='Output in JSON format')
        
        # Info command
        info_parser = subparsers.add_parser('info', add_help=False)
        info_parser.add_argument('--json', action='store_true', help='Output in JSON format')
        
        # Device command
        device_parser = subparsers.add_parser('device', add_help=False)
        device_parser.add_argument('device_id', nargs='?', help='Device ID')
        device_parser.add_argument('--json', action='store_true', help='Output in JSON format')
        
        # Drivers command
        drivers_parser = subparsers.add_parser('drivers', add_help=False)
        drivers_parser.add_argument('--json', action='store_true', help='Output in JSON format')
        
        # Initialize command
        init_parser = subparsers.add_parser('initialize', add_help=False)
        
        # Refresh command
        refresh_parser = subparsers.add_parser('refresh', add_help=False)
        
        # Parse arguments
        try:
            args = parser.parse_args(arg.split())
        except Exception:
            return HardwareUtilitiesCommands.do_hal.__doc__
        
        # If no command specified, show help
        if not args.command:
            return HardwareUtilitiesCommands.do_hal.__doc__
        
        # Process commands
        if args.command == 'status':
            return HardwareUtilitiesCommands._hal_status(args)
        elif args.command == 'info':
            return HardwareUtilitiesCommands._hal_info(args)
        elif args.command == 'device':
            return HardwareUtilitiesCommands._hal_device(args)
        elif args.command == 'drivers':
            return HardwareUtilitiesCommands._hal_drivers(args)
        elif args.command == 'initialize':
            return HardwareUtilitiesCommands._hal_initialize(args)
        elif args.command == 'refresh':
            return HardwareUtilitiesCommands._hal_refresh(args)
        else:
            return HardwareUtilitiesCommands.do_hal.__doc__
    
    @staticmethod
    def _hal_status(args):
        """Show HAL status"""
        # Make sure HAL is initialized
        if not hal._hal_state['initialized']:
            return "HAL is not initialized. Use 'hal initialize' to initialize."
        
        # Get list of devices
        devices = hal.list_devices()
        
        # Format the output
        if args.json:
            status = {
                'initialized': hal._hal_state['initialized'],
                'device_count': len(devices),
                'devices': [d.to_dict() for d in devices]
            }
            return json.dumps(status, indent=2)
        else:
            output = ["Hardware Abstraction Layer (HAL) Status:"]
            output.append(f"  Initialized: {hal._hal_state['initialized']}")
            output.append(f"  Device Count: {len(devices)}")
            output.append("  Devices:")
            
            for device in devices:
                output.append(f"    {device.device_id}: {device.name} [{device.device_type}]")
            
            return "\n".join(output)
    
    @staticmethod
    def _hal_info(args):
        """Show detailed hardware information"""
        # Make sure HAL is initialized
        if not hal._hal_state['initialized']:
            hal.initialize()
        
        # Get hardware info
        hardware_info = hal.get_hardware_info()
        
        # Format the output
        if args.json:
            return json.dumps(hardware_info, indent=2)
        else:
            output = ["Hardware Information:"]
            
            # System info
            if 'system' in hardware_info:
                output.append("  System:")
                for key, value in hardware_info['system'].items():
                    output.append(f"    {key}: {value}")
            
            # CPU info
            if 'cpu' in hardware_info:
                output.append("\n  CPU:")
                for key, value in hardware_info['cpu'].items():
                    output.append(f"    {key}: {value}")
            
            # Memory info
            if 'memory' in hardware_info:
                output.append("\n  Memory:")
                for key, value in hardware_info['memory'].items():
                    if isinstance(value, dict):
                        output.append(f"    {key}:")
                        for k, v in value.items():
                            # Format sizes in human-readable format
                            if k in ['total', 'available', 'free'] and isinstance(v, int):
                                v = HardwareUtilitiesCommands._format_size(v)
                            output.append(f"      {k}: {v}")
                    else:
                        output.append(f"    {key}: {value}")
            
            # Storage info
            if 'storage' in hardware_info and 'disks' in hardware_info['storage']:
                output.append("\n  Storage:")
                for i, disk in enumerate(hardware_info['storage']['disks']):
                    output.append(f"    Disk {i+1}:")
                    for key, value in disk.items():
                        # Format sizes in human-readable format
                        if key in ['total', 'used', 'free'] and isinstance(value, int):
                            value = HardwareUtilitiesCommands._format_size(value)
                        output.append(f"      {key}: {value}")
            
            # Network info
            if 'network' in hardware_info and 'interfaces' in hardware_info['network']:
                output.append("\n  Network:")
                for i, iface in enumerate(hardware_info['network']['interfaces']):
                    output.append(f"    Interface {i+1} ({iface.get('name', 'unknown')}):")
                    
                    if 'addresses' in iface:
                        output.append("      Addresses:")
                        for addr in iface['addresses']:
                            output.append(f"        {addr.get('family', 'unknown')}: {addr.get('address', 'unknown')}")
                    
                    if 'stats' in iface:
                        output.append("      Stats:")
                        for key, value in iface['stats'].items():
                            output.append(f"        {key}: {value}")
            
            return "\n".join(output)
    
    @staticmethod
    def _hal_device(args):
        """Show detailed information about a specific device"""
        # Make sure HAL is initialized
        if not hal._hal_state['initialized']:
            hal.initialize()
        
        # Check if device ID is specified
        if not args.device_id:
            # No device ID specified, list all devices
            devices = hal.list_devices()
            
            if args.json:
                return json.dumps([d.to_dict() for d in devices], indent=2)
            else:
                output = ["Available Devices:"]
                for device in devices:
                    output.append(f"  {device.device_id}: {device.name} [{device.device_type}]")
                return "\n".join(output)
        
        # Get device info
        device_info = hal.get_device_info(args.device_id)
        if not device_info:
            return f"Error: Device '{args.device_id}' not found"
        
        # Get device driver
        driver = hal.get_driver(args.device_id)
        driver_status = driver.get_status() if driver else None
        
        # Format the output
        if args.json:
            result = device_info.to_dict()
            if driver_status:
                result['status'] = driver_status
            return json.dumps(result, indent=2)
        else:
            output = [f"Device Information: {args.device_id}"]
            output.append(f"  Name: {device_info.name}")
            output.append(f"  Type: {device_info.device_type}")
            output.append(f"  Description: {device_info.description}")
            
            if device_info.properties:
                output.append("  Properties:")
                for key, value in device_info.properties.items():
                    if isinstance(value, dict):
                        output.append(f"    {key}:")
                        for k, v in value.items():
                            output.append(f"      {k}: {v}")
                    elif isinstance(value, list):
                        output.append(f"    {key}: {', '.join(str(v) for v in value)}")
                    else:
                        output.append(f"    {key}: {value}")
            
            if driver_status:
                output.append("\n  Status:")
                for key, value in driver_status.items():
                    if isinstance(value, dict):
                        output.append(f"    {key}:")
                        for k, v in value.items():
                            # Format sizes in human-readable format
                            if k in ['total', 'available', 'used', 'free'] and isinstance(v, int):
                                v = HardwareUtilitiesCommands._format_size(v)
                            output.append(f"      {k}: {v}")
                    elif isinstance(value, list):
                        output.append(f"    {key}: {', '.join(str(v) for v in value)}")
                    else:
                        output.append(f"    {key}: {value}")
            
            return "\n".join(output)
    
    @staticmethod
    def _hal_drivers(args):
        """List all available device drivers"""
        # Make sure HAL is initialized
        if not hal._hal_state['initialized']:
            hal.initialize()
        
        # Get drivers
        drivers = {}
        for device_id, driver in hal._hal_state['drivers'].items():
            device_info = hal.get_device_info(device_id)
            if device_info:
                driver_class = driver.__class__.__name__
                if driver_class not in drivers:
                    drivers[driver_class] = []
                drivers[driver_class].append({
                    'device_id': device_id,
                    'name': device_info.name,
                    'device_type': device_info.device_type,
                    'initialized': driver.initialized
                })
        
        # Format the output
        if args.json:
            return json.dumps(drivers, indent=2)
        else:
            output = ["Available Device Drivers:"]
            
            for driver_class, devices in drivers.items():
                output.append(f"\n  {driver_class}:")
                for device in devices:
                    status = "[Initialized]" if device['initialized'] else "[Not Initialized]"
                    output.append(f"    {device['device_id']}: {device['name']} {status}")
            
            return "\n".join(output)
    
    @staticmethod
    def _hal_initialize(args):
        """Initialize the HAL"""
        # Check if HAL is already initialized
        if hal._hal_state['initialized']:
            return "HAL is already initialized"
        
        # Initialize HAL
        success = hal.initialize()
        
        if success:
            return "HAL initialized successfully"
        else:
            return "Error initializing HAL"
    
    @staticmethod
    def _hal_refresh(args):
        """Re-detect hardware and refresh device information"""
        # Make sure HAL is initialized
        if not hal._hal_state['initialized']:
            hal.initialize()
            return "HAL initialized"
        
        # Update hardware info
        hal._hal_state['hardware_info'] = hal.detect_hardware()
        
        return "Hardware information refreshed"
    
    @staticmethod
    def _format_size(size_bytes):
        """Format size in bytes to human-readable format"""
        if size_bytes == 0:
            return "0B"
        
        units = ["B", "KB", "MB", "GB", "TB", "PB"]
        i = 0
        while size_bytes >= 1024 and i < len(units) - 1:
            size_bytes /= 1024.0
            i += 1
        
        return f"{size_bytes:.2f} {units[i]}"

def register_commands(shell):
    """Register commands with the shell"""
    shell.register_command("lshw", HardwareUtilitiesCommands.do_lshw)
    shell.register_command("lsblk", HardwareUtilitiesCommands.do_lsblk)
    shell.register_command("lsusb", HardwareUtilitiesCommands.do_lsusb)
    shell.register_command("lspci", HardwareUtilitiesCommands.do_lspci)
    shell.register_command("sensors", HardwareUtilitiesCommands.do_sensors)
    shell.register_command("hal", HardwareUtilitiesCommands.do_hal)
