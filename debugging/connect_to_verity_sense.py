import asyncio
from bleak import BleakClient

# mac address from show_ble_devices.py
MAC_ADDRESS = "A0:9E:1A:C5:31:04"
HR_UUID = "00002a37-0000-1000-8000-00805f9b34fb"
BATTERY_UUID = "00002a19-0000-1000-8000-00805f9b34fb"

def hr_data_handler(sender, data):
    # callback function for getting a bpm from bluetooth
    bpm = data[1]
    print(f"bpm: {bpm}")

async def main():
    print(f"connecting to {MAC_ADDRESS}...")
    async with BleakClient(MAC_ADDRESS) as client:
        print("connected to ppg sensor")
        battery_data = await client.read_gatt_char(BATTERY_UUID)
        battery_percentage = battery_data[0]
        print(f"battery: {battery_percentage}%")
        # streams data to callback function
        await client.start_notify(HR_UUID, hr_data_handler)
        print("connected to hr data")
        
        # keeps script running
        await asyncio.sleep(60.0)
        
        await client.stop_notify(HR_UUID)

if __name__ == "__main__":
    asyncio.run(main())