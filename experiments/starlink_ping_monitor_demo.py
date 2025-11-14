#!/usr/bin/env python3
"""
Demo script showing how starlink_ping_monitor.py would work with actual data.

This is for demonstration and documentation purposes only. It simulates what
the ping monitor output would look like with real Starlink data.

This script does NOT require a Starlink dish and can be run anywhere.
"""

import time
import os
import random
from datetime import datetime


def clear_terminal():
    """Clear the terminal screen"""
    os.system('cls' if os.name == 'nt' else 'clear')


def generate_sample_ping_stats(iteration):
    """Generate realistic sample ping statistics"""
    base_latency = 28.0
    jitter = random.uniform(-2, 3)
    
    return {
        'ping_drop_rate': round(random.uniform(0, 0.01), 5),
        'ping_latency_ms_mean': round(base_latency + jitter, 3),
        'ping_latency_ms_p50': round(base_latency + jitter - 1, 3),
        'ping_latency_ms_p95': round(base_latency + jitter + 7, 3),
        'ping_latency_ms_p99': round(base_latency + jitter + 14, 3),
        'pop_ping_drop_rate': round(random.uniform(0, 0.005), 5),
        'pop_ping_latency_ms': round(base_latency + jitter - 0.5, 3),
        'seconds_to_first_non_empty_slot': round(random.uniform(0, 0.1), 3),
    }


def display_ping_stats(ping_stats, timestamp, iteration):
    """Display ping statistics in a clean, readable format"""
    clear_terminal()
    
    print("=" * 80)
    print("STARLINK PING STATISTICS MONITOR (DEMO)")
    print("=" * 80)
    print(f"Timestamp: {timestamp}")
    print(f"Iteration: {iteration}")
    print(f"Press Ctrl+C to stop")
    print("=" * 80)
    print()
    
    # Sort keys for consistent display
    sorted_keys = sorted(ping_stats.keys())
    
    # Calculate max key length for formatting
    max_key_len = max(len(key) for key in sorted_keys) if sorted_keys else 0
    
    for key in sorted_keys:
        value = ping_stats[key]
        print(f"  {key:<{max_key_len}} : {value}")
    
    print()
    print("=" * 80)
    print()
    print("NOTE: This is a DEMO with simulated data.")
    print("The actual starlink_ping_monitor.py script polls real Starlink dish data.")
    print()


def main():
    """Run the demo"""
    print("Starlink Ping Statistics Monitor - DEMO")
    print("=" * 80)
    print()
    print("This demo shows what the ping monitor looks like with simulated data.")
    print("The actual script requires a Starlink dish at 192.168.100.1")
    print()
    print("Starting demo in 2 seconds... (Press Ctrl+C to stop)")
    time.sleep(2)
    
    iteration = 0
    
    try:
        while True:
            iteration += 1
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Generate sample data
            ping_stats = generate_sample_ping_stats(iteration)
            
            # Display the statistics
            display_ping_stats(ping_stats, timestamp, iteration)
            
            # Wait 1 second before next update (like the real monitor)
            time.sleep(1)
    
    except KeyboardInterrupt:
        clear_terminal()
        print("\n" + "=" * 80)
        print("STARLINK PING STATISTICS MONITOR - DEMO STOPPED")
        print("=" * 80)
        print(f"Total iterations: {iteration}")
        print("Demo stopped by user")
        print("=" * 80)
        print()
        print("To run the actual monitor with your Starlink dish:")
        print("  python3 starlink_ping_monitor.py")
        print()


if __name__ == '__main__':
    main()
