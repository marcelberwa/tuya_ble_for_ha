"""The Tuya BLE integration."""
from __future__ import annotations

import logging

from dataclasses import dataclass
import json
from typing import Any, Iterable

from homeassistant.const import CONF_ADDRESS, CONF_DEVICE_ID
from homeassistant.core import HomeAssistant
from .const import (
    CONF_ACCESS_ID,
    CONF_ACCESS_SECRET,
    CONF_APP_TYPE,
    CONF_REGION,
    CONF_TUYA_DEVICE_ID,
    TUYA_DOMAIN,
    TUYA_RESPONSE_RESULT,
    TUYA_RESPONSE_SUCCESS,
)
from homeassistant.helpers.entity import DeviceInfo, EntityDescription
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .tuya_cloud_api import TuyaCloudAPI

from .tuya_ble import (
    AbstaractTuyaBLEDeviceManager,
    TuyaBLEDevice,
    TuyaBLEDeviceCredentials,
)

from .const import (
    CONF_PRODUCT_MODEL,
    CONF_UUID,
    CONF_LOCAL_KEY,
    CONF_CATEGORY,
    CONF_PRODUCT_ID,
    CONF_DEVICE_NAME,
    CONF_PRODUCT_NAME,
    DOMAIN,
    TUYA_API_DEVICES_URL,
    TUYA_API_FACTORY_INFO_URL,
    TUYA_FACTORY_INFO_MAC,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class TuyaCloudCacheItem:
    api: TuyaCloudAPI | None
    login: dict[str, Any]
    credentials: dict[str, dict[str, Any]]


CONF_TUYA_LOGIN_KEYS = [
    CONF_ACCESS_ID,
    CONF_ACCESS_SECRET,
    CONF_TUYA_DEVICE_ID,
    CONF_REGION,
]

CONF_TUYA_DEVICE_KEYS = [
    CONF_UUID,
    CONF_LOCAL_KEY,
    CONF_DEVICE_ID,
    CONF_CATEGORY,
    CONF_PRODUCT_ID,
    CONF_DEVICE_NAME,
    CONF_PRODUCT_NAME,
    CONF_PRODUCT_MODEL,
]

_cache: dict[str, TuyaCloudCacheItem] = {}


async def cleanup_cache() -> None:
    """Clean up cache and close all API sessions."""
    global _cache
    for cache_item in _cache.values():
        if cache_item.api:
            await cache_item.api.close()
    _cache.clear()
    _LOGGER.debug("Cache cleaned up and all API sessions closed")


class HASSTuyaBLEDeviceManager(AbstaractTuyaBLEDeviceManager):
    """Cloud connected manager of the Tuya BLE devices credentials."""

    def __init__(self, hass: HomeAssistant, data: dict[str, Any]) -> None:
        assert hass is not None
        self._hass = hass
        self._data = data

    @staticmethod
    def _is_login_success(response: dict[Any, Any]) -> bool:
        return bool(response.get(TUYA_RESPONSE_SUCCESS, False))

    @staticmethod
    def _get_cache_key(data: dict[str, Any]) -> str:
        key_dict = {key: data.get(key) for key in CONF_TUYA_LOGIN_KEYS}
        return json.dumps(key_dict)

    @staticmethod
    def _has_login(data: dict[Any, Any]) -> bool:
        for key in CONF_TUYA_LOGIN_KEYS:
            if data.get(key) is None:
                return False
        return True

    @staticmethod
    def _has_credentials(data: dict[Any, Any]) -> bool:
        for key in CONF_TUYA_DEVICE_KEYS:
            if data.get(key) is None:
                return False
        return True

    async def _login(self, data: dict[str, Any], add_to_cache: bool) -> dict[Any, Any]:
        """Login into Tuya cloud using credentials from data dictionary."""
        global _cache

        if len(data) == 0:
            return {}

        try:
            # Check if we already have a valid cached API for these credentials
            if add_to_cache:
                cache_key = self._get_cache_key(data)
                cache_item = _cache.get(cache_key)
                if cache_item and cache_item.api:
                    # Try to reuse existing API if it's still valid
                    try:
                        token = await cache_item.api.get_token()
                        if token:
                            _LOGGER.debug("Reusing existing API session for %s", data[CONF_ACCESS_ID][:8] + "...")
                            return {TUYA_RESPONSE_SUCCESS: True, "result": {"access_token": token}}
                    except Exception as e:
                        _LOGGER.debug("Existing API session invalid, creating new one: %s", e)
                        # Close the invalid session
                        await cache_item.api.close()
                        cache_item.api = None
            
            # Create TuyaCloudAPI instance - this is async now
            region = data.get(CONF_REGION, "eu")
            api = TuyaCloudAPI(
                api_region=region,
                api_key=data.get(CONF_ACCESS_ID, ""),
                api_secret=data.get(CONF_ACCESS_SECRET, ""),
                api_device_id=data.get(CONF_TUYA_DEVICE_ID, ""),
            )
            
            # Get token to verify authentication
            token = await api.get_token()
            
            _LOGGER.debug("TuyaCloudAPI created - token: %s, error: %s", 
                         bool(token), api.error)
            
            # Check if authentication was successful by checking if we have a token
            if token:
                response = {TUYA_RESPONSE_SUCCESS: True, "result": {"access_token": token}}
                _LOGGER.debug("Successful login for API Key %s", data[CONF_ACCESS_ID][:8] + "...")
                
                if add_to_cache:
                    cache_key = self._get_cache_key(data)
                    cache_item = _cache.get(cache_key)
                    if cache_item:
                        # Update the API reference (might be the same or new)
                        cache_item.api = api
                        cache_item.login = data
                    else:
                        _cache[cache_key] = TuyaCloudCacheItem(api, data, {})
                else:
                    # If not caching, close the session immediately after successful login
                    # The caller should use add_to_cache=True if they need to keep the session
                    await api.close()
                    _LOGGER.debug("Login successful but not cached, session closed")
            else:
                # Login failed - close the API session
                await api.close()
                error_msg = "Authentication failed"
                error_code = None
                if api.error:
                    if isinstance(api.error, dict):
                        error_msg = api.error.get('msg', str(api.error))
                        error_code = api.error.get('code', None)
                    else:
                        error_msg = str(api.error)
                _LOGGER.error("TuyaCloudAPI authentication failed: %s", error_msg)
                response = {
                    TUYA_RESPONSE_SUCCESS: False, 
                    "msg": error_msg,
                    "code": error_code
                }
                
        except Exception as e:
            _LOGGER.error("Login failed with exception: %s", str(e))
            # Close API session on exception
            if 'api' in locals():
                await api.close()
            response = {
                TUYA_RESPONSE_SUCCESS: False, 
                "msg": str(e),
                "code": None
            }

        return response

    def _check_login(self) -> bool:
        cache_key = self._get_cache_key(self._data)
        return _cache.get(cache_key) != None

    async def login(self, add_to_cache: bool = False) -> dict[Any, Any]:
        return await self._login(self._data, add_to_cache)

    async def _fill_cache_item(self, item: TuyaCloudCacheItem) -> None:
        try:
            # Use our async API to get devices
            devices_response = await item.api.get_devices()
            
            _LOGGER.debug("Devices response type: %s, content: %s", type(devices_response), devices_response)
            
            if isinstance(devices_response, dict) and devices_response.get(TUYA_RESPONSE_SUCCESS):
                result = devices_response.get(TUYA_RESPONSE_RESULT, {})
                
                # Handle nested devices structure: result can be either a list or dict with 'devices' key
                if isinstance(result, dict):
                    devices = result.get("devices", [])
                elif isinstance(result, list):
                    devices = result
                else:
                    devices = []
                
                _LOGGER.debug("Found %d devices to process", len(devices) if isinstance(devices, list) else 0)
                
                if isinstance(devices, list):
                    for device in devices:
                        if not isinstance(device, dict):
                            continue
                        device_id = device.get("id")
                        device_uuid = device.get("uuid")
                        
                        if not device_id or not device_uuid:
                            continue
                        
                        mac = None
                        
                        # Try to get MAC from factory info
                        try:
                            fi_response = await item.api.cloud_request(
                                TUYA_API_FACTORY_INFO_URL % device_id,
                                method="GET"
                            )
                            
                            _LOGGER.debug("Factory info response for device %s: %s", device_id, fi_response)
                            
                            if fi_response and isinstance(fi_response, dict) and fi_response.get(TUYA_RESPONSE_SUCCESS):
                                fi_response_result = fi_response.get(TUYA_RESPONSE_RESULT)
                                if (fi_response_result and 
                                    isinstance(fi_response_result, list) and 
                                    len(fi_response_result) > 0):
                                    factory_info = fi_response_result[0]
                                    if (factory_info and 
                                        isinstance(factory_info, dict) and 
                                        TUYA_FACTORY_INFO_MAC in factory_info):
                                        mac = ":".join(
                                            factory_info[TUYA_FACTORY_INFO_MAC][i : i + 2]
                                            for i in range(0, 12, 2)
                                        ).upper()
                        except Exception as e:
                            _LOGGER.debug("Failed to get factory info for device %s: %s", device_id, e)
                        
                        # Store credentials - use UUID as fallback key if MAC is not available
                        device_credentials = {
                            CONF_UUID: device_uuid,
                            CONF_LOCAL_KEY: device.get("local_key"),
                            CONF_DEVICE_ID: device_id,
                            CONF_CATEGORY: device.get("category"),
                            CONF_PRODUCT_ID: device.get("product_id"),
                            CONF_DEVICE_NAME: device.get("name"),
                            CONF_PRODUCT_MODEL: device.get("model"),
                            CONF_PRODUCT_NAME: device.get("product_name"),
                        }
                        
                        if mac:
                            # Store by MAC address if available
                            device_credentials[CONF_ADDRESS] = mac
                            item.credentials[mac] = device_credentials
                            _LOGGER.debug("Stored credentials for device %s with MAC %s", device.get("name"), mac)
                        
                        # Always store by UUID as well for lookup
                        item.credentials[device_uuid] = device_credentials
                        _LOGGER.debug("Stored credentials for device %s with UUID %s", device.get("name"), device_uuid)
            else:
                _LOGGER.warning("Invalid devices_response type or failed response: %s", devices_response)
        except Exception as e:
            _LOGGER.exception("Failed to fill cache item: %s", str(e))

    async def build_cache(self) -> None:
        global _cache
        data = {}
        tuya_config_entries = self._hass.config_entries.async_entries(TUYA_DOMAIN)
        for config_entry in tuya_config_entries:
            data.clear()
            data.update(config_entry.data)
            key = self._get_cache_key(data)
            item = _cache.get(key)
            if item is None or len(item.credentials) == 0:
                if self._is_login_success(await self._login(data, True)):
                    item = _cache.get(key)
                    if item and len(item.credentials) == 0:
                        await self._fill_cache_item(item)

        ble_config_entries = self._hass.config_entries.async_entries(DOMAIN)
        for config_entry in ble_config_entries:
            data.clear()
            data.update(config_entry.options)
            key = self._get_cache_key(data)
            item = _cache.get(key)
            if item is None or len(item.credentials) == 0:
                if self._is_login_success(await self._login(data, True)):
                    item = _cache.get(key)
                    if item and len(item.credentials) == 0:
                        await self._fill_cache_item(item)

    def get_login_from_cache(self) -> None:
        global _cache
        for cache_item in _cache.values():
            self._data.update(cache_item.login)
            break

    async def get_device_credentials(
        self,
        address: str,
        force_update: bool = False,
        save_data: bool = False,
    ) -> TuyaBLEDeviceCredentials | None:
        """Get credentials of the Tuya BLE device."""
        global _cache
        item: TuyaCloudCacheItem | None = None
        credentials: dict[str, any] | None = None
        result: TuyaBLEDeviceCredentials | None = None

        if not force_update and self._has_credentials(self._data):
            credentials = self._data.copy()
        else:
            cache_key: str | None = None
            if self._has_login(self._data):
                cache_key = self._get_cache_key(self._data)
            else:
                for key in _cache.keys():
                    if _cache[key].credentials.get(address) is not None:
                        cache_key = key
                        break
            if cache_key:
                item = _cache.get(cache_key)
            if item is None or force_update:
                if self._is_login_success(await self.login(True)):
                    item = _cache.get(cache_key)
                    if item:
                        await self._fill_cache_item(item)

            if item:
                _LOGGER.debug("Looking up credentials for MAC address: %s (normalized: %s)", address, address.upper())
                credentials = item.credentials.get(address)
                
                # If not found by MAC address, try to find by matching stored address in credentials
                # Also try to match if this MAC was previously associated with a device
                if not credentials:
                    _LOGGER.debug("Credentials not found by direct MAC lookup '%s', searching in %d cached devices", 
                                 address, len(item.credentials))
                    _LOGGER.debug("Available credential keys: %s", list(item.credentials.keys()))
                    
                    # Try to find credentials where the stored address matches
                    for key, cred in item.credentials.items():
                        if isinstance(cred, dict):
                            stored_address = cred.get(CONF_ADDRESS)
                            stored_name = cred.get(CONF_DEVICE_NAME, "unknown")
                            if stored_address:
                                _LOGGER.debug("Comparing MAC %s with stored address %s for device %s", 
                                            address, stored_address, stored_name)
                                if stored_address.upper() == address.upper():
                                    credentials = cred
                                    _LOGGER.info("Found credentials for MAC %s (device: %s)", address, stored_name)
                                    break
                    
                    # If still not found and we have existing data with UUID, try to match by UUID
                    if not credentials and CONF_UUID in self._data:
                        device_uuid = self._data.get(CONF_UUID)
                        credentials = item.credentials.get(device_uuid)
                        if credentials:
                            _LOGGER.info("Found credentials by UUID %s for MAC %s", device_uuid, address)
                            # Update the credentials cache to also use this MAC
                            credentials[CONF_ADDRESS] = address
                            item.credentials[address] = credentials
                    
                    if not credentials:
                        _LOGGER.warning("Device with MAC %s not found in Tuya cloud cache. Available devices: %s", 
                                      address, 
                                      {k: v.get(CONF_DEVICE_NAME, 'unknown') for k, v in item.credentials.items() if isinstance(v, dict)})

        if credentials:
            result = TuyaBLEDeviceCredentials(
                credentials.get(CONF_UUID, ""),
                credentials.get(CONF_LOCAL_KEY, ""),
                credentials.get(CONF_DEVICE_ID, ""),
                credentials.get(CONF_CATEGORY, ""),
                credentials.get(CONF_PRODUCT_ID, ""),
                credentials.get(CONF_DEVICE_NAME, ""),
                credentials.get(CONF_PRODUCT_MODEL, ""),
                credentials.get(CONF_PRODUCT_NAME, ""),
            )
            _LOGGER.debug("Retrieved: %s", result)
            if save_data:
                if item:
                    self._data.update(item.login)
                self._data.update(credentials)

        return result

    @property
    def data(self) -> dict[str, Any]:
        return self._data
