"""
PicoScope 3000 Series (A API) Rapid Block Capture with CSV Export

This script demonstrates how to:
1. Initialize a PicoScope 3000 series oscilloscope
2. Configure channels A and B with appropriate voltage ranges
3. Set up a trigger on Channel B to capture signals of interest
4. Use segmented (rapid block) memory mode to capture multiple triggers
5. Convert the raw ADC data to voltage values (mV)
6. Save captured waveforms to CSV files for later analysis or plotting

Each capture segment is saved as an individual CSV file with timestamp information.
"""

import ctypes           # For C-compatible data types needed by PicoScope driver
import numpy as np      # For numerical operations on data
import os, time         # For file/directory operations and timing
import csv              # For saving data to CSV format
from datetime import datetime  # For timestamping saved files
from picosdk.ps3000a import ps3000a as ps  # PicoScope 3000A series driver
from picosdk.functions import adc2mV, assert_pico_ok  # Helper functions

# === CONFIGURATION PARAMETERS ===
# These settings control the behavior of the scope and data acquisition

NUM_SEGMENTS = 32        # Number of trigger events to capture in one run
SAMPLES_PER_SEGMENT = 10000  # Number of samples for each trigger event (increased for full 1ms capture)
TIMEBASE = 8             # Timebase index: controls sampling interval, 8 = 100 μs/div (approx 80ns sample interval)
RANGE_A = ps.PS3000A_RANGE['PS3000A_1V']   # Channel A: ±1V range for signal capture
RANGE_B = ps.PS3000A_RANGE['PS3000A_10V']  # Channel B: ±10V range for trigger signal
THRESHOLD_V = 4.5        # Trigger threshold voltage (volts) - scope will trigger when Ch B crosses this level
AUTO_TRIGGER_MS = 1000   # Auto-trigger timeout in ms - will force trigger if none detected in this time
CSV_DIR = 'captures/try_2.5'  # Directory to save captured data in CSV format
posix = False            # Set True when running on Linux/macOS for path handling

# Create output directory if it doesn't exist
os.makedirs(CSV_DIR, exist_ok=True)  # Will not raise error if directory exists

# === OPEN & POWER-HANDLING ===
def open_scope():
    """
    Open connection to the PicoScope device and handle power conditions.
    
    The PicoScope can be in different power states depending on the USB connection:
    - Normal powered operation (status code 0)
    - USB 3.0 device on USB 2.0 port (status code 286)
    - No power supply connected (status code 282)
    
    Returns:
        chandle: Device handle for subsequent API calls
    """
    chandle = ctypes.c_int16()  # Create a handle (pointer) for the device
    status = ps.ps3000aOpenUnit(ctypes.byref(chandle), None)  # Open picoscope
        # takes a pointer to a handle and an optional serial number (None = first found)
    try:
        assert_pico_ok(status)  # Check if open was successful
    except:
        # Handle USB‑power states 282/286
        if status in (282, 286):
            # If power issue, try to change power source setting to match current state
            print(f"Handling power condition: {status}")
            status = ps.ps3000aChangePowerSource(chandle, status)
            assert_pico_ok(status)  # Check if power setting was successful
        else:
            raise  # Re-raise any other errors
    print(f"PicoScope opened successfully, handle: {chandle.value}")
    return chandle

# === SETUP CHANNELS & TRIGGER ===
def setup_channels(chandle):
    """
    Configure scope channels and trigger settings.
    
    Sets up:
    - Channel A for signal capture at ±1V range
    - Channel B for trigger detection at ±10V range
    - Rising edge trigger on Channel B at THRESHOLD_V
    
    Args:
        chandle: Device handle returned from open_scope()
    """
    # Channel A (data) configuration
    # Parameters: handle, channel, enable (1=on), coupling (DC), range, offset
    assert_pico_ok(ps.ps3000aSetChannel(
        chandle,
        ps.PS3000A_CHANNEL['PS3000A_CHANNEL_A'],  # Channel identifier
        1,  # Enable channel (1=enabled, 0=disabled)
        ps.PS3000A_COUPLING['PS3000A_DC'],  # DC coupling (vs AC)
        RANGE_A,  # Voltage range (±1V)
        0   # Zero offset
    ))
    print("Channel A configured: ±1V range, DC coupling")
    
    # Channel B (trigger) configuration
    assert_pico_ok(ps.ps3000aSetChannel(
        chandle,
        ps.PS3000A_CHANNEL['PS3000A_CHANNEL_B'],
        1,  # Enable channel
        ps.PS3000A_COUPLING['PS3000A_DC'],  # DC coupling
        RANGE_B,  # Voltage range (±10V)
        0   # Zero offset
    ))
    print("Channel B configured: ±10V range, DC coupling")

    # Get maximum ADC value for trigger threshold conversion (ADC stands for Analog-to-Digital Converter)
    maxADC = ctypes.c_int16()  # Create variable to store max ADC value
    assert_pico_ok(ps.ps3000aMaximumValue(chandle, ctypes.byref(maxADC))) # Max ADC value is needed for scaling
    print(f"Maximum ADC count: {maxADC.value}")
    
    # Convert trigger voltage threshold to ADC counts
    # The ADC range (-maxADC to +maxADC) maps to the voltage range (-10V to +10V)
    max_voltage_range = 10  # Half of the total range of RANGE_B (±10V = 20V total)
    thr_count = int(THRESHOLD_V * maxADC.value / max_voltage_range)
    print(f"Trigger threshold: {THRESHOLD_V}V = {thr_count} ADC counts")

    # Configure simple trigger on Channel B
    assert_pico_ok(ps.ps3000aSetSimpleTrigger(
        chandle,
        1,  # Enable trigger (1=enabled)
        ps.PS3000A_CHANNEL['PS3000A_CHANNEL_B'],  # Trigger on Channel B
        thr_count,  # Trigger threshold in ADC counts
        ps.PS3000A_THRESHOLD_DIRECTION['PS3000A_RISING'],  # Trigger on rising edge
        0,  # Zero delay (trigger immediately when condition met)
        AUTO_TRIGGER_MS  # Auto-trigger after this many milliseconds if no trigger detected
    ))
    print(f"Trigger configured: Rising edge on Channel B at {THRESHOLD_V}V with {AUTO_TRIGGER_MS}ms timeout")

# === SEGMENTED MEMORY SETUP ===
def setup_segments(chandle):
    """
    Configure the scope's memory into multiple segments for rapid block capture.
    
    Segmented memory allows capturing multiple trigger events in quick succession
    by dividing the scope's memory into separate segments.
    
    Args:
        chandle: Device handle
        
    Returns:
        int: Maximum number of samples per segment allowed by the device
    """
    # Create variable to receive maximum samples info
    maxSamples = ctypes.c_int32()
    
    # Divide memory into segments
    assert_pico_ok(ps.ps3000aMemorySegments(
        chandle,
        NUM_SEGMENTS,  # Number of segments to create
        ctypes.byref(maxSamples)  # Output: max samples per segment
    ))
    
    # Set the number of captures to collect
    assert_pico_ok(ps.ps3000aSetNoOfCaptures(
        chandle,
        NUM_SEGMENTS
    ))
    
    print(f"Memory configured: {NUM_SEGMENTS} segments with up to {maxSamples.value} samples each")
    # Return maxSamples per segment (may differ from SAMPLES_PER_SEGMENT due to hardware limitations)
    return maxSamples.value

