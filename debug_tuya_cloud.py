#!/usr/bin/env python3
"""Debug script for Tuya Cloud API connection."""
import asyncio
import sys
import json

# Add the custom_components path to import the Tuya Cloud API
sys.path.insert(0, 'custom_components/tuya_ble')

from tuya_cloud_api import TuyaCloudAPI


async def debug_tuya_cloud(mac_address: str, access_id: str, access_secret: str, 
                           device_id: str, region: str = "eu"):
    """Debug Tuya Cloud API connection and retrieve device info."""
    
    print(f"\n=== Tuya Cloud Debug ===")
    print(f"MAC Address: {mac_address}")
    print(f"Region: {region}")
    print(f"Access ID: {access_id[:8]}...")
    print(f"Device ID: {device_id[:8]}..." if device_id else "None")
    print("=" * 50)
    
    # Initialize API
    api = TuyaCloudAPI(
        api_region=region,
        api_key=access_id,
        api_secret=access_secret,
        api_device_id=device_id,
    )
    
    # Step 1: Get token
    print("\n[1] Getting authentication token...")
    token = await api.get_token()
    if token:
        print(f"✓ Token received: {token[:20]}...")
    else:
        print(f"✗ Authentication failed: {api.error}")
        return
    
    # Step 2: Get devices
    print("\n[2] Fetching devices list...")
    devices_response = await api.get_devices()
    print(f"Devices response: {json.dumps(devices_response, indent=2)}")
    
    if not devices_response.get("success"):
        print("✗ Failed to get devices")
        return
    
    devices = devices_response.get("result", [])
    print(f"✓ Found {len(devices)} device(s)")
    
    # Step 3: Find device by MAC and get factory info
    mac_clean = mac_address.replace(":", "").upper()
    
    for device in devices:
        device_id = device.get("id")
        print(f"\n[3] Checking device: {device.get('name')} (ID: {device_id})")
        print(f"    Device info: {json.dumps(device, indent=4)}")
        
        # Get factory info
        factory_info_url = f"v1.0/devices/{device_id}/factory-infos"
        fi_response = await api.cloud_request(factory_info_url, method="GET")
        
        print(f"\n[4] Factory info response for {device_id}:")
        print(f"    Type: {type(fi_response)}")
        print(f"    Content: {json.dumps(fi_response, indent=4) if isinstance(fi_response, dict) else fi_response}")
        
        if isinstance(fi_response, dict) and fi_response.get("success"):
            fi_result = fi_response.get("result")
            if isinstance(fi_result, list) and len(fi_result) > 0:
                factory_info = fi_result[0]
                if isinstance(factory_info, dict):
                    device_mac = factory_info.get("mac", "")
                    formatted_mac = ":".join(device_mac[i:i+2] for i in range(0, 12, 2)).upper()
                    
                    print(f"    Device MAC: {formatted_mac}")
                    
                    if device_mac.upper() == mac_clean:
                        print(f"\n✓ MATCH FOUND!")
                        print(f"    UUID: {device.get('uuid')}")
                        print(f"    Local Key: {device.get('local_key')}")
                        print(f"    Category: {device.get('category')}")
                        print(f"    Product ID: {device.get('product_id')}")
                        print(f"    Model: {device.get('model')}")
                        return
    
    print(f"\n✗ No device found with MAC address {mac_address}")


if __name__ == "__main__":
    # if len(sys.argv) < 5:
    #     print("Usage: python debug_tuya_cloud.py <MAC> <ACCESS_ID> <ACCESS_SECRET> <DEVICE_ID> [REGION]")
    #     print("Example: python debug_tuya_cloud.py AA:BB:CC:DD:EE:FF your_access_id your_secret your_device_id eu")
    #     sys.exit(1)
    
    mac = "DC:23:4F:C1:27:F6"#sys.argv[1]
    access_id = "nkkuqrgvxpr8f3p7jevr"#sys.argv[2]
    access_secret = "061fe21668f34b3d939d7ba49b884a6d"#sys.argv[3]
    device_id = "bfff1ekayvsdhnwh"#sys.argv[4]
    region = "eu"#sys.argv[5] if len(sys.argv) > 5 else "eu"
    
    asyncio.run(debug_tuya_cloud(mac, access_id, access_secret, device_id, region))
