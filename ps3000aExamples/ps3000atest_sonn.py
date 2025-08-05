#
# PS3000A Streaming with CSV Export
# This example captures streaming data and saves it to CSV files whenever the buffer is full

import ctypes
import numpy as np
from picosdk.ps3000a import ps3000a as ps
from picosdk.functions import adc2mV, assert_pico_ok
import time
import csv
import os
from datetime import datetime

# Create chandle and status ready for use
chandle = ctypes.c_int16()
status = {}

# Open PicoScope device
status["openunit"] = ps.ps3000aOpenUnit(ctypes.byref(chandle), None)

try:
    assert_pico_ok(status["openunit"])
except:
    powerStatus = status["openunit"]
    if powerStatus == 286:
        status["changePowerSource"] = ps.ps3000aChangePowerSource(chandle, powerStatus)
    elif powerStatus == 282:
        status["changePowerSource"] = ps.ps3000aChangePowerSource(chandle, powerStatus)
    else:
        raise
    assert_pico_ok(status["changePowerSource"])

# Channel settings
enabled = 1
disabled = 0
analogue_offset = 0.0
channel_range = ps.PS3000A_RANGE['PS3000A_2V']

# Set up channel A
status["setChA"] = ps.ps3000aSetChannel(chandle,
                                        ps.PS3000A_CHANNEL['PS3000A_CHANNEL_A'],
                                        enabled,
                                        ps.PS3000A_COUPLING['PS3000A_DC'],
                                        channel_range,
                                        analogue_offset)
assert_pico_ok(status["setChA"])

# Set up channel B
status["setChB"] = ps.ps3000aSetChannel(chandle,
                                        ps.PS3000A_CHANNEL['PS3000A_CHANNEL_B'],
                                        enabled,
                                        ps.PS3000A_COUPLING['PS3000A_DC'],
                                        channel_range,
                                        analogue_offset)
assert_pico_ok(status["setChB"])

# Buffer configuration
sizeOfOneBuffer = 1000  # Size of each buffer
numBuffersToCapture = 5  # Number of buffers before stopping
totalSamples = sizeOfOneBuffer * numBuffersToCapture

# Create buffers
bufferAMax = np.zeros(shape=sizeOfOneBuffer, dtype=np.int16)
bufferBMax = np.zeros(shape=sizeOfOneBuffer, dtype=np.int16)
memory_segment = 0

# Set data buffers
status["setDataBuffersA"] = ps.ps3000aSetDataBuffers(chandle,
                                                     ps.PS3000A_CHANNEL['PS3000A_CHANNEL_A'],
                                                     bufferAMax.ctypes.data_as(ctypes.POINTER(ctypes.c_int16)),
                                                     None,
                                                     sizeOfOneBuffer,
                                                     memory_segment,
                                                     ps.PS3000A_RATIO_MODE['PS3000A_RATIO_MODE_NONE'])
assert_pico_ok(status["setDataBuffersA"])

status["setDataBuffersB"] = ps.ps3000aSetDataBuffers(chandle,
                                                     ps.PS3000A_CHANNEL['PS3000A_CHANNEL_B'],
                                                     bufferBMax.ctypes.data_as(ctypes.POINTER(ctypes.c_int16)),
                                                     None,
                                                     sizeOfOneBuffer,
                                                     memory_segment,
                                                     ps.PS3000A_RATIO_MODE['PS3000A_RATIO_MODE_NONE'])
assert_pico_ok(status["setDataBuffersB"])

# Get maximum ADC value for conversion
maxADC = ctypes.c_int16()
status["maximumValue"] = ps.ps3000aMaximumValue(chandle, ctypes.byref(maxADC))
assert_pico_ok(status["maximumValue"])

# CSV export setup
csv_directory = r"c:\Users\tberhanu\Desktop\workspace\picosdk-python-wrappers\captured_data"
os.makedirs(csv_directory, exist_ok=True)
file_counter = 0

