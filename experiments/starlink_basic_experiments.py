#!/usr/bin/env python3
"""
Three Simple Starlink Experiments

These experiments can run with your own Starlink dish without requiring
any subscription or external services. They only require:
- A Starlink dish accessible at 192.168.100.1 on your network
- Python 3.7+ with grpcio and protobuf installed
- The starlink-grpc-tools repository cloned locally

Setup:
1. Clone starlink-grpc-tools: 
   git clone https://github.com/sparky8512/starlink-grpc-tools.git
2. Install requirements:
   pip install grpcio protobuf
3. Ensure you can reach your dish at 192.168.100.1

Usage:
    python3 starlink_basic_experiments.py <experiment_number>

Where experiment_number is 1, 2, or 3
"""

import sys
import time
import json
from datetime import datetime

# You'll need to have the starlink-grpc-tools in your path
# or run this from the starlink-grpc-tools directory
try:
    import starlink_grpc
except ImportError:
    print("ERROR: Could not import starlink_grpc")
    print("Please ensure starlink-grpc-tools is in your Python path")
    print("You can clone it from: https://github.com/sparky8512/starlink-grpc-tools")
    sys.exit(1)


def experiment_1_basic_status_monitor():
    """
    Experiment 1: Basic Status Monitor
    
    This experiment collects and displays basic status information from your
    Starlink dish every 5 seconds for 1 minute. No external services required.
    
    Data collected:
    - Connection state (CONNECTED, SEARCHING, etc.)
    - Uptime
    - Signal quality (SNR)
    - Obstruction information
    - Current throughput (upload/download)
    - Latency to Starlink PoP
    
    Use case: Monitor your dish's health and connectivity in real-time
    """
    print("="*70)
    print("EXPERIMENT 1: Basic Status Monitor")
    print("="*70)
    print("\nCollecting status data every 5 seconds for 1 minute...")
    print("Press Ctrl+C to stop early\n")
    
    results = []
    
    try:
        for i in range(12):  # 12 samples over 1 minute
            timestamp = datetime.now().isoformat()
            
            # Get status data from dish
            try:
                status_data, errors = starlink_grpc.get_status()
                
                # Extract key metrics
                data_point = {
                    'timestamp': timestamp,
                    'state': status_data.get('state', 'UNKNOWN'),
                    'uptime_seconds': status_data.get('uptime', 0),
                    'snr': status_data.get('snr'),
                    'fraction_obstructed': status_data.get('fraction_obstructed', 0),
                    'downlink_throughput_bps': status_data.get('downlink_throughput_bps', 0),
                    'uplink_throughput_bps': status_data.get('uplink_throughput_bps', 0),
                    'pop_ping_latency_ms': status_data.get('pop_ping_latency_ms', 0),
                    'alerts': status_data.get('alerts', 0)
                }
                
                results.append(data_point)
                
                # Display current reading
                print(f"\n[Sample {i+1}/12] @ {timestamp}")
                print(f"  State: {data_point['state']}")
                print(f"  Uptime: {data_point['uptime_seconds']} seconds "
                      f"({data_point['uptime_seconds']/3600:.1f} hours)")
                print(f"  Obstruction: {data_point['fraction_obstructed']*100:.1f}%")
                print(f"  Download: {data_point['downlink_throughput_bps']/1e6:.2f} Mbps")
                print(f"  Upload: {data_point['uplink_throughput_bps']/1e6:.2f} Mbps")
                print(f"  Latency: {data_point['pop_ping_latency_ms']:.1f} ms")
                
                if errors:
                    print(f"  Errors: {errors}")
                    
            except Exception as e:
                print(f"  Error collecting data: {e}")
            
            # Wait 5 seconds before next sample (skip on last iteration)
            if i < 11:
                time.sleep(5)
    
    except KeyboardInterrupt:
        print("\n\nStopped by user")
    
    # Summary statistics
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    
    if results:
        avg_download = sum(r['downlink_throughput_bps'] for r in results) / len(results)
        avg_upload = sum(r['uplink_throughput_bps'] for r in results) / len(results)
        avg_latency = sum(r['pop_ping_latency_ms'] for r in results) / len(results)
        avg_obstruction = sum(r['fraction_obstructed'] for r in results) / len(results)
        
        print(f"Samples collected: {len(results)}")
        print(f"Average download: {avg_download/1e6:.2f} Mbps")
        print(f"Average upload: {avg_upload/1e6:.2f} Mbps")
        print(f"Average latency: {avg_latency:.1f} ms")
        print(f"Average obstruction: {avg_obstruction*100:.1f}%")
        
        # Save to file
        filename = f"starlink_status_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nData saved to: {filename}")
    
    return results


