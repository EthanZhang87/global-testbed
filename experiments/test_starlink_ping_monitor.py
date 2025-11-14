#!/usr/bin/env python3
"""
Unit tests for starlink_ping_monitor.py

Tests the key filtering and extraction logic without requiring a Starlink dish.
"""

import sys
import os

# Add the experiments directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the functions we want to test (without running main)
# We need to temporarily mock starlink_grpc to avoid import errors
sys.modules['starlink_grpc'] = type('MockModule', (), {})()

import starlink_ping_monitor


def test_is_obsolete_field():
    """Test the obsolete field filtering logic"""
    
    # Test SNR fields (should be obsolete)
    assert starlink_ping_monitor.is_obsolete_field('snr') == True
    assert starlink_ping_monitor.is_obsolete_field('SNR') == True
    assert starlink_ping_monitor.is_obsolete_field('snr_above_noise_floor') == True
    
    # Test seconds_to_* fields (should be obsolete except seconds_to_first_non_empty_slot)
    assert starlink_ping_monitor.is_obsolete_field('seconds_to_something') == True
    assert starlink_ping_monitor.is_obsolete_field('seconds_to_next_slot') == True
    assert starlink_ping_monitor.is_obsolete_field('seconds_to_first_non_empty_slot') == False  # Exception!
    
    # Test regular ping fields (should not be obsolete)
    assert starlink_ping_monitor.is_obsolete_field('ping_drop_rate') == False
    assert starlink_ping_monitor.is_obsolete_field('ping_latency_ms') == False
    assert starlink_ping_monitor.is_obsolete_field('pop_ping_latency_ms') == False
    
    print("✓ test_is_obsolete_field passed")


def test_extract_ping_stats():
    """Test the ping statistics extraction logic"""
    
    # Mock status data with various fields
    status_data = {
        'ping_drop_rate': 0.01,
        'ping_latency_ms': 28.5,
        'pop_ping_latency_ms': 27.3,
        'snr': 8.5,  # Should be filtered out
        'snr_above_noise_floor': 3.2,  # Should be filtered out
        'seconds_to_first_non_empty_slot': 0.5,  # Should be included (exception)
        'seconds_to_next_slot': 1.2,  # Should be filtered out
        'uplink_throughput_bps': 10000000,  # Not a ping field, should be excluded
        'downlink_throughput_bps': 50000000,  # Not a ping field, should be excluded
        'state': 'CONNECTED',  # Not a ping field, should be excluded
    }
    
    # Mock history stats with ping fields
    history_stats = {
        'ping_latency_ms_mean': 29.1,
        'ping_latency_ms_p50': 28.0,
        'ping_latency_ms_p95': 35.2,
        'ping_latency_ms_p99': 42.1,
        'ping_packets_sent': 1000,
        'ping_packets_received': 995,
    }
    
    # Extract ping stats
    ping_stats = starlink_ping_monitor.extract_ping_stats(status_data, history_stats)
    
    # Verify ping fields are included
    assert 'ping_drop_rate' in ping_stats
    assert 'ping_latency_ms' in ping_stats
    assert 'pop_ping_latency_ms' in ping_stats
    assert 'ping_latency_ms_mean' in ping_stats
    assert 'ping_latency_ms_p50' in ping_stats
    assert 'ping_latency_ms_p95' in ping_stats
    assert 'ping_latency_ms_p99' in ping_stats
    assert 'ping_packets_sent' in ping_stats
    assert 'ping_packets_received' in ping_stats
    
    # Verify seconds_to_first_non_empty_slot is included (exception)
    assert 'seconds_to_first_non_empty_slot' in ping_stats
    
    # Verify obsolete fields are excluded
    assert 'snr' not in ping_stats
    assert 'snr_above_noise_floor' not in ping_stats
    assert 'seconds_to_next_slot' not in ping_stats
    
    # Verify non-ping fields are excluded
    assert 'uplink_throughput_bps' not in ping_stats
    assert 'downlink_throughput_bps' not in ping_stats
    assert 'state' not in ping_stats
    
    # Verify values are correct
    assert ping_stats['ping_drop_rate'] == 0.01
    assert ping_stats['ping_latency_ms'] == 28.5
    assert ping_stats['seconds_to_first_non_empty_slot'] == 0.5
    assert ping_stats['ping_latency_ms_mean'] == 29.1
    
    print("✓ test_extract_ping_stats passed")


def test_extract_ping_stats_no_history():
    """Test extraction when history stats are not available"""
    
    status_data = {
        'ping_drop_rate': 0.01,
        'pop_ping_latency_ms': 27.3,
        'seconds_to_first_non_empty_slot': 0.5,
    }
    
    # Extract with no history stats
    ping_stats = starlink_ping_monitor.extract_ping_stats(status_data, None)
    
    # Verify status ping fields are included
    assert 'ping_drop_rate' in ping_stats
    assert 'pop_ping_latency_ms' in ping_stats
    assert 'seconds_to_first_non_empty_slot' in ping_stats
    
    print("✓ test_extract_ping_stats_no_history passed")


def test_format_value():
    """Test value formatting"""
    
    # Test None
    assert starlink_ping_monitor.format_value(None) == "N/A"
    
    # Test float
    assert starlink_ping_monitor.format_value(28.123456) == "28.123"
    assert starlink_ping_monitor.format_value(0.005) == "0.005"
    
    # Test bool
    assert starlink_ping_monitor.format_value(True) == "Yes"
    assert starlink_ping_monitor.format_value(False) == "No"
    
    # Test int
    assert starlink_ping_monitor.format_value(42) == "42"
    
    # Test string
    assert starlink_ping_monitor.format_value("test") == "test"
    
    print("✓ test_format_value passed")


def run_all_tests():
    """Run all tests"""
    print("Running unit tests for starlink_ping_monitor.py")
    print("=" * 60)
    
    try:
        test_is_obsolete_field()
        test_extract_ping_stats()
        test_extract_ping_stats_no_history()
        test_format_value()
        
        print("=" * 60)
        print("✓ All tests passed!")
        return True
    except AssertionError as e:
        print("=" * 60)
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
