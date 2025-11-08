"""Config flow for Tuya BLE integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    OptionsFlowWithConfigEntry,
)
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowHandler, FlowResult

from .const import (
    CONF_ACCESS_ID,
    CONF_ACCESS_SECRET,
    CONF_APP_TYPE,
    CONF_DEVICE_NAME,
    CONF_ENDPOINT,
    CONF_REGION,
    CONF_TUYA_DEVICE_ID,
    SMARTLIFE_APP,
    TUYA_REGIONS,
    TUYA_RESPONSE_CODE,
    TUYA_RESPONSE_MSG,
    TUYA_RESPONSE_SUCCESS,
    TUYA_SMART_APP,
)

from .tuya_ble import SERVICE_UUID, TuyaBLEDeviceCredentials

from .const import (
    DOMAIN,
)
from .devices import TuyaBLEData, get_device_readable_name
from .cloud import HASSTuyaBLEDeviceManager, _cache

_LOGGER = logging.getLogger(__name__)


async def _try_login(
    manager: HASSTuyaBLEDeviceManager,
    user_input: dict[str, Any],
    errors: dict[str, str],
    placeholders: dict[str, Any],
) -> dict[str, Any] | None:
    response: dict[Any, Any] | None
    data: dict[str, Any]

    data = {
        CONF_ACCESS_ID: user_input[CONF_ACCESS_ID],
        CONF_ACCESS_SECRET: user_input[CONF_ACCESS_SECRET],
        CONF_TUYA_DEVICE_ID: user_input[CONF_TUYA_DEVICE_ID],
        CONF_REGION: user_input[CONF_REGION],
    }

    response = await manager._login(data, True)

    if response.get(TUYA_RESPONSE_SUCCESS, False):
        return data

    errors["base"] = "login_error"
    if response:
        placeholders.update(
            {
                TUYA_RESPONSE_CODE: response.get(TUYA_RESPONSE_CODE),
                TUYA_RESPONSE_MSG: response.get(TUYA_RESPONSE_MSG),
            }
        )

    return None


def _show_login_form(
    flow: FlowHandler,
    user_input: dict[str, Any],
    errors: dict[str, str],
    placeholders: dict[str, Any],
) -> FlowResult:
    """Shows the Tuya IOT platform login form."""
    
    return flow.async_show_form(
        step_id="login",
        data_schema=vol.Schema(
            {
                vol.Required(
                    CONF_ACCESS_ID, default=user_input.get(CONF_ACCESS_ID, "")
                ): str,
                vol.Required(
                    CONF_ACCESS_SECRET,
                    default=user_input.get(CONF_ACCESS_SECRET, ""),
                ): str,
                vol.Required(
                    CONF_TUYA_DEVICE_ID,
                    default=user_input.get(CONF_TUYA_DEVICE_ID, ""),
                ): str,
                vol.Required(
                    CONF_REGION,
                    default=user_input.get(CONF_REGION, "eu"),
                ): vol.In(
                    # Region selector for Tuya Cloud access
                    [region.code for region in TUYA_REGIONS]
                ),
            }
        ),
        errors=errors,
        description_placeholders=placeholders,
    )


class TuyaBLEOptionsFlow(OptionsFlowWithConfigEntry):
    """Handle a Tuya BLE options flow."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        super().__init__(config_entry)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        return await self.async_step_login(user_input)

    async def async_step_login(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the Tuya IOT platform login step."""
        errors: dict[str, str] = {}
        placeholders: dict[str, Any] = {}
        credentials: TuyaBLEDeviceCredentials | None = None
        address: str | None = self.config_entry.data.get(CONF_ADDRESS)

        if user_input is not None:
            entry: TuyaBLEData | None = None
            domain_data = self.hass.data.get(DOMAIN)
            if domain_data:
                entry = domain_data.get(self.config_entry.entry_id)
            if entry:
                login_data = await _try_login(
                    entry.manager,
                    user_input,
                    errors,
                    placeholders,
                )
                if login_data:
                    credentials = await entry.manager.get_device_credentials(
                        address, True, True
                    )
                    if credentials:
                        return self.async_create_entry(
                            title=self.config_entry.title,
                            data=entry.manager.data,
                        )
                    else:
                        errors["base"] = "device_not_registered"

        if user_input is None:
            user_input = {}
            user_input.update(self.config_entry.options)

        return _show_login_form(self, user_input, errors, placeholders)


class TuyaBLEConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tuya BLE."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        super().__init__()
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_devices: dict[str, BluetoothServiceInfoBleak] = {}
        self._data: dict[str, Any] = {}
        self._manager: HASSTuyaBLEDeviceManager | None = None
        self._get_device_info_error = False

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> FlowResult:
        """Handle the bluetooth discovery step."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._discovery_info = discovery_info
        if self._manager is None:
            self._manager = HASSTuyaBLEDeviceManager(self.hass, self._data)
        await self._manager.build_cache()
        self.context["title_placeholders"] = {
            "name": await get_device_readable_name(
                discovery_info,
                self._manager,
            )
        }
        return await self.async_step_login()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the user step."""
        if self._manager is None:
            self._manager = HASSTuyaBLEDeviceManager(self.hass, self._data)
        await self._manager.build_cache()
        return await self.async_step_login()

    async def async_step_login(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the Tuya IOT platform login step."""
        data: dict[str, Any] | None = None
        errors: dict[str, str] = {}
        placeholders: dict[str, Any] = {}

        if user_input is not None:
            data = await _try_login(
                self._manager,
                user_input,
                errors,
                placeholders,
            )
            if data:
                self._data.update(data)
                # Populate the device cache with the new login data
                await self._manager._login(data, True)
                # Force cache population for the new credentials
                global _cache
                cache_key = self._manager._get_cache_key(data)
                cache_item = _cache.get(cache_key)
                if cache_item and len(cache_item.credentials) == 0:
                    await self._manager._fill_cache_item(cache_item)
                
                return await self.async_step_device()

        if user_input is None:
            user_input = {}
            if self._discovery_info:
                await self._manager.get_device_credentials(
                    self._discovery_info.address,
                    False,
                    True,
                )
            if self._data is None or len(self._data) == 0:
                self._manager.get_login_from_cache()
            if self._data is not None and len(self._data) > 0:
                user_input.update(self._data)

        return _show_login_form(self, user_input, errors, placeholders)

    async def async_step_device(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the user step to pick discovered device."""
        errors: dict[str, str] = {}

        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            
            # Handle manual MAC entry selection
            if address == "manual":
                return await self.async_step_manual_mac()
            
            # Check if it's a manual MAC address entry
            if address not in self._discovered_devices:
                # Validate MAC address format
                import re
                if not re.match(r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$', address):
                    errors["base"] = "invalid_mac_address"
                    return await self._show_device_form(errors)
                # Create a fake discovery info for manual entry
                self._discovered_devices[address] = type('obj', (object,), {
                    'address': address,
                    'name': f'Manual Entry ({address})',
                    'rssi': None,
                })()

            discovery_info = self._discovered_devices[address]
            local_name = await get_device_readable_name(discovery_info, self._manager)
            await self.async_set_unique_id(
                discovery_info.address, raise_on_progress=False
            )
            self._abort_if_unique_id_configured()
            credentials = await self._manager.get_device_credentials(
                discovery_info.address, self._get_device_info_error, True
            )
            self._data[CONF_ADDRESS] = discovery_info.address
            if credentials is None:
                self._get_device_info_error = True
                errors["base"] = "device_not_registered"
            else:
                return self.async_create_entry(
                    title=local_name,
                    data={CONF_ADDRESS: discovery_info.address},
                    options=self._data,
                )

        # Perform enhanced device discovery
        await self._perform_enhanced_discovery()

        if not self._discovered_devices:
            return self.async_abort(reason="no_unconfigured_devices")

        return await self._show_device_form(errors)

    async def _perform_enhanced_discovery(self) -> None:
        """Perform enhanced device discovery with multiple attempts and active scanning."""
        import asyncio

        current_addresses = self._async_current_ids()
        _LOGGER.debug("Current configured addresses: %s", current_addresses)

        # First attempt: Check already discovered devices
        for discovery in async_discovered_service_info(self.hass):
            _LOGGER.debug(
                "Scanning device: %s, address: %s, service_data: %s, service_uuids: %s",
                discovery.name,
                discovery.address,
                discovery.service_data,
                discovery.service_uuids if hasattr(discovery, 'service_uuids') else 'N/A'
            )
            
            if discovery.address in current_addresses:
                _LOGGER.debug("Device %s already configured, skipping", discovery.address)
                continue
            if discovery.address in self._discovered_devices:
                _LOGGER.debug("Device %s already in discovered list, skipping", discovery.address)
                continue
            if discovery.service_data is None:
                _LOGGER.debug("Device %s has no service_data, skipping", discovery.address)
                continue
            if not SERVICE_UUID in discovery.service_data.keys():
                _LOGGER.debug(
                    "Device %s missing SERVICE_UUID (%s) in service_data keys: %s",
                    discovery.address,
                    SERVICE_UUID,
                    list(discovery.service_data.keys())
                )
                continue
            
            _LOGGER.info("Found Tuya BLE device: %s (%s)", discovery.name, discovery.address)
            self._discovered_devices[discovery.address] = discovery

        # If we have devices, return early
        if self._discovered_devices:
            _LOGGER.info("Found %d Tuya BLE device(s) in first scan", len(self._discovered_devices))
            return

        # Second attempt: Wait and scan again (allows for intermittent advertising)
        _LOGGER.debug("No devices found in first scan, waiting 3 seconds for second scan...")
        await asyncio.sleep(3)
        for discovery in async_discovered_service_info(self.hass):
            if (
                discovery.address in current_addresses
                or discovery.address in self._discovered_devices
                or discovery.service_data is None
                or not SERVICE_UUID in discovery.service_data.keys()
            ):
                continue
            _LOGGER.info("Found Tuya BLE device (2nd scan): %s (%s)", discovery.name, discovery.address)
            self._discovered_devices[discovery.address] = discovery

        # If we still have devices, return
        if self._discovered_devices:
            _LOGGER.info("Found %d Tuya BLE device(s) in second scan", len(self._discovered_devices))
            return

        # Third attempt: Wait longer and scan again
        _LOGGER.debug("No devices found in second scan, waiting 5 seconds for third scan...")
        await asyncio.sleep(5)
        for discovery in async_discovered_service_info(self.hass):
            if (
                discovery.address in current_addresses
                or discovery.address in self._discovered_devices
                or discovery.service_data is None
                or not SERVICE_UUID in discovery.service_data.keys()
            ):
                continue
            _LOGGER.info("Found Tuya BLE device (3rd scan): %s (%s)", discovery.name, discovery.address)
            self._discovered_devices[discovery.address] = discovery
        
        if self._discovered_devices:
            _LOGGER.info("Found %d Tuya BLE device(s) in third scan", len(self._discovered_devices))
        else:
            _LOGGER.warning("No Tuya BLE devices found after all scan attempts")

        # Final fallback: Check cloud cache for registered devices
        if not self._discovered_devices and self._manager:
            _LOGGER.debug("Checking cloud cache for registered devices...")
            from .cloud import _cache
            for cache_item in _cache.values():
                if cache_item.credentials:
                    _LOGGER.debug("Found %d devices in cloud cache", len(cache_item.credentials))
                    # Add cloud devices to discovered devices list
                    for mac_address, device_data in cache_item.credentials.items():
                        if mac_address not in current_addresses:
                            _LOGGER.info("Adding cloud-registered device: %s", mac_address)
                            # Create a fake discovery info for cloud devices
                            # This allows users to configure cloud-registered devices
                            # even if they're not currently discoverable via Bluetooth
                            self._discovered_devices[mac_address] = type('obj', (object,), {
                                'address': mac_address,
                                'name': device_data.get(CONF_DEVICE_NAME, 'Unknown Device'),
                                'rssi': None,
                            })()
            if self._discovered_devices:
                _LOGGER.info("Found %d device(s) from cloud cache", len(self._discovered_devices))
            else:
                _LOGGER.debug("No devices found in cloud cache")

    async def _show_device_form(self, errors: dict[str, str]) -> FlowResult:
        """Show the device selection form with manual MAC entry option."""
        def_address: str = ""
        if self._discovered_devices:
            def_address = list(self._discovered_devices)[0]

        # Create options dict with discovered devices
        device_options = {}
        for service_info in self._discovered_devices.values():
            device_options[service_info.address] = await get_device_readable_name(
                service_info,
                self._manager,
            )

        # Add manual entry option
        device_options["manual"] = "Enter MAC address manually"

        return self.async_show_form(
            step_id="device",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_ADDRESS,
                        default=def_address,
                    ): vol.In(device_options),
                },
            ),
            errors=errors,
            description_placeholders={
                "scan_status": "Scanning for Tuya BLE devices... Please ensure your devices are powered on and in pairing mode."
            },
        )

    async def async_step_manual_mac(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle manual MAC address entry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            address = user_input[CONF_ADDRESS].upper()
            # Validate MAC address format
            import re
            if not re.match(r'^([0-9A-F]{2}[:-]){5}([0-9A-F]{2})$', address):
                errors["base"] = "invalid_mac_address"
            else:
                # Create a fake discovery info for manual entry
                self._discovered_devices[address] = type('obj', (object,), {
                    'address': address,
                    'name': f'Manual Entry ({address})',
                    'rssi': None,
                })()
                # Proceed to device selection with the manual entry
                return await self.async_step_device({CONF_ADDRESS: address})

        return self.async_show_form(
            step_id="manual_mac",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): str,
                }
            ),
            errors=errors,
            description_placeholders={
                "instructions": "Enter the MAC address of your Tuya BLE device (format: AA:BB:CC:DD:EE:FF)"
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> TuyaBLEOptionsFlow:
        """Get the options flow for this handler."""
        return TuyaBLEOptionsFlow(config_entry)
