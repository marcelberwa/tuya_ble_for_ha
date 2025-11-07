#!/usr/bin/env python3
"""Test script to validate tinytuya authentication"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'custom_components', 'tuya_ble'))

from tinytuya.tinytuya import Cloud as TuyaCloud

def test_auth():
    print("Testing Tuya Cloud authentication with tinytuya...")
    
    # These would be your actual credentials
    api_key = "your_access_id_here"
    api_secret = "your_access_secret_here"
    region = "us"  # or eu, cn, etc.
    
    try:
        cloud = TuyaCloud(
            apiRegion=region,
            apiKey=api_key,
            apiSecret=api_secret,
        )
        
        if cloud.token:
            print(f"✅ Authentication successful! Token: {cloud.token[:20]}...")
            
            # Test getting devices
            devices = cloud.getdevices(verbose=True)
            if devices.get('success'):
                print(f"✅ Device list retrieved successfully: {len(devices.get('result', []))} devices")
            else:
                print(f"❌ Failed to get devices: {devices}")
                
        else:
            print(f"❌ Authentication failed: {cloud.error}")
            
    except Exception as e:
        print(f"❌ Exception during authentication: {e}")

if __name__ == "__main__":
    print("Note: Replace 'your_access_id_here' and 'your_access_secret_here' with your actual Tuya IoT credentials")
    print("This script demonstrates the authentication approach now used in the integration.")
    print()
    test_auth()