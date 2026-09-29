import asyncio
import csv
import time
from collections import deque
import matplotlib.pyplot as plt
from bleak import BleakClient

# mac address from show_ble_devices.py
MAC_ADDRESS = "A0:9E:1A:C5:31:04"
HR_UUID = "00002a37-0000-1000-8000-00805f9b34fb"
BATTERY_UUID = "00002a19-0000-1000-8000-00805f9b34fb"

# deque for hr and time
timestamps = deque(maxlen=200) 
hr_values = deque(maxlen=200)
start_time = None
csv_writer = None

def hr_data_handler(sender, data):
    global start_time
    
    if start_time is None:
        start_time = time.time()

    bpm = data[1]
    current_time = time.time() - start_time

    # updates data
    timestamps.append(current_time)
    hr_values.append(bpm)

    # saves data to csv
    if csv_writer is not None:
        csv_writer.writerow([current_time, bpm])

    print(f"bpm: {bpm}")

async def main():
    global start_time, csv_writer

    print(f"connecting to {MAC_ADDRESS}...")
    async with BleakClient(MAC_ADDRESS) as client:
        print("connected to ppg sensor")
        
        battery_data = await client.read_gatt_char(BATTERY_UUID)
        battery_percentage = battery_data[0]
        print(f"battery: {battery_percentage}%")

        # opens csv file and sets up the header
        with open("hr_data_log.csv", mode="w", newline="") as csv_file:
            csv_writer = csv.writer(csv_file)
            csv_writer.writerow(["Time(s)", "BPM"])

            # sets up interactive visualizer
            plt.ion() 
            fig, ax = plt.subplots()
            line, = ax.plot([], [], 'r-', linewidth=2)
            
            ax.set_title("Real-Time Heart Rate")
            ax.set_xlabel("Time (Seconds)")
            ax.set_ylabel("Heart Rate (BPM)")
            ax.set_ylim(40, 200) 
            ax.grid(True)

            # starts streaming data to callback function
            await client.start_notify(HR_UUID, hr_data_handler)
            print("connected to hr data. Visualizing and recording...")
            
            # starts loop timer
            start_time = time.time()
            
            try:
                while time.time() - start_time < 60.0:
                    if timestamps and hr_values:
                        # updates line data
                        line.set_data(timestamps, hr_values)
                        
                        # sliding x axis effect to show last 30 second
                        ax.set_xlim(max(0, timestamps[-1] - 30), max(30, timestamps[-1] + 5))
                        
                        fig.canvas.draw()
                        fig.canvas.flush_events()
                    
                    # allows bleak's async ble operations to run
                    await asyncio.sleep(0.1)
                    
            except KeyboardInterrupt:
                print("\nStopping early...")
                
            finally:
                await client.stop_notify(HR_UUID)
                print("Disconnected. Data saved to hr_data_log.csv")
                
                plt.ioff()
                plt.show()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass