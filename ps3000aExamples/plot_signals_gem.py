#
# Signal Plotting Script for PS3000A Captured Data
# This script reads CSV files from the captured_data directory and plots both channels
# CORRECTED VERSION

import os
import csv
import matplotlib.pyplot as plt
import numpy as np
from glob import glob

# Configuration
# IMPORTANT: Update this path to your directory containing the CSV files.
csv_directory = r"c:\Users\tberhanu\Desktop\workspace\picosdk-python-wrappers\captures_o4_2"
TOTAL_CAPTURE_TIME_MS = 10.0 # Total capture time in milliseconds (from PicoScope UI)


def read_csv_file(filepath):
    """Read CSV file and return index, channel A, and channel B data"""
    index_data = []
    channel_a_data = []
    channel_b_data = []
    
    try:
        with open(filepath, 'r') as file:
            reader = csv.reader(file)
            header = next(reader)  # Skip header row
            
            for row in reader:
                if len(row) >= 3:
                    index_data.append(float(row[0]))
                    channel_a_data.append(float(row[1]))
                    channel_b_data.append(float(row[2]))
    
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return None, None, None
    
    return np.array(index_data), np.array(channel_a_data), np.array(channel_b_data)

def plot_single_file(filepath):
    """Plot data from a single CSV file with dual Y-axes."""
    index_data, channel_a, channel_b = read_csv_file(filepath)
    
    if index_data is None:
        return False
    
    # --- FIX 1: Generate a proper time axis ---
    num_samples = len(index_data)
    time_ms = np.linspace(0, TOTAL_CAPTURE_TIME_MS, num=num_samples)
    
    filename = os.path.basename(filepath)
    
    # --- FIX 2: Use dual Y-axes for clarity ---
    fig, ax1 = plt.subplots(figsize=(12, 8))
    
    # Plot Channel A on the primary Y-axis (left)
    color_a = 'blue'
    ax1.set_xlabel('Time (ms)')
    ax1.set_ylabel('Channel A (mV)', color=color_a)
    line1 = ax1.plot(time_ms, channel_a, color=color_a, label='Channel A', linewidth=1)
    ax1.tick_params(axis='y', labelcolor=color_a)
    ax1.grid(True, which='both', linestyle='--', linewidth=0.5, alpha=0.7)

    # Create a secondary Y-axis sharing the same X-axis
    ax2 = ax1.twinx()
    
    # Plot Channel B on the secondary Y-axis (right)
    color_b = 'red'
    ax2.set_ylabel('Channel B (mV)', color=color_b)
    line2 = ax2.plot(time_ms, channel_b, color=color_b, label='Channel B', linewidth=1)
    ax2.tick_params(axis='y', labelcolor=color_b)
    
    plt.title(f'PicoScope Signals - {filename}')
    
    # Combine legends from both axes
    lines = line1 + line2
    labels = [l.get_label() for l in lines]
    ax1.legend(lines, labels, loc='upper right')
    
    fig.tight_layout()
    
    return True

def plot_all_files_subplots():
    """Plot data from all CSV files in separate subplots with dual axes."""
    csv_files = sorted(glob(os.path.join(csv_directory, "*.csv")))
    
    if not csv_files:
        print(f"No CSV files found in {csv_directory}")
        return
        
    num_files = len(csv_files)
    cols = min(3, num_files)
    rows = (num_files + cols - 1) // cols
    
    fig, axes = plt.subplots(rows, cols, figsize=(15, 4 * rows), squeeze=False)
    axes_flat = axes.flatten()
    
    for i, filepath in enumerate(csv_files):
        ax1 = axes_flat[i]
        index_data, channel_a, channel_b = read_csv_file(filepath)
        
        if index_data is not None:
            num_samples = len(index_data)
            time_ms = np.linspace(0, TOTAL_CAPTURE_TIME_MS, num=num_samples)
            filename = os.path.basename(filepath)
            
            # Plot Channel A (left axis)
            color_a = 'blue'
            ax1.set_xlabel('Time (ms)')
            ax1.set_ylabel('Ch A (mV)', color=color_a)
            ax1.plot(time_ms, channel_a, color=color_a, linewidth=1)
            ax1.tick_params(axis='y', labelcolor=color_a)
            ax1.grid(True, alpha=0.3)
            
            # Plot Channel B (right axis)
            ax2 = ax1.twinx()
            color_b = 'red'
            ax2.set_ylabel('Ch B (mV)', color=color_b)
            ax2.plot(time_ms, channel_b, color=color_b, linewidth=1)
            ax2.tick_params(axis='y', labelcolor=color_b)
            
            ax1.set_title(f'{filename}', fontsize=10)

    # Hide empty subplots
    for i in range(num_files, len(axes_flat)):
        axes_flat[i].set_visible(False)
        
    plt.tight_layout()