def save_buffer_to_csv(buffer_a, buffer_b, sample_interval_ns, buffer_num):
    """Save buffer data to CSV file"""
    global file_counter
    
    # Convert ADC counts to mV
    adc2mVChA = adc2mV(buffer_a, channel_range, maxADC)
    adc2mVChB = adc2mV(buffer_b, channel_range, maxADC)
    
    # Create time array
    time_ns = np.arange(len(buffer_a)) * sample_interval_ns
    
    # Create filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"capture_{timestamp}_buffer_{file_counter:03d}.csv"
    filepath = os.path.join(csv_directory, filename)
    
    # Write to CSV
    with open(filepath, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Time_ns', 'Channel_A_mV', 'Channel_B_mV'])
        for i in range(len(buffer_a)):
            writer.writerow([time_ns[i], adc2mVChA[i], adc2mVChB[i]])
    
    print(f"Buffer {buffer_num} saved to: {filename}")
    file_counter += 1

# Streaming setup
sampleInterval = ctypes.c_int32(250)  # 250 μs
sampleUnits = ps.PS3000A_TIME_UNITS['PS3000A_US']
maxPreTriggerSamples = 0
autoStopOn = 1
downsampleRatio = 1

status["runStreaming"] = ps.ps3000aRunStreaming(chandle,
                                                ctypes.byref(sampleInterval),
                                                sampleUnits,
                                                maxPreTriggerSamples,
                                                totalSamples,
                                                autoStopOn,
                                                downsampleRatio,
                                                ps.PS3000A_RATIO_MODE['PS3000A_RATIO_MODE_NONE'],
                                                sizeOfOneBuffer)
assert_pico_ok(status["runStreaming"])

actualSampleInterval = sampleInterval.value
actualSampleIntervalNs = actualSampleInterval * 1000

print(f"Capturing at sample interval {actualSampleIntervalNs} ns")
print(f"Buffer size: {sizeOfOneBuffer} samples")
print(f"Will capture {numBuffersToCapture} buffers")
print(f"CSV files will be saved to: {csv_directory}")

# Global variables for callback
nextSample = 0
autoStopOuter = False
wasCalledBack = False
buffers_captured = 0

def streaming_callback(handle, noOfSamples, startIndex, overflow, triggerAt, triggered, autoStop, param):
    global nextSample, autoStopOuter, wasCalledBack, buffers_captured
    wasCalledBack = True
    
    print(f"Callback triggered: noOfSamples={noOfSamples}, startIndex={startIndex}")
    
    # Save data regardless of buffer size (remove the exact size check)
    if noOfSamples > 0:
        # Copy current buffer data
        buffer_a_copy = bufferAMax[startIndex:startIndex + noOfSamples].copy()
        buffer_b_copy = bufferBMax[startIndex:startIndex + noOfSamples].copy()
        
        # Save to CSV
        save_buffer_to_csv(buffer_a_copy, buffer_b_copy, actualSampleIntervalNs, buffers_captured)
        buffers_captured += 1
    
    nextSample += noOfSamples
    if autoStop:
        autoStopOuter = True

# Convert callback to C function pointer
cFuncPtr = ps.StreamingReadyType(streaming_callback)

# Main data collection loop
print("Starting data collection...")
max_iterations = 1000  # Prevent infinite loop
iteration_count = 0

while nextSample < totalSamples and not autoStopOuter and iteration_count < max_iterations:
    wasCalledBack = False
    status["getStreamingLastestValues"] = ps.ps3000aGetStreamingLatestValues(chandle, cFuncPtr, None)
    
    if not wasCalledBack:
        time.sleep(0.01)
    
    iteration_count += 1
    
    # Print progress every 100 iterations
    if iteration_count % 100 == 0:
        print(f"Iteration {iteration_count}, nextSample: {nextSample}")

print(f"Data collection complete. Captured {buffers_captured} buffers.")
print(f"Total iterations: {iteration_count}")
print(f"Final nextSample: {nextSample}")

# Stop and close
status["stop"] = ps.ps3000aStop(chandle)
assert_pico_ok(status["stop"])

status["close"] = ps.ps3000aCloseUnit(chandle)
assert_pico_ok(status["close"])

print("Device closed successfully.")
print(f"All CSV files saved in: {csv_directory}")
