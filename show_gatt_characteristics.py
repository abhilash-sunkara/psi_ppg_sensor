import asyncio
from bleak import BleakClient
MAC_ADDRESS = "A0:9E:1A:C5:31:04"

async def main():
    print(f"Connecting to {MAC_ADDRESS}...")
    
    async with BleakClient(MAC_ADDRESS) as client:
        print("Connected! Reading GATT table...\n")
        
        for service in client.services:
            print(f"[Service] {service.uuid}: {service.description}")
            
            for char in service.characteristics:
                properties = ", ".join(char.properties)
                print(f"  ├── [Characteristic] {char.uuid}")
                print(f"  │     Properties:  {properties}")
                print(f"  │     Description: {char.description}")
            print("-" * 60)

if __name__ == "__main__":
    asyncio.run(main())