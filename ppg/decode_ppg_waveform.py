import asyncio
from bleak import BleakScanner
from polar_python import PolarDevice
import csv
import time

MAC_ADDRESS = "A0:9E:1A:C5:31:04"

start_time = None
csv_writer = None

def ppg_handler(data):
    global start_time
    
    if start_time is None:
        start_time = time.time()
        
    current_time = time.time() - start_time

    # First 3 objects in array are leds for ppg sensor, 4th is for ambient light
    for sample in data.samples:
        print(f"Led 1: {sample[0]}, Led 2: {sample[1]}, Led 3: {sample[2]}, Ambient light: {sample[3]}")
        
        if csv_writer is not None:
            csv_writer.writerow([current_time, sample[0], sample[1], sample[2], sample[3]])

async def main():
    global csv_writer 
        
    print(f"searching for {MAC_ADDRESS}...")
    device = await BleakScanner.find_device_by_address(MAC_ADDRESS)
    
    if not device:
        print("sensor not found")
        return

    async with PolarDevice(device) as polar:
        print("starting ppg stream\n")
        
        with open("csv_files/ppg_data_log.csv", mode="w", newline="") as csv_file:
            csv_writer = csv.writer(csv_file)
            csv_writer.writerow(["Time", "Led 1", "Led 2", "Led 3", "Ambient Light"])
            
            await polar.start_ppg_stream(ppg_handler, 55, 22, 4)
            
            try:
                await asyncio.sleep(15.0)
            except KeyboardInterrupt:
                pass
            finally:
                print("stoppping stream")
                await polar.stop_ppg_stream()
                print("disconnected")

if __name__ == "__main__":
    asyncio.run(main())