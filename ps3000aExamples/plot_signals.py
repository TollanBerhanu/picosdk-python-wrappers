#
# Signal Plotting Script for PS3000A Captured Data
# This script reads CSV files from the captured_data directory and plots both channels

import os
import csv
import matplotlib.pyplot as plt
import numpy as np
from glob import glob

# Configuration
csv_directory = r"c:\Users\tberhanu\Desktop\workspace\picosdk-python-wrappers\captures_o4_2"
plot_all_files = True  # Set to False to plot only the latest file

def read_csv_file(filepath):
    """Read CSV file and return time, channel A, and channel B data"""
    time_data = []
    channel_a_data = []
    channel_b_data = []
    
    try:
        with open(filepath, 'r') as file:
            reader = csv.reader(file)
            header = next(reader)  # Skip header row
            
            for row in reader:
                if len(row) >= 3:
                    time_data.append(float(row[0]))
                    channel_a_data.append(float(row[1]))
                    channel_b_data.append(float(row[2]))
    
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return None, None, None
    
    return np.array(time_data), np.array(channel_a_data), np.array(channel_b_data)

def plot_single_file(filepath):
    """Plot data from a single CSV file"""
    time_data, channel_a, channel_b = read_csv_file(filepath)
    
    if time_data is None:
        return False
    
    filename = os.path.basename(filepath)
    
    plt.figure(figsize=(12, 8))
    plt.plot(time_data / 1e6, channel_a, 'b-', label='Channel A', linewidth=1)  # Convert ns to ms
    plt.plot(time_data / 1e6, channel_b, 'r-', label='Channel B', linewidth=1)
    
    plt.xlabel('Time (ms)')
    plt.ylabel('Voltage (mV)')
    plt.title(f'PicoScope Signals - {filename}')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    
    return True

def plot_all_files():
    """Plot data from all CSV files in separate subplots"""
    csv_files = glob(os.path.join(csv_directory, "*.csv"))
    
    if not csv_files:
        print(f"No CSV files found in {csv_directory}")
        return
    
    csv_files.sort()  # Sort files by name
    
    # Calculate subplot arrangement
    num_files = len(csv_files)
    cols = min(3, num_files)  # Max 3 columns
    rows = (num_files + cols - 1) // cols
    
    fig, axes = plt.subplots(rows, cols, figsize=(15, 4*rows))
    if num_files == 1:
        axes = [axes]
    elif rows == 1:
        axes = axes.reshape(1, -1)
    
    for i, filepath in enumerate(csv_files):
        row = i // cols
        col = i % cols
        ax = axes[row, col] if rows > 1 else axes[col]
        
        time_data, channel_a, channel_b = read_csv_file(filepath)
        
        if time_data is not None:
            filename = os.path.basename(filepath)
            
            ax.plot(time_data / 1e6, channel_a, 'b-', label='Channel A', linewidth=1)
            ax.plot(time_data / 1e6, channel_b, 'r-', label='Channel B', linewidth=1)
            
            ax.set_xlabel('Time (ms)')
            ax.set_ylabel('Voltage (mV)')
            ax.set_title(f'{filename}', fontsize=10)
            ax.legend()
            ax.grid(True, alpha=0.3)
    
    # Hide empty subplots
    for i in range(num_files, rows * cols):
        row = i // cols
        col = i % cols
        if rows > 1:
            axes[row, col].set_visible(False)
        elif cols > 1:
            axes[col].set_visible(False)
    
    plt.tight_layout()

def plot_overlapping_signals():
    """Plot all signals overlapping in one plot"""
    csv_files = glob(os.path.join(csv_directory, "*.csv"))
    
    if not csv_files:
        print(f"No CSV files found in {csv_directory}")
        return
    
    csv_files.sort()
    
    plt.figure(figsize=(14, 8))
    
    for i, filepath in enumerate(csv_files):
        time_data, channel_a, channel_b = read_csv_file(filepath)
        
        if time_data is not None:
            filename = os.path.basename(filepath).replace('.csv', '')
            alpha = 0.7 if len(csv_files) > 5 else 1.0
            
            plt.plot(time_data / 1e6, channel_a, 'b-', alpha=alpha, linewidth=1, 
                    label=f'Ch A - {filename}' if i == 0 else "")
            plt.plot(time_data / 1e6, channel_b, 'r-', alpha=alpha, linewidth=1,
                    label=f'Ch B - {filename}' if i == 0 else "")
    
    plt.xlabel('Time (ms)')
    plt.ylabel('Voltage (mV)')
    plt.title('PicoScope Signals - All Captures Overlapped')
    plt.legend(['Channel A', 'Channel B'])
    plt.grid(True, alpha=0.3)
    plt.tight_layout()

def plot_latest_file():
    """Plot only the most recent CSV file"""
    csv_files = glob(os.path.join(csv_directory, "*.csv"))
    
    if not csv_files:
        print(f"No CSV files found in {csv_directory}")
        return
    
    # Get the most recent file
    latest_file = max(csv_files, key=os.path.getctime)
    
    if plot_single_file(latest_file):
        print(f"Plotted latest file: {os.path.basename(latest_file)}")

def main():
    """Main plotting function with menu"""
    if not os.path.exists(csv_directory):
        print(f"Directory not found: {csv_directory}")
        return
    
    csv_files = glob(os.path.join(csv_directory, "*.csv"))
    
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
            plot_all_files()
            print("Plotting all files in subplots...")
            
        elif choice == '2':
            plot_overlapping_signals()
            print("Plotting all files overlapped...")
            
        elif choice == '3':
            plot_latest_file()
            
        elif choice == '4':
            print("\nAvailable files:")
            for i, filepath in enumerate(sorted(csv_files), 1):
                print(f"{i}. {os.path.basename(filepath)}")
            
            file_choice = int(input("\nEnter file number: ")) - 1
            if 0 <= file_choice < len(csv_files):
                if plot_single_file(sorted(csv_files)[file_choice]):
                    print(f"Plotted: {os.path.basename(sorted(csv_files)[file_choice])}")
            else:
                print("Invalid file number")
                return
        
        else:
            print("Invalid choice")
            return
        
        plt.show()
        
    except (ValueError, KeyboardInterrupt):
        print("Operation cancelled")

if __name__ == "__main__":
    main()