def experiment_2_obstruction_analysis():
    """
    Experiment 2: Obstruction Pattern Analysis
    
    This experiment analyzes obstruction patterns over a 30-second period
    to help you understand if there are specific directions with more
    obstructions (trees, buildings, etc.).
    
    Data collected:
    - Overall obstruction percentage
    - Obstruction duration (how long obstructions last)
    - Obstruction interval (how often they occur)
    - Wedge-by-wedge obstruction data (12 directional wedges)
    
    Use case: Identify if you need to trim trees or relocate your dish
    """
    print("="*70)
    print("EXPERIMENT 2: Obstruction Pattern Analysis")
    print("="*70)
    print("\nAnalyzing obstruction patterns for 30 seconds...")
    print("This will help identify if specific directions have more obstructions\n")
    
    try:
        # Get obstruction detail
        status_data, errors = starlink_grpc.get_status()
        obstruction_data, errors2 = starlink_grpc.get_obstruction_map()
        
        print("OBSTRUCTION OVERVIEW")
        print("-" * 70)
        
        # General obstruction info
        fraction_obstructed = status_data.get('fraction_obstructed', 0)
        obstruction_duration = status_data.get('obstruction_duration')
        obstruction_interval = status_data.get('obstruction_interval')
        
        print(f"Total area obstructed: {fraction_obstructed*100:.1f}%")
        if obstruction_duration:
            print(f"Average obstruction duration: {obstruction_duration:.1f} seconds")
        if obstruction_interval:
            print(f"Average interval between obstructions: {obstruction_interval:.1f} seconds")
        
        # Directional analysis
        print("\nDIRECTIONAL OBSTRUCTION MAP")
        print("-" * 70)
        print("(Looking up at the sky, North is 0°, rotating clockwise)")
        print()
        
        # The dish reports obstruction in 12 wedges, 30 degrees each
        # Starting from North (0°) and rotating East
        directions = [
            "N (0°-30°)",
            "NNE (30°-60°)",
            "ENE (60°-90°)",
            "E (90°-120°)",
            "ESE (120°-150°)",
            "SSE (150°-180°)",
            "S (180°-210°)",
            "SSW (210°-240°)",
            "WSW (240°-270°)",
            "W (270°-300°)",
            "WNW (300°-330°)",
            "NNW (330°-360°)"
        ]
        
        # Get the obstruction map data
        if obstruction_data and 'snr' in obstruction_data:
            snr_map = obstruction_data['snr']
            
            # Analyze SNR values (lower SNR = more obstruction)
            print("Signal Quality by Direction (higher is better):")
            for i, direction in enumerate(directions):
                if i < len(snr_map):
                    snr_value = snr_map[i]
                    # Create a simple bar chart
                    bar_length = int(snr_value / 2) if snr_value > 0 else 0
                    bar = "█" * bar_length
                    print(f"{direction:15} {snr_value:6.1f} dB {bar}")
        
        # Additional analysis
        print("\nDISH POINTING INFORMATION")
        print("-" * 70)
        azimuth = status_data.get('direction_azimuth', 0)
        elevation = status_data.get('direction_elevation', 0)
        print(f"Dish azimuth: {azimuth:.1f}° (from North)")
        print(f"Dish elevation: {elevation:.1f}° (from horizontal)")
        
        print("\nRECOMMENDATIONS")
        print("-" * 70)
        if fraction_obstructed > 0.05:
            print("⚠ Your dish has significant obstructions (>5%)")
            print("  Consider:")
            print("  - Trimming trees in obstructed directions")
            print("  - Moving the dish to a location with clearer sky view")
            print("  - Elevating the dish higher")
        elif fraction_obstructed > 0.01:
            print("⚠ Your dish has minor obstructions (1-5%)")
            print("  This may cause occasional connectivity issues")
        else:
            print("✓ Your dish has minimal obstructions (<1%)")
            print("  Good dish placement!")
        
        # Save data
        result = {
            'timestamp': datetime.now().isoformat(),
            'fraction_obstructed': fraction_obstructed,
            'obstruction_duration': obstruction_duration,
            'obstruction_interval': obstruction_interval,
            'azimuth': azimuth,
            'elevation': elevation,
            'snr_map': snr_map if obstruction_data and 'snr' in obstruction_data else None
        }
        
        filename = f"starlink_obstruction_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"\nData saved to: {filename}")
        
        return result
        
    except Exception as e:
        print(f"Error during analysis: {e}")
        import traceback
        traceback.print_exc()
        return None


def experiment_3_performance_variability():
    """
    Experiment 3: Performance Variability Over Time
    
    This experiment measures how your Starlink performance varies over a
    short period (2 minutes), sampling every 10 seconds. It helps identify
    if you have stable connectivity or frequent fluctuations.
    
    Data collected:
    - Throughput variations (upload/download)
    - Latency variations
    - Packet loss patterns
    - Connection state changes
    
    Use case: Understand if your connection is suitable for video calls,
    gaming, or other latency-sensitive applications
    """
    print("="*70)
    print("EXPERIMENT 3: Performance Variability Analysis")
    print("="*70)
    print("\nMeasuring performance every 10 seconds for 2 minutes...")
    print("This will show you how stable your connection is\n")
    
    results = []
    
    try:
        for i in range(12):  # 12 samples over 2 minutes
            timestamp = datetime.now().isoformat()
            
            try:
                # Get both status and history data
                status_data, errors = starlink_grpc.get_status()
                
                # Try to get ping stats from history
                try:
                    history_stats = starlink_grpc.history_ping_stats()
                    ping_drop_rate = history_stats.get('ping_drop_rate', 0)
                    ping_latency_mean = history_stats.get('ping_latency_ms_mean', 0)
                except:
                    ping_drop_rate = 0
                    ping_latency_mean = status_data.get('pop_ping_latency_ms', 0)
                
                data_point = {
                    'timestamp': timestamp,
                    'sample_number': i + 1,
                    'state': status_data.get('state', 'UNKNOWN'),
                    'downlink_mbps': status_data.get('downlink_throughput_bps', 0) / 1e6,
                    'uplink_mbps': status_data.get('uplink_throughput_bps', 0) / 1e6,
                    'latency_ms': status_data.get('pop_ping_latency_ms', 0),
                    'ping_drop_rate': ping_drop_rate,
                    'fraction_obstructed': status_data.get('fraction_obstructed', 0)
                }
                
                results.append(data_point)
                
                # Display current reading
                print(f"[{i+1:2d}/12] {data_point['state']:12} | "
                      f"↓{data_point['downlink_mbps']:6.2f} Mbps | "
                      f"↑{data_point['uplink_mbps']:5.2f} Mbps | "
                      f"{data_point['latency_ms']:5.1f} ms | "
                      f"Drop: {data_point['ping_drop_rate']*100:4.1f}%")
                
            except Exception as e:
                print(f"  Error collecting sample {i+1}: {e}")
            
            # Wait 10 seconds before next sample
            if i < 11:
                time.sleep(10)
    
    except KeyboardInterrupt:
        print("\n\nStopped by user")
    
    # Analysis
    print("\n" + "="*70)
    print("VARIABILITY ANALYSIS")
    print("="*70)
    
    if len(results) >= 2:
        # Calculate statistics
        downloads = [r['downlink_mbps'] for r in results]
        uploads = [r['uplink_mbps'] for r in results]
        latencies = [r['latency_ms'] for r in results]
        
        import statistics
        
        print("\nDownload Speed:")
        print(f"  Mean: {statistics.mean(downloads):.2f} Mbps")
        print(f"  Min: {min(downloads):.2f} Mbps")
        print(f"  Max: {max(downloads):.2f} Mbps")
        if len(downloads) > 1:
            print(f"  Std Dev: {statistics.stdev(downloads):.2f} Mbps")
            print(f"  Coefficient of Variation: {statistics.stdev(downloads)/statistics.mean(downloads)*100:.1f}%")
        
        print("\nUpload Speed:")
        print(f"  Mean: {statistics.mean(uploads):.2f} Mbps")
        print(f"  Min: {min(uploads):.2f} Mbps")
        print(f"  Max: {max(uploads):.2f} Mbps")
        if len(uploads) > 1:
            print(f"  Std Dev: {statistics.stdev(uploads):.2f} Mbps")
            print(f"  Coefficient of Variation: {statistics.stdev(uploads)/statistics.mean(uploads)*100:.1f}%")
        
        print("\nLatency:")
        print(f"  Mean: {statistics.mean(latencies):.1f} ms")
        print(f"  Min: {min(latencies):.1f} ms")
        print(f"  Max: {max(latencies):.1f} ms")
        if len(latencies) > 1:
            print(f"  Std Dev: {statistics.stdev(latencies):.1f} ms")
            print(f"  Jitter (approx): {statistics.stdev(latencies):.1f} ms")
        
        print("\nSTABILITY ASSESSMENT")
        print("-" * 70)
        
        # Check for connection state changes
        states = [r['state'] for r in results]
        if len(set(states)) > 1:
            print("⚠ Connection state changed during monitoring")
            print(f"  States observed: {set(states)}")
        else:
            print(f"✓ Connection remained stable: {states[0]}")
        
        # Check variability
        if len(downloads) > 1:
            cv_download = statistics.stdev(downloads)/statistics.mean(downloads)*100
            if cv_download > 30:
                print("⚠ High download speed variability (CV > 30%)")
                print("  Your connection may not be suitable for consistent streaming")
            elif cv_download > 15:
                print("⚠ Moderate download speed variability (CV 15-30%)")
                print("  Occasional buffering may occur during video streaming")
            else:
                print("✓ Low download speed variability (CV < 15%)")
                print("  Good for streaming and downloads")
        
        if len(latencies) > 1:
            jitter = statistics.stdev(latencies)
            if jitter > 20:
                print("⚠ High latency jitter (>20ms)")
                print("  May affect real-time applications (gaming, video calls)")
            elif jitter > 10:
                print("⚠ Moderate latency jitter (10-20ms)")
                print("  Acceptable for most applications")
            else:
                print("✓ Low latency jitter (<10ms)")
                print("  Excellent for real-time applications")
        
        # Save data
        filename = f"starlink_variability_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nData saved to: {filename}")
    
    return results


def main():
    """Main function to run experiments"""
    
    if len(sys.argv) < 2:
        print(__doc__)
        print("\nAvailable experiments:")
        print("  1 - Basic Status Monitor (1 minute)")
        print("  2 - Obstruction Pattern Analysis (30 seconds)")
        print("  3 - Performance Variability (2 minutes)")
        print("\nExample: python3 starlink_basic_experiments.py 1")
        sys.exit(1)
    
    experiment_num = sys.argv[1]
    
    # Check if dish is reachable
    print("Checking Starlink dish connectivity at 192.168.100.1...")
    try:
        import socket
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
            sys.exit(1)
        print("✓ Dish is reachable\n")
    except Exception as e:
        print(f"ERROR: Could not check dish connectivity: {e}")
        sys.exit(1)
    
    # Run selected experiment
    if experiment_num == '1':
        experiment_1_basic_status_monitor()
    elif experiment_num == '2':
        experiment_2_obstruction_analysis()
    elif experiment_num == '3':
        experiment_3_performance_variability()
    else:
        print(f"ERROR: Unknown experiment number: {experiment_num}")
        print("Please choose 1, 2, or 3")
        sys.exit(1)


if __name__ == '__main__':
    main()
