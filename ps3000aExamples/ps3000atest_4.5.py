import ctypes
import numpy as np
from picosdk.ps3000a import ps3000a as ps
from picosdk.functions import adc2mV, assert_pico_ok
import os
from datetime import datetime
import csv
import time

# Configuration Parameters
NUM_SEGMENTS = 32
SAMPLES_PER_SEGMENT = 500000
CHANNEL_A_RANGE = ps.PS3000A_RANGE['PS3000A_1V']
CHANNEL_B_RANGE = ps.PS3000A_RANGE['PS3000A_10V']
SAMPLING_INTERVAL = 8  # Adjusted to match screenshot (100us/div)
CAPTURE_DIR = "captures"
os.makedirs(CAPTURE_DIR, exist_ok=True)

# Initialize PicoScope
def open_scope():
    chandle = ctypes.c_int16()
    status = ps.ps3000aOpenUnit(ctypes.byref(chandle), None)

    try:
        assert_pico_ok(status)
    except:
        powerstate = status
        if powerstate == 282:
            print("Connecting external power supply...")
            status = ps.ps3000aChangePowerSource(chandle, powerstate)
            assert_pico_ok(status)
        elif powerstate == 286:
            print("USB 3.0 device connected to a USB 2.0 port, switching modes...")
            status = ps.ps3000aChangePowerSource(chandle, powerstate)
            assert_pico_ok(status)
        else:
            raise Exception(f"Unhandled PicoScope powerstate error: {powerstate}")

    return chandle

# Setup channels
def setup_channels(chandle):
    # Channel A
    ps.ps3000aSetChannel(chandle, ps.PS3000A_CHANNEL['PS3000A_CHANNEL_A'],
                         1, ps.PS3000A_COUPLING['PS3000A_DC'], CHANNEL_A_RANGE, 0)
    # Channel B (Trigger)
    ps.ps3000aSetChannel(chandle, ps.PS3000A_CHANNEL['PS3000A_CHANNEL_B'],
                         1, ps.PS3000A_COUPLING['PS3000A_DC'], CHANNEL_B_RANGE, 0)

# Setup trigger on Channel B
def setup_trigger(chandle):
    threshold = int(4.5 / 10.0 * 32767)  # Convert to ADC counts
    ps.ps3000aSetSimpleTrigger(chandle, 1, ps.PS3000A_CHANNEL['PS3000A_CHANNEL_B'],
                               threshold, ps.PS3000A_THRESHOLD_DIRECTION['PS3000A_RISING'],
                               0, 1000)

# Configure Segmented Memory
def setup_segments(chandle):
    nMaxSamples = ctypes.c_int32()
    ps.ps3000aMemorySegments(chandle, NUM_SEGMENTS, ctypes.byref(nMaxSamples))

# Capture segments
def capture_segments(chandle):
    timebase = SAMPLING_INTERVAL
    overflow = (ctypes.c_int16 * NUM_SEGMENTS)()
    
    buffers_a = []
    buffers_b = []

    for i in range(NUM_SEGMENTS):
        buffer_a = (ctypes.c_int16 * SAMPLES_PER_SEGMENT)()
        buffer_b = (ctypes.c_int16 * SAMPLES_PER_SEGMENT)()
        buffers_a.append(buffer_a)
        buffers_b.append(buffer_b)

        ps.ps3000aSetDataBuffer(chandle, ps.PS3000A_CHANNEL['PS3000A_CHANNEL_A'],
                                buffer_a, SAMPLES_PER_SEGMENT, i, 0)
        ps.ps3000aSetDataBuffer(chandle, ps.PS3000A_CHANNEL['PS3000A_CHANNEL_B'],
                                buffer_b, SAMPLES_PER_SEGMENT, i, 0)

    ps.ps3000aRunBlock(chandle, 0, SAMPLES_PER_SEGMENT, timebase, 1, None, 0, None, None)

    ready = ctypes.c_int16(0)
    while not ready.value:
        ps.ps3000aIsReady(chandle, ctypes.byref(ready))
        time.sleep(0.1)

    samples_collected = ctypes.c_int32(SAMPLES_PER_SEGMENT)
    ps.ps3000aGetValuesBulk(chandle, ctypes.byref(samples_collected), 0, NUM_SEGMENTS - 1, 1, 0, overflow)

    return buffers_a, buffers_b

# Save buffers to CSV
def save_to_csv(buffers_a, buffers_b, chandle):
    maxADC = ctypes.c_int16()
    ps.ps3000aMaximumValue(chandle, ctypes.byref(maxADC))

    for idx, (buff_a, buff_b) in enumerate(zip(buffers_a, buffers_b)):
        data_a = adc2mV(buff_a, CHANNEL_A_RANGE, maxADC)
        data_b = adc2mV(buff_b, CHANNEL_B_RANGE, maxADC)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"segment_{idx+1}_{timestamp}.csv"
        filepath = os.path.join(CAPTURE_DIR, filename)

        with open(filepath, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(['Sample', 'Channel A (mV)', 'Channel B (mV)'])
            for sample_idx in range(SAMPLES_PER_SEGMENT):
                writer.writerow([sample_idx, data_a[sample_idx], data_b[sample_idx]])

        print(f"Segment {idx+1} saved to {filepath}")

# Main capturing loop
def main():
    chandle = open_scope()
    setup_channels(chandle)
    setup_trigger(chandle)
    setup_segments(chandle)

    try:
        while True:
            buffers_a, buffers_b = capture_segments(chandle)
            save_to_csv(buffers_a, buffers_b, chandle)
            print("Buffer full - All segments saved. Restarting capture...")
            time.sleep(1)  # Small delay before restarting capture

    except KeyboardInterrupt:
        print("Capture stopped by user.")

    finally:
        ps.ps3000aStop(chandle)
        ps.ps3000aCloseUnit(chandle)
        print("PicoScope closed successfully.")

if __name__ == '__main__':
    main()
