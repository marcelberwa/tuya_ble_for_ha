"""The Tuya BLE integration."""
from __future__ import annotations

from typing_extensions import Final

DOMAIN: Final = "tuya_ble"
TUYA_DOMAIN: Final = "tuya"

# Configuration constants
CONF_ACCESS_ID: Final = "access_id"
CONF_ACCESS_SECRET: Final = "access_secret"
CONF_APP_TYPE: Final = "app_type"
CONF_AUTH_TYPE: Final = "auth_type"
CONF_COUNTRY_CODE: Final = "country_code"
CONF_ENDPOINT: Final = "endpoint"
CONF_REGION: Final = "region"
CONF_TUYA_DEVICE_ID: Final = "tuya_device_id"

CONF_UUID: Final = "uuid"
CONF_LOCAL_KEY: Final = "local_key"
CONF_CATEGORY: Final = "category"
CONF_PRODUCT_ID: Final = "product_id"
CONF_DEVICE_NAME: Final = "device_name"
CONF_PRODUCT_MODEL: Final = "product_model"
CONF_PRODUCT_NAME: Final = "product_name"

# App type constants
SMARTLIFE_APP: Final = "smart_life"
TUYA_SMART_APP: Final = "tuya_smart"

# Region constants for Tuya Cloud
class TuyaRegion:
    def __init__(self, code: str, name: str, description: str):
        self.code = code
        self.name = name
        self.description = description

TUYA_REGIONS: Final = [
    TuyaRegion("cn", "China", "China Data Center"),
    TuyaRegion("us", "United States", "US - Western America Data Center"),
    TuyaRegion("us-e", "US East", "US - Eastern America Data Center"), 
    TuyaRegion("eu", "Europe", "Central Europe Data Center"),
    TuyaRegion("eu-w", "Europe West", "Western Europe Data Center"),
    TuyaRegion("in", "India", "India Data Center"),
    TuyaRegion("sg", "Singapore", "Singapore Data Center"),
]

# API response constants
TUYA_RESPONSE_CODE: Final = "code"
TUYA_RESPONSE_MSG: Final = "msg"
TUYA_RESPONSE_RESULT: Final = "result"
TUYA_RESPONSE_SUCCESS: Final = "success"

DEVICE_METADATA_UUIDS: Final = "uuids"

DEVICE_DEF_MANUFACTURER: Final = "Tuya"
SET_DISCONNECTED_DELAY = 10 * 60

TUYA_API_DEVICES_URL: Final = "/v1.0/users/%s/devices"
TUYA_API_FACTORY_INFO_URL: Final = "/v1.0/iot-03/devices/factory-infos?device_ids=%s"
TUYA_FACTORY_INFO_MAC: Final = "mac"

BATTERY_STATE_LOW: Final = "low"
BATTERY_STATE_NORMAL: Final = "normal"
BATTERY_STATE_HIGH: Final = "high"

BATTERY_NOT_CHARGING: Final = "not_charging"
BATTERY_CHARGING: Final = "charging"
BATTERY_CHARGED: Final = "charged"

CO2_LEVEL_NORMAL: Final = "normal"
CO2_LEVEL_ALARM: Final = "alarm"

FINGERBOT_MODE_PUSH: Final = "push"
FINGERBOT_MODE_SWITCH: Final = "switch"
FINGERBOT_MODE_PROGRAM: Final = "program"
FINGERBOT_BUTTON_EVENT: Final = "fingerbot_button_pressed"

