import ctypes
import numpy as np
import os, time
import csv
from datetime import datetime
from picosdk.ps3000a import ps3000a as ps
from picosdk.functions import adc2mV, assert_pico_ok

# === CONFIGURATION ===
NUM_SEGMENTS       = 32          # Number of trigger captures (segments)
SAMPLES_PER_SEGMENT = 1000       # Samples per segment (adjustable)
TIMEBASE            = 8          # 100 µs/div (~1 ms total)
RANGE_A             = ps.PS3000A_RANGE['PS3000A_1V']   # ±1 V
RANGE_B             = ps.PS3000A_RANGE['PS3000A_10V']  # ±10 V (trigger)
THRESHOLD_V         = 4.5        # Trigger level (volts)
AUTO_TRIGGER_MS     = 1000       # Auto‑trigger timeout (ms)
CSV_DIR             = 'captures'
posix = False         # Set True on Linux/macOS

os.makedirs(CSV_DIR, exist_ok=True)

# === OPEN & POWER-HANDLING ===
def open_scope():
    chandle = ctypes.c_int16()
    status = ps.ps3000aOpenUnit(ctypes.byref(chandle), None)
    try:
        assert_pico_ok(status)
    except:
        # Handle USB‑power states 282/286
        if status in (282, 286):
            status = ps.ps3000aChangePowerSource(chandle, status)
            assert_pico_ok(status)
        else:
            raise
    return chandle

# === SETUP CHANNELS & TRIGGER ===
def setup_channels(chandle):
    # Channel A (data)
    assert_pico_ok(ps.ps3000aSetChannel(
        chandle,
        ps.PS3000A_CHANNEL['PS3000A_CHANNEL_A'],
        1,  # enable
        ps.PS3000A_COUPLING['PS3000A_DC'],
        RANGE_A,
        0   # offset
    ))
    # Channel B (trigger)
    assert_pico_ok(ps.ps3000aSetChannel(
        chandle,
        ps.PS3000A_CHANNEL['PS3000A_CHANNEL_B'],
        1,
        ps.PS3000A_COUPLING['PS3000A_DC'],
        RANGE_B,
        0
    ))

    # Convert THRESHOLD_V to ADC counts
    maxADC = ctypes.c_int16()
    assert_pico_ok(ps.ps3000aMaximumValue(chandle, ctypes.byref(maxADC)))
    thr_count = int(THRESHOLD_V * maxADC.value / (RANGE_B * 1000.0))

    # Simple rising‑edge trigger on B
    assert_pico_ok(ps.ps3000aSetSimpleTrigger(
        chandle,
        1,
        ps.PS3000A_CHANNEL['PS3000A_CHANNEL_B'],
        thr_count,
        ps.PS3000A_THRESHOLD_DIRECTION['PS3000A_RISING'],
        0,
        AUTO_TRIGGER_MS
    ))

# === SEGMENTED MEMORY ===
def setup_segments(chandle):
    maxSamples = ctypes.c_int32()
    assert_pico_ok(ps.ps3000aMemorySegments(
        chandle,
        NUM_SEGMENTS,
        ctypes.byref(maxSamples)
    ))
    assert_pico_ok(ps.ps3000aSetNoOfCaptures(
        chandle,
        NUM_SEGMENTS
    ))
    # Return maxSamples per segment (may differ from SAMPLES_PER_SEGMENT)
    return maxSamples.value

# === ALLOCATE BUFFERS ===
def allocate_buffers(n_segments, n_samples):
    bufs_a = []
    bufs_b = []
    for seg in range(n_segments):
        bufa = (ctypes.c_int16 * n_samples)()
        bufb = (ctypes.c_int16 * n_samples)()
        bufs_a.append(bufa)
        bufs_b.append(bufb)
    return bufs_a, bufs_b

# === SET DATA POINTERS ===
def set_data_buffers(chandle, bufs_a, bufs_b, n_samples):
    for idx in range(len(bufs_a)):
        assert_pico_ok(ps.ps3000aSetDataBuffers(
            chandle,
            ps.PS3000A_CHANNEL['PS3000A_CHANNEL_A'],
            bufs_a[idx],
            None,
            n_samples,
            idx,
            ps.PS3000A_RATIO_MODE['PS3000A_RATIO_MODE_NONE']
        ))
        assert_pico_ok(ps.ps3000aSetDataBuffers(
            chandle,
            ps.PS3000A_CHANNEL['PS3000A_CHANNEL_B'],
            bufs_b[idx],
            None,
            n_samples,
            idx,
            ps.PS3000A_RATIO_MODE['PS3000A_RATIO_MODE_NONE']
        ))

# === CAPTURE ===
def capture_and_save():
    chandle = open_scope()
    setup_channels(chandle)
    seg_max = setup_segments(chandle)
    n_samples = min(seg_max, SAMPLES_PER_SEGMENT)

    # Allocate and register buffers
    bufs_a, bufs_b = allocate_buffers(NUM_SEGMENTS, n_samples)
    set_data_buffers(chandle, bufs_a, bufs_b, n_samples)

    # Start block capture
    assert_pico_ok(ps.ps3000aRunBlock(
        chandle,
        0,
        n_samples,
        TIMEBASE,
        1,
        None,
        0,
        None,
        None
    ))

    # Wait until capture ready
    ready = ctypes.c_int16(0)
    while not ready.value:
        ps.ps3000aIsReady(chandle, ctypes.byref(ready))
        time.sleep(0.01)

    # Retrieve all segments
    samples_ret = ctypes.c_int32(n_samples)
    overflow = (ctypes.c_int16 * NUM_SEGMENTS)()
    assert_pico_ok(ps.ps3000aGetValuesBulk(
        chandle,
        ctypes.byref(samples_ret),
        0,
        NUM_SEGMENTS - 1,
        1,
        ps.PS3000A_RATIO_MODE['PS3000A_RATIO_MODE_NONE'],
        ctypes.byref(overflow)
    ))

    # Convert & save
    maxADC = ctypes.c_int16()
    assert_pico_ok(ps.ps3000aMaximumValue(chandle, ctypes.byref(maxADC)))

    for idx in range(NUM_SEGMENTS):
        data_a = adc2mV(bufs_a[idx], RANGE_A, maxADC)
        data_b = adc2mV(bufs_b[idx], RANGE_B, maxADC)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = f"seg{idx+1:02d}_{timestamp}.csv"
        path = os.path.join(CSV_DIR, fname)

        with open(path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Index', 'A (mV)', 'B (mV)'])
            for i in range(n_samples):
                writer.writerow([i, data_a[i], data_b[i]])

        print(f"Saved segment {idx+1} to {path}")

    ps.ps3000aStop(chandle)
    ps.ps3000aCloseUnit(chandle)

if __name__ == '__main__':
    capture_and_save()