# === ALLOCATE BUFFERS FOR DATA ===
def allocate_buffers(n_segments, n_samples):
    """
    Create memory buffers for each segment for both channels.
    
    For each segment, we need separate buffers for each channel (A and B).
    These buffers will hold the raw ADC values before conversion to voltages.
    
    Args:
        n_segments: Number of segments to allocate buffers for
        n_samples: Number of samples per segment
        
    Returns:
        tuple: Two lists of buffers (bufs_a, bufs_b) for channels A and B
    """
    bufs_a = []  # List to hold Channel A buffers
    bufs_b = []  # List to hold Channel B buffers
    
    # For each memory segment, create buffers for both channels
    for seg in range(n_segments):
        # Create a C array of 16-bit integers for each channel
        bufa = (ctypes.c_int16 * n_samples)()  # Channel A buffer
        bufb = (ctypes.c_int16 * n_samples)()  # Channel B buffer
        bufs_a.append(bufa)
        bufs_b.append(bufb)
    
    print(f"Allocated {n_segments} buffers with {n_samples} samples each for both channels")
    return bufs_a, bufs_b

# === REGISTER BUFFERS WITH DEVICE ===
def set_data_buffers(chandle, bufs_a, bufs_b, n_samples):
    """
    Register the buffer locations with the PicoScope driver for data collection.
    
    The driver needs to know where to store the data for each segment and channel.
    This function tells the driver which memory locations to use.
    
    Args:
        chandle: Device handle
        bufs_a: List of Channel A buffers
        bufs_b: List of Channel B buffers
        n_samples: Number of samples per buffer
    """
    # For each segment, set the data buffer locations for both channels
    for idx in range(len(bufs_a)):
        # Register Channel A buffer for this segment
        assert_pico_ok(ps.ps3000aSetDataBuffers(
            chandle,
            ps.PS3000A_CHANNEL['PS3000A_CHANNEL_A'],  # Channel identifier
            bufs_a[idx],  # Buffer for max values
            None,  # Buffer for min values (None = not using min buffer)
            n_samples,  # Number of samples in buffer
            idx,  # Segment index
            ps.PS3000A_RATIO_MODE['PS3000A_RATIO_MODE_NONE']  # No downsampling
        ))
        
        # Register Channel B buffer for this segment
        assert_pico_ok(ps.ps3000aSetDataBuffers(
            chandle,
            ps.PS3000A_CHANNEL['PS3000A_CHANNEL_B'],  # Channel identifier
            bufs_b[idx],  # Buffer for max values
            None,  # Buffer for min values (None = not using min buffer)
            n_samples,  # Number of samples in buffer
            idx,  # Segment index
            ps.PS3000A_RATIO_MODE['PS3000A_RATIO_MODE_NONE']  # No downsampling
        ))
    
    print(f"Registered {len(bufs_a)} buffer pairs with the device")