def plot_overlapping_signals():
    """Plot all signals overlapping in one plot."""
    csv_files = sorted(glob(os.path.join(csv_directory, "*.csv")))
    
    if not csv_files:
        print(f"No CSV files found in {csv_directory}")
        return
        
    plt.figure(figsize=(14, 8))
    
    for i, filepath in enumerate(csv_files):
        index_data, channel_a, channel_b = read_csv_file(filepath)
        
        if index_data is not None:
            # FIX: Use the calculated time axis
            num_samples = len(index_data)
            time_ms = np.linspace(0, TOTAL_CAPTURE_TIME_MS, num=num_samples)
            alpha = 0.7 if len(csv_files) > 5 else 1.0
            
            plt.plot(time_ms, channel_a, 'b-', alpha=alpha, linewidth=1)
            plt.plot(time_ms, channel_b, 'r-', alpha=alpha, linewidth=1)

    plt.xlabel('Time (ms)')
    plt.ylabel('Voltage (mV)')
    plt.title('PicoScope Signals - All Captures Overlapped')
    plt.legend(['Channel A', 'Channel B'])
    plt.grid(True, alpha=0.3)
    plt.tight_layout()

def plot_latest_file():
    """Plot only the most recent CSV file."""
    csv_files = glob(os.path.join(csv_directory, "*.csv"))
    
    if not csv_files:
        print(f"No CSV files found in {csv_directory}")
        return
        
    latest_file = max(csv_files, key=os.path.getctime)
    
    if plot_single_file(latest_file):
        print(f"Plotted latest file: {os.path.basename(latest_file)}")

def main():
    """Main plotting function with menu"""
    if not os.path.exists(csv_directory):
        print(f"Directory not found: {csv_directory}")
        return
        
    csv_files = sorted(glob(os.path.join(csv_directory, "*.csv")))
    
    if not csv_files:
        print(f"No CSV files found in {csv_directory}")
        return
        
    print(f"Found {len(csv_files)} CSV files in {csv_directory}")
    print("\nPlotting options:")
    print("1. Plot all files in separate subplots")
    print("2. Plot all files overlapping")
    print("3. Plot latest file only")
    print("4. Plot specific file")
    
    try:
        choice = input("\nEnter your choice (1-4): ").strip()
        
        if choice == '1':
            plot_all_files_subplots()
        elif choice == '2':
            plot_overlapping_signals()
        elif choice == '3':
            plot_latest_file()
        elif choice == '4':
            print("\nAvailable files:")
            for i, filepath in enumerate(csv_files, 1):
                print(f"{i}. {os.path.basename(filepath)}")
            
            file_choice = int(input("\nEnter file number: ")) - 1
            if 0 <= file_choice < len(csv_files):
                plot_single_file(csv_files[file_choice])
            else:
                print("Invalid file number")
                return
        else:
            print("Invalid choice")
            return
            
        plt.show()
        
    except (ValueError, KeyboardInterrupt):
        print("\nOperation cancelled.")

if __name__ == "__main__":
    main()