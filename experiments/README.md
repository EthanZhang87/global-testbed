# Starlink Experiments

This directory contains experimental Python scripts for analyzing your Starlink dish performance without requiring any external subscriptions or services.

## Prerequisites

1. **A Starlink dish** accessible at `192.168.100.1` on your network
2. **Python 3.7+** installed
3. **starlink-grpc-tools** repository cloned locally

## Setup Instructions

### 1. Clone the starlink-grpc-tools repository

```bash
git clone https://github.com/sparky8512/starlink-grpc-tools.git
cd starlink-grpc-tools
```

### 2. Install Python dependencies

```bash
pip install grpcio protobuf
```

### 3. Verify dish connectivity

Make sure you can access your Starlink dish:
- Open a browser and navigate to `http://192.168.100.1`
- You should see the Starlink web interface

If you're using a custom router, ensure that traffic to `192.168.100.1` is routed to your Starlink dish.

### 4. Copy the experiments scripts

Copy the experiment scripts to the `starlink-grpc-tools` directory:

```bash
cp /path/to/global-testbed/experiments/starlink_basic_experiments.py .
cp /path/to/global-testbed/experiments/starlink_ping_monitor.py .
```

## Available Experiments

### Ping Statistics Monitor (Real-time)

**Duration:** Continuous (runs until stopped with Ctrl+C)

**What it does:**
- Polls the dish once per second for ping statistics
- Extracts all ping-related fields from status and history data
- Filters out obsolete fields (SNR, seconds_to_* except seconds_to_first_non_empty_slot)
- Clears terminal and displays updated statistics each second
- Shows real-time ping performance metrics

**Use case:** Real-time monitoring of ping performance and latency statistics

**Run it:**
```bash
python3 starlink_ping_monitor.py
```

**Sample output:**
```
================================================================================
STARLINK PING STATISTICS MONITOR
================================================================================
Timestamp: 2024-01-15 10:30:45
Iteration: 42
Press Ctrl+C to stop
================================================================================

  ping_drop_rate                : 0.005
  ping_latency_ms_mean          : 28.345
  ping_latency_ms_p50           : 27.500
  ping_latency_ms_p95           : 35.200
  ping_latency_ms_p99           : 42.100
  pop_ping_drop_rate            : 0.003
  pop_ping_latency_ms           : 27.800
  seconds_to_first_non_empty_slot : 0.000

================================================================================
```

**Features:**
- ✅ Updates every second
- ✅ Clears terminal for clean display
- ✅ Shows iteration count
- ✅ Filters obsolete fields automatically
- ✅ Always includes seconds_to_first_non_empty_slot

**To stop:** Press `Ctrl+C`

---

### Experiment 1: Basic Status Monitor

**Duration:** 1 minute (12 samples, 5 seconds apart)

**What it does:**
- Monitors your dish's connection state
- Tracks upload/download speeds
- Measures latency to Starlink PoP
- Calculates obstruction percentage
- Records dish uptime

**Use case:** Quick health check of your Starlink connection

**Run it:**
```bash
python3 starlink_basic_experiments.py 1
```

**Sample output:**
```
[Sample 1/12] @ 2024-01-15T10:30:45.123456
  State: CONNECTED
  Uptime: 86400 seconds (24.0 hours)
  Obstruction: 2.3%
  Download: 147.52 Mbps
  Upload: 12.34 Mbps
  Latency: 28.5 ms
```

**Output file:** `starlink_status_YYYYMMDD_HHMMSS.json`

---

### Experiment 2: Obstruction Pattern Analysis

**Duration:** 30 seconds (instant analysis)

**What it does:**
- Analyzes obstruction patterns by direction
- Shows which compass directions have more obstructions
- Provides recommendations for dish placement
- Displays dish pointing information (azimuth, elevation)

**Use case:** Determine if you need to trim trees or relocate your dish

**Run it:**
```bash
python3 starlink_basic_experiments.py 2
```

**Sample output:**
```
DIRECTIONAL OBSTRUCTION MAP
----------------------------------------------------------------------
(Looking up at the sky, North is 0°, rotating clockwise)

Signal Quality by Direction (higher is better):
N (0°-30°)      12.5 dB ██████
NNE (30°-60°)   15.3 dB ███████
ENE (60°-90°)    8.2 dB ████
E (90°-120°)     3.1 dB █

RECOMMENDATIONS
----------------------------------------------------------------------
⚠ Your dish has minor obstructions (1-5%)
  This may cause occasional connectivity issues
```

**Output file:** `starlink_obstruction_YYYYMMDD_HHMMSS.json`

---

### Experiment 3: Performance Variability Analysis

**Duration:** 2 minutes (12 samples, 10 seconds apart)

**What it does:**
- Measures how stable your connection is over time
- Calculates average, min, max, and standard deviation for:
  - Download speed
  - Upload speed
  - Latency (and jitter)
- Assesses suitability for streaming, gaming, video calls

**Use case:** Understand if your connection is stable enough for specific applications

**Run it:**
```bash
python3 starlink_basic_experiments.py 3
```