# === MAIN CAPTURE FUNCTION ===
def capture_and_save():
    """
    Main function to perform the capture and save data to CSV files.
    
    This function orchestrates the entire capture process:
    1. Initialize the scope
    2. Configure channels and trigger
    3. Setup memory segments
    4. Start capture
    5. Wait for completion
    6. Retrieve data
    7. Convert and save to CSV files
    8. Clean up
    """
    # Open the scope and get handle
    chandle = open_scope()
    
    # Setup channels and trigger
    setup_channels(chandle)
    
    # Configure memory segments and get max samples per segment
    seg_max = setup_segments(chandle)
    
    # Use the smaller of requested samples or max available
    n_samples = min(seg_max, SAMPLES_PER_SEGMENT)
    print(f"Using {n_samples} samples per segment")

    # Get timebase info for actual timing calculations
    # The timebase value determines the sampling interval
    timeIntervalNs = ctypes.c_float()  # Will hold the actual time interval between samples
    returnedMaxSamples = ctypes.c_int16()  # Will hold max samples possible at this timebase
    
    # Query the device for timebase information
    status = ps.ps3000aGetTimebase2(
        chandle, TIMEBASE, n_samples, ctypes.byref(timeIntervalNs), 
        1, ctypes.byref(returnedMaxSamples), 0
    )
    assert_pico_ok(status)
    
    print(f"Timebase {TIMEBASE} gives {timeIntervalNs.value} ns interval between samples")
    
    # Calculate how many samples we need to cover 1ms of capture time
    time_required_ns = 1_000_000  # 1ms in nanoseconds
    samples_needed = int(time_required_ns / timeIntervalNs.value) + 100  # Add margin
    
    # Warn if we don't have enough samples for full 1ms
    if samples_needed > n_samples:
        print(f"WARNING: Need {samples_needed} samples to cover 1ms, but only using {n_samples}")
    else:
        print(f"Using {n_samples} samples to cover 1ms (need {samples_needed})")

    # Allocate and register buffers for data storage
    bufs_a, bufs_b = allocate_buffers(NUM_SEGMENTS, n_samples)
    set_data_buffers(chandle, bufs_a, bufs_b, n_samples)

    print("Starting block capture...")
    # Start block capture
    assert_pico_ok(ps.ps3000aRunBlock(
        chandle,
        0,               # Number of pre-trigger samples
        n_samples,       # Number of post-trigger samples
        TIMEBASE,        # Timebase setting
        1,               # Segment index (always 1 for first call)
        None,            # Time indisposed ms (NULL = not needed)
        0,               # Segment index
        None,            # lpReady callback (NULL = not using callback)
        None             # pParameter for callback (NULL = not using callback)
    ))

    # Wait until capture is ready (device says data collection is complete)
    ready = ctypes.c_int16(0)
    while not ready.value:
        ps.ps3000aIsReady(chandle, ctypes.byref(ready))
        time.sleep(0.01)  # Short sleep to prevent CPU hogging
    
    print("Capture complete, retrieving data...")

    # Retrieve all segments of data at once
    samples_ret = ctypes.c_int32(n_samples)  # Will contain actual samples returned
    overflow = (ctypes.c_int16 * NUM_SEGMENTS)()  # Array to store overflow flags for each segment
    
    # Get all values in bulk from all segments
    assert_pico_ok(ps.ps3000aGetValuesBulk(
        chandle,
        ctypes.byref(samples_ret),  # Actual number of samples (output)
        0,                          # Start segment
        NUM_SEGMENTS - 1,           # End segment
        1,                          # Downsampling ratio (1 = no downsampling)
        ps.PS3000A_RATIO_MODE['PS3000A_RATIO_MODE_NONE'],  # No downsampling
        ctypes.byref(overflow)      # Overflow flags (output)
    ))
    
    print(f"Retrieved {samples_ret.value} samples per segment")

    # Get maximum ADC value for data conversion
    maxADC = ctypes.c_int16()
    assert_pico_ok(ps.ps3000aMaximumValue(chandle, ctypes.byref(maxADC)))

    # Process and save each segment
    for idx in range(NUM_SEGMENTS):
        # Convert raw ADC counts to millivolts using helper function
        # The adc2mV function scales the raw ADC values to actual voltages
        # based on the voltage range and maximum ADC count
        data_a = adc2mV(bufs_a[idx], RANGE_A, maxADC)  # Convert Channel A data to mV
        data_b = adc2mV(bufs_b[idx], RANGE_B, maxADC)  # Convert Channel B data to mV

        # Create filename with timestamp and segment number
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = f"seg{idx+1:02d}_{timestamp}.csv"
        path = os.path.join(CSV_DIR, fname)

        # Create time array in nanoseconds, spanning exactly 1ms regardless of actual samples
        # This ensures consistent time axis when plotting
        time_ns = np.linspace(0, 1_000_000, n_samples)  # 0 to 1ms (1,000,000 ns)

        # Write data to CSV file
        with open(path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Time_ns', 'A_mV', 'B_mV'])  # Header row
            for i in range(n_samples):
                writer.writerow([time_ns[i], data_a[i], data_b[i]])

        print(f"Saved segment {idx+1} to {path}")

    # Stop the scope
    ps.ps3000aStop(chandle)
    print("Scope stopped")
    
    # Close the device connection
    ps.ps3000aCloseUnit(chandle)
    print("Scope connection closed")

# Main execution
if __name__ == '__main__':
    print("=== PicoScope 3000 Series Rapid Block Capture ===")
    capture_and_save()
    print("=== Capture process completed successfully ===")
