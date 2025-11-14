#!/usr/bin/env python3
"""
Starlink Ping Statistics Monitor

This script polls the Starlink dish once per second and displays ping-related
statistics in real-time. It clears the terminal each cycle and prints an updated
set of statistics.

Requirements:
- Starlink dish accessible at 192.168.100.1
- Python 3.7+ with grpcio and protobuf installed
- starlink-grpc-tools repository in Python path

Usage:
    python3 starlink_ping_monitor.py

Press Ctrl+C to stop.
"""

import sys
import time
import os
from datetime import datetime

# Import starlink_grpc module
try:
    import starlink_grpc
except ImportError:
    print("ERROR: Could not import starlink_grpc")
    print("Please ensure starlink-grpc-tools is in your Python path")
    print("You can clone it from: https://github.com/sparky8512/starlink-grpc-tools")
    sys.exit(1)


def clear_terminal():
    """Clear the terminal screen"""
    os.system('cls' if os.name == 'nt' else 'clear')


def is_obsolete_field(field_name):
    """
    Determine if a field is obsolete based on the problem requirements.
    
    Obsolete fields include:
    - Fields with 'snr' (case insensitive)
    - Fields starting with 'seconds_to_' EXCEPT 'seconds_to_first_non_empty_slot'
    
    Args:
        field_name: Name of the field to check
        
    Returns:
        True if the field is obsolete and should be ignored, False otherwise
    """
    field_lower = field_name.lower()
    
    # Always include seconds_to_first_non_empty_slot even if marked obsolete
    if field_name == 'seconds_to_first_non_empty_slot':
        return False
    
    # Filter out SNR-related fields
    if 'snr' in field_lower:
        return True
    
    # Filter out other seconds_to_* fields
    if field_name.startswith('seconds_to_'):
        return True
    
    return False


def extract_ping_stats(status_data, history_stats=None):
    """
    Extract all ping-related statistics from status and history data.
    
    Args:
        status_data: Dictionary containing status information from get_status()
        history_stats: Optional dictionary containing history statistics
        
    Returns:
        Dictionary containing only ping-related fields that are not obsolete
    """
    ping_stats = {}
    
    # Extract ping fields from status_data
    if status_data:
        for key, value in status_data.items():
            # Check if field name contains 'ping' (case insensitive)
            if 'ping' in key.lower() and not is_obsolete_field(key):
                ping_stats[key] = value
    
    # Extract ping fields from history_stats
    if history_stats:
        for key, value in history_stats.items():
            # Check if field name contains 'ping' (case insensitive)
            if 'ping' in key.lower() and not is_obsolete_field(key):
                ping_stats[key] = value
    
    # Always include seconds_to_first_non_empty_slot if available
    if status_data and 'seconds_to_first_non_empty_slot' in status_data:
        ping_stats['seconds_to_first_non_empty_slot'] = status_data['seconds_to_first_non_empty_slot']
    
    return ping_stats


def format_value(value):
    """Format a value for display"""
    if value is None:
        return "N/A"
    elif isinstance(value, float):
        return f"{value:.3f}"
    elif isinstance(value, bool):
        return "Yes" if value else "No"
    else:
        return str(value)


def display_ping_stats(ping_stats, timestamp, iteration):
    """
    Display ping statistics in a clean, readable format.
    
    Args:
        ping_stats: Dictionary of ping statistics
        timestamp: Timestamp of the data collection
        iteration: Current iteration number
    """
    clear_terminal()
    
    print("=" * 80)
    print("STARLINK PING STATISTICS MONITOR")
    print("=" * 80)
    print(f"Timestamp: {timestamp}")
    print(f"Iteration: {iteration}")
    print(f"Press Ctrl+C to stop")
    print("=" * 80)
    print()
    
    if not ping_stats:
        print("No ping statistics available")
    else:
        # Sort keys for consistent display
        sorted_keys = sorted(ping_stats.keys())
        
        # Calculate max key length for formatting
        max_key_len = max(len(key) for key in sorted_keys) if sorted_keys else 0
        
        for key in sorted_keys:
            value = ping_stats[key]
            formatted_value = format_value(value)
            print(f"  {key:<{max_key_len}} : {formatted_value}")
    
    print()
    print("=" * 80)


def check_dish_connectivity():
    """Check if Starlink dish is reachable"""
    import socket
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(('192.168.100.1', 9200))
        sock.close()
        
        if result != 0:
            print("ERROR: Cannot reach Starlink dish at 192.168.100.1:9200")
            print("Please ensure:")
            print("  1. Your Starlink dish is powered on")
            print("  2. You are connected to the Starlink network")
            print("  3. You can access http://192.168.100.1 in a browser")
            return False
        return True
    except Exception as e:
        print(f"ERROR: Could not check dish connectivity: {e}")
        return False


def main():
    """Main function to run the ping statistics monitor"""
    
    print("Starlink Ping Statistics Monitor")
    print("=" * 80)
    print()
    print("Checking Starlink dish connectivity at 192.168.100.1...")
    
    if not check_dish_connectivity():
        sys.exit(1)
    
    print("✓ Dish is reachable")
    print()
    print("Starting monitor... (Press Ctrl+C to stop)")
    time.sleep(2)
    
    iteration = 0
    
    try:
        while True:
            iteration += 1
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            try:
                # Get status data from dish
                status_data, status_errors = starlink_grpc.get_status()
                
                # Try to get history ping stats
                history_stats = None
                try:
                    history_stats = starlink_grpc.history_ping_stats()
                except Exception as e:
                    # History stats might not be available, continue without them
                    pass
                
                # Extract ping-related statistics
                ping_stats = extract_ping_stats(status_data, history_stats)
                
                # Display the statistics
                display_ping_stats(ping_stats, timestamp, iteration)
                
                # Display any errors
                if status_errors:
                    print(f"Errors: {status_errors}")
                
            except Exception as e:
                clear_terminal()
                print("=" * 80)
                print("STARLINK PING STATISTICS MONITOR")
                print("=" * 80)
                print(f"Timestamp: {timestamp}")
                print(f"Iteration: {iteration}")
                print("=" * 80)
                print()
                print(f"Error collecting data: {e}")
                print()
                print("=" * 80)
            
            # Wait 1 second before next poll
            time.sleep(1)
    
    except KeyboardInterrupt:
        clear_terminal()
        print("\n" + "=" * 80)
        print("STARLINK PING STATISTICS MONITOR - STOPPED")
        print("=" * 80)
        print(f"Total iterations: {iteration}")
        print("Monitor stopped by user")
        print("=" * 80)
        sys.exit(0)


if __name__ == '__main__':
    main()
