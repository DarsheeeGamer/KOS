"""
Hardware Utilities Commands for KOS Shell

This module provides Linux-style hardware utilities that leverage
the KADVLayer's hardware_manager component for comprehensive hardware management.
"""

import os
import sys
import json
import logging
import time
from datetime import datetime
from typing import Dict, List, Any, Optional

# Import KOS components
from kos.advlayer import kadvlayer

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
        
        if not kadvlayer or not kadvlayer.hardware_manager:
            return "Error: Hardware manager not available"
        
        # Get hardware devices
        devices = kadvlayer.hardware_manager.get_devices()
        
        # Apply filters
        if device_type:
            devices = [d for d in devices if d.get('device_type', '').lower() == device_type.lower()]
        
        if device_class:
            devices = [d for d in devices if d.get('device_class', '').lower() == device_class.lower()]
        
        if device_bus:
            devices = [d for d in devices if d.get('bus', '').lower() == device_bus.lower()]
        
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
        
        if not kadvlayer or not kadvlayer.hardware_manager:
            return "Error: Hardware manager not available"
        
        # Get block devices
        devices = kadvlayer.hardware_manager.get_block_devices()
        
        # Filter devices
        if not show_all:
            devices = [d for d in devices if d.get('size', 0) > 0]
        
        # Format output
        if json_output:
            # Filter devices to only include requested columns
            filtered_devices = []
            for device in devices:
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
            for device in devices:
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
        
        if not kadvlayer or not kadvlayer.hardware_manager:
            return "Error: Hardware manager not available"
        
        # Get USB devices
        devices = kadvlayer.hardware_manager.get_usb_devices()
        
        # Format output
        if json_output:
            return json.dumps(devices, indent=2)
        elif tree_format:
            output = ["USB Device Hierarchy:"]
            
            # Build device tree
            root_devices = [d for d in devices if not d.get('parent_id')]
            
            def add_device_to_tree(device, level=0):
                device_id = device.get('device_id', '')
                vendor_id = device.get('vendor_id', '')
                product_id = device.get('product_id', '')
                name = device.get('name', 'Unknown Device')
                
                line = '  ' * level
                line += f"{device_id} {vendor_id}:{product_id} {name}"
                output.append(line)
                
                # Add children
                for child in [d for d in devices if d.get('parent_id') == device_id]:
                    add_device_to_tree(child, level + 1)
            
            # Add each root device and its children
            for root_device in root_devices:
                add_device_to_tree(root_device)
            
            return "\n".join(output)
        else:
            output = ["USB Devices:"]
            
            for device in devices:
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
        
        if not kadvlayer or not kadvlayer.hardware_manager:
            return "Error: Hardware manager not available"
        
        # Get PCI devices
        devices = kadvlayer.hardware_manager.get_pci_devices()
        
        # Format output
        if json_output:
            return json.dumps(devices, indent=2)
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
        
        if not kadvlayer or not kadvlayer.hardware_manager:
            return "Error: Hardware manager not available"
        
        # Get sensors data
        sensors = kadvlayer.hardware_manager.get_sensors()
        
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

def register_commands(shell):
    """Register commands with the shell"""
    shell.register_command("lshw", HardwareUtilitiesCommands.do_lshw)
    shell.register_command("lsblk", HardwareUtilitiesCommands.do_lsblk)
    shell.register_command("lsusb", HardwareUtilitiesCommands.do_lsusb)
    shell.register_command("lspci", HardwareUtilitiesCommands.do_lspci)
    shell.register_command("sensors", HardwareUtilitiesCommands.do_sensors)
