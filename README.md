# Home Assistant Tuya BLE Integration

## Overview

This integration provides local control support for Tuya devices connected via Bluetooth Low Energy (BLE) in Home Assistant. It enables direct communication with Tuya BLE devices using their Tuya IoT cloud credentials.

**Features:**
- Local control of Tuya BLE devices without cloud dependencies (after initial setup)
- Automatic device discovery via Bluetooth
- Support for multiple device categories (climate, sensors, smart locks, fingerbots, and more)
- Simplified setup requiring only Tuya IoT Access ID, Access Secret, and Region
- Automatic device matching based on MAC address

_Based on code from [@PlusPlus-ua](https://github.com/PlusPlus-ua/ha_tuya_ble) and [@redphx](https://github.com/redphx/poc-tuya-ble-fingerbot)_

## Installation

Place the `custom_components` folder in your configuration directory (or add its contents to an existing `custom_components` folder).

Alternatively, add this integration to HACS (Home Assistant Community Store).

## Setup & Configuration

### Prerequisites

The integration works locally, but connection to Tuya BLE device requires the encryption key from the Tuya IOT cloud. It could be obtained using the same credentials as in official Tuya integration. To obtain the credentials, please refer to official Tuya integration [documentation](https://www.home-assistant.io/integrations/tuya/). In short, these are the steps to take:

1. Go to [Tuya IoT Console](https://iot.tuya.com)
2. Create a new **Cloud Project** or use an existing one
3. Add the Tuya BLE devices (best via the official Tuya App -> tab **Link App Account**)
3. Give the devices the permissions for "Device Control"
4. Get your **Access ID** and **Access Secret** (in the tab **Overview** of the **Cloud Project**)
5. Note your **API Region** (CN, EU, US, IN, etc.)

### Adding Devices

1. Ensure your Tuya BLE device is powered on and in range
2. In Home Assistant, go to **Settings → Devices & Services → Integrations**
3. Click **Create Integration** and search for "Tuya BLE"
4. Home Assistant will automatically discover nearby Tuya BLE devices
5. When a device is found, enter your **Tuya IoT Access ID**, **Access Secret**, and **Region**
6. The device will be automatically matched and added to your setup

**Note:** You do NOT need to enter the Device ID manually. The integration automatically matches devices based on their MAC address from the Bluetooth discovery.

## Supported Devices

### Fingerbots (category_id 'szjqr')
  - **Fingerbot** (product_ids 'ltak7e1p', 'y6kttvd6', 'yrnk7mnn', 'nvr2rocq', 'bnt7wajf', 'rvdceqjh', '5xhbk964')
    - Original device, first in category, powered by CR2 battery
    - Full programming support with series of actions
  
  - **Adaprox Fingerbot** (product_id 'y6kttvd6')
    - Built-in battery with USB type C charging
  
  - **Fingerbot Plus** (product_ids 'blliqpsj', 'ndvkgsrm', 'yiihr7zh', 'neq16kgd')
    - Similar to original with sensor button for manual control
    - Advanced programming capabilities (position, repeat count, idle position)
  
  - **CubeTouch 1s** (product_id '3yqdo5yt')
    - Built-in battery with USB type C charging
  
  - **CubeTouch II** (product_id 'xhf790if')
    - Built-in battery with USB type C charging

  **Programming Format:** `position[/time];...` where position is in percents (0-100), optional time is in seconds.

### Temperature & Humidity Sensors (category_id 'wsdcg')
  - **Soil Moisture Sensor** (product_id 'ojzlzzsw')

### CO2 Sensors (category_id 'co2bj')
  - **CO2 Detector** (product_id '59s19z5m')

### Smart Locks (category_id 'ms')
  - **Smart Lock** (product_ids 'ludzroix', 'isk2p555')

### Climate Control (category_id 'wk')
  - **Thermostatic Radiator Valve** (product_ids 'drlajpqc', 'nhj2j7su', 'hkdvdvef')
    - Full temperature control support
    - Heating mode, target temperature, and valve position control
    - Energy-saving features

### Smart Water Bottles (category_id 'znhsb')
  - **Smart Water Bottle** (product_id 'cdlandip')

### Irrigation Systems (category_id 'ggq')
  - **Irrigation Computer** (product_id '6pahkcau')

## Troubleshooting

### Device Not Discovered
- Ensure your Tuya BLE device is powered on and nearby
- Check that Bluetooth is enabled in Home Assistant
- Verify the device is in pairing/discovery mode if needed
- Try restarting Home Assistant Bluetooth

### Authentication Errors
- Double-check your Tuya IoT Access ID and Access Secret
- Verify you're using the correct API Region
- Ensure your Tuya IoT API credentials have "Device Control" permissions

### No Credentials After Login
- Verify the device is registered in your Tuya IoT cloud account
- Check that the device MAC address matches what's discovered
- Try re-adding the integration

## Contributing

Contributions are welcome! Please feel free to submit issues and pull requests to help improve this integration.

<p align="center">
  <a href="buymeacoffee.com/marcelberwa"><img src="https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png" alt="Buy me an Xilinx FPGA"></a>
</p>