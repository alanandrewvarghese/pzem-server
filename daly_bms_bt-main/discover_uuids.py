import asyncio
import sys
from bleak import BleakScanner, BleakClient

DEFAULT_MAC = "C6:6C:09:03:0A:13"

async def scan():
    print("Scanning for devices...")
    devices = await BleakScanner.discover()
    for d in devices:
        print(f"Found: {d.address} - {d.name}")

async def discover_services(mac):
    print(f"Connecting to {mac}...")
    try:
        async with BleakClient(mac) as client:
            print(f"Connected: {client.is_connected}")
            print("Services:")
            for service in client.services:
                print(f"[Service] {service.uuid} ({service.description})")
                for char in service.characteristics:
                    print(f"  [Characteristic] {char.uuid} (Handle: {char.handle})")
                    print(f"    - Properties: {', '.join(char.properties)}")
                    print(f"    - Description: {char.description}")
    except Exception as e:
        print(f"Error connecting to {mac}: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        mac = sys.argv[1]
        if mac.lower() == "scan":
            asyncio.run(scan())
        else:
            asyncio.run(discover_services(mac))
    else:
        print(f"No MAC provided, trying default: {DEFAULT_MAC}")
        asyncio.run(discover_services(DEFAULT_MAC))