**Sample output:**
```
[ 1/12] CONNECTED    | ↓145.23 Mbps | ↑12.45 Mbps | 28.3 ms | Drop:  0.0%
[ 2/12] CONNECTED    | ↓152.18 Mbps | ↑13.21 Mbps | 29.1 ms | Drop:  0.2%
...

VARIABILITY ANALYSIS
----------------------------------------------------------------------

Download Speed:
  Mean: 148.45 Mbps
  Min: 132.10 Mbps
  Max: 165.30 Mbps
  Std Dev: 8.23 Mbps
  Coefficient of Variation: 5.5%

STABILITY ASSESSMENT
----------------------------------------------------------------------
✓ Connection remained stable: CONNECTED
✓ Low download speed variability (CV < 15%)
  Good for streaming and downloads
✓ Low latency jitter (<10ms)
  Excellent for real-time applications
```

**Output file:** `starlink_variability_YYYYMMDD_HHMMSS.json`

---

## Understanding the Results

### Connection States

- **CONNECTED** - Dish is actively connected to satellites
- **SEARCHING** - Dish is looking for satellites
- **BOOTING** - Dish is starting up
- **STOWED** - Dish is in storage/travel mode
- **OBSTRUCTED** - Dish view is blocked
- **NO_SATS** - No satellites are visible

### Obstruction Impact

- **< 1%** - Minimal impact, excellent placement
- **1-5%** - Minor impact, may cause occasional issues
- **> 5%** - Significant impact, consider relocating dish

### Variability (Coefficient of Variation)

- **< 15%** - Stable connection, good for all use cases
- **15-30%** - Moderate variability, may see occasional buffering
- **> 30%** - High variability, connection may not be suitable for streaming

### Latency Jitter

- **< 10ms** - Excellent for gaming and video calls
- **10-20ms** - Acceptable for most applications
- **> 20ms** - May cause issues with real-time applications

## Troubleshooting

### Error: Cannot reach Starlink dish

**Solution:**
1. Verify dish is powered on
2. Check you're connected to Starlink network (or network that routes to dish)
3. Try accessing `http://192.168.100.1` in a browser
4. If using custom router, ensure port 9200 is accessible

### Error: Could not import starlink_grpc

**Solution:**
1. Make sure you're running the script from the `starlink-grpc-tools` directory
2. Or add `starlink-grpc-tools` to your PYTHONPATH:
   ```bash
   export PYTHONPATH=/path/to/starlink-grpc-tools:$PYTHONPATH
   ```

### High obstruction percentage

**Solution:**
- Use Experiment 2 to identify which directions have obstructions
- Trim trees or vegetation in those directions
- Consider relocating dish to higher position
- Ensure dish has clear view of the sky (especially north for northern hemisphere)

### Unstable connection (high variability)

**Solution:**
- Check for obstructions that may move (tree branches in wind)
- Verify dish mounting is secure
- Look for sources of interference
- Monitor during different times of day

## Data Files

All experiments save their data to JSON files with timestamps. You can:
- Import them into spreadsheet software for analysis
- Plot them with Python (matplotlib, pandas)
- Compare results over time
- Share with Starlink support if needed

Example Python script to plot results:

```python
import json
import matplotlib.pyplot as plt

# Load data
with open('starlink_variability_20240115_103045.json', 'r') as f:
    data = json.load(f)

# Extract timestamps and speeds
times = range(len(data))
downloads = [d['downlink_mbps'] for d in data]

# Plot
plt.plot(times, downloads)
plt.xlabel('Sample Number')
plt.ylabel('Download Speed (Mbps)')
plt.title('Starlink Download Speed Over Time')
plt.show()
```

## Integration with LEOScope

These experiments can be integrated into the LEOScope testbed:

1. **Scheduled Monitoring:** Run Experiment 1 periodically to track dish health
2. **Pre-Experiment Checks:** Run Experiment 2 before running network experiments
3. **Performance Baseline:** Use Experiment 3 to establish baseline before/after comparisons

See the main LEOScope documentation for details on integrating these into automated experiment workflows.

## No Subscription Required

All three experiments:
- ✅ Run entirely on your local network
- ✅ Only communicate with your dish at 192.168.100.1
- ✅ Do not require Starlink app
- ✅ Do not require external services
- ✅ Work with basic Starlink service
- ✅ No additional fees or subscriptions

## Safety Notes

- These scripts only **read** data from your dish
- They do **not** modify any settings
- They do **not** reboot or stow your dish
- Safe to run as often as you like

## Advanced Usage

### Running in a loop

To continuously monitor your connection:

```bash
# Run Experiment 1 every 5 minutes
while true; do 
    python3 starlink_basic_experiments.py 1
    sleep 300
done
```

### Logging to file

```bash
python3 starlink_basic_experiments.py 1 | tee -a starlink_monitor.log
```

### Running on schedule with cron

```bash
# Run every hour
0 * * * * cd /path/to/starlink-grpc-tools && python3 starlink_basic_experiments.py 1 >> /var/log/starlink.log 2>&1
```

## Contributing

Found an issue or have ideas for new experiments? Please open an issue or pull request in the global-testbed repository.

## References

- [Starlink gRPC Tools](https://github.com/sparky8512/starlink-grpc-tools)
- [Starlink Community Knowledge Base](https://github.com/starlink-community/knowledge-base/wiki)
- [LEOScope Documentation](../README.md)

## License

These experiments are part of the LEOScope project and follow the same license.
