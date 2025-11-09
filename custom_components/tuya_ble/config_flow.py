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
)
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowHandler, FlowResult

from .const import (
    CONF_ACCESS_ID,
    CONF_ACCESS_SECRET,
    CONF_REGION,
    CONF_TUYA_DEVICE_ID,
    TUYA_REGIONS,
    TUYA_RESPONSE_CODE,
    TUYA_RESPONSE_MSG,
    TUYA_RESPONSE_SUCCESS,
)

from .tuya_ble import TuyaBLEDeviceCredentials

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
    device_mac: str | None = None,
) -> dict[str, Any] | None:
    response: dict[Any, Any] | None
    data: dict[str, Any]

    data = {
        CONF_ACCESS_ID: user_input[CONF_ACCESS_ID],
        CONF_ACCESS_SECRET: user_input[CONF_ACCESS_SECRET],
        CONF_REGION: user_input[CONF_REGION],
    }
    
    # Only include device ID if provided (for options flow)
    if CONF_TUYA_DEVICE_ID in user_input:
        data[CONF_TUYA_DEVICE_ID] = user_input[CONF_TUYA_DEVICE_ID]

    response = await manager._login(data, True)

    if response.get(TUYA_RESPONSE_SUCCESS, False):
        # If we have a device MAC, try to find the device ID automatically
        if device_mac:
            cache_key = manager._get_cache_key(data)
            cache_item = _cache.get(cache_key)
            if cache_item and len(cache_item.credentials) == 0:
                await manager._fill_cache_item(cache_item)
            
            # Search for the device by MAC address in credentials
            if cache_item and cache_item.credentials:
                for mac_address, device_data in cache_item.credentials.items():
                    if mac_address.upper() == device_mac.upper():
                        data[CONF_TUYA_DEVICE_ID] = device_data.get(CONF_TUYA_DEVICE_ID, "")
                        _LOGGER.info("Found device ID for MAC %s: %s", device_mac, data[CONF_TUYA_DEVICE_ID])
                        return data
                
                # Device not found in cloud
                errors["base"] = "device_not_registered"
                placeholders["mac_address"] = device_mac
                return None
        
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
    show_device_id: bool = False,
) -> FlowResult:
    """Shows the Tuya IOT platform login form."""
    
    schema_fields = {
        vol.Required(
            CONF_ACCESS_ID, default=user_input.get(CONF_ACCESS_ID, "")
        ): str,
        vol.Required(
            CONF_ACCESS_SECRET,
            default=user_input.get(CONF_ACCESS_SECRET, ""),
        ): str,
    }
    
    # Only show device ID field in options flow
    if show_device_id:
        schema_fields[vol.Required(
            CONF_TUYA_DEVICE_ID,
            default=user_input.get(CONF_TUYA_DEVICE_ID, ""),
        )] = str
    
    schema_fields[vol.Required(
        CONF_REGION,
        default=user_input.get(CONF_REGION, "eu"),
    )] = vol.In(
        # Region selector for Tuya Cloud access
        [region.code for region in TUYA_REGIONS]
    )
    
    return flow.async_show_form(
        step_id="login",
        data_schema=vol.Schema(schema_fields),
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
                    address,  # Pass the device MAC
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

        return _show_login_form(self, user_input, errors, placeholders, show_device_id=True)


class TuyaBLEConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tuya BLE."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        super().__init__()
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._data: dict[str, Any] = {}
        self._manager: HASSTuyaBLEDeviceManager | None = None

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
        """Handle the user step - not supported, devices must be discovered via Bluetooth."""
        return self.async_abort(reason="use_bluetooth_discovery")

    async def async_step_login(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the Tuya IOT platform login step."""
        data: dict[str, Any] | None = None
        errors: dict[str, str] = {}
        placeholders: dict[str, Any] = {}

        if not self._discovery_info:
            return self.async_abort(reason="no_bluetooth_discovery")

        if user_input is not None:
            data = await _try_login(
                self._manager,
                user_input,
                errors,
                placeholders,
                self._discovery_info.address,  # Pass the discovered device MAC
            )
            if data:
                self._data.update(data)
                self._data[CONF_ADDRESS] = self._discovery_info.address
                
                # Verify credentials were retrieved
                credentials = await self._manager.get_device_credentials(
                    self._discovery_info.address, 
                    True, 
                    True
                )
                
                if credentials:
                    local_name = await get_device_readable_name(
                        self._discovery_info,
                        self._manager,
                    )
                    return self.async_create_entry(
                        title=local_name,
                        data={CONF_ADDRESS: self._discovery_info.address},
                        options=self._data,
                    )
                else:
                    errors["base"] = "device_not_registered"
                    placeholders["mac_address"] = self._discovery_info.address

        if user_input is None:
            user_input = {}
            # Try to get cached credentials for this device
            if self._discovery_info:
                await self._manager.get_device_credentials(
                    self._discovery_info.address,
                    False,
                    True,
                )
            # Check if we have cached login data
            if self._data is None or len(self._data) == 0:
                self._manager.get_login_from_cache()
            if self._data is not None and len(self._data) > 0:
                user_input.update(self._data)

        # Add device name/MAC to placeholders
        placeholders["device_name"] = await get_device_readable_name(
            self._discovery_info,
            self._manager,
        )
        placeholders["mac_address"] = self._discovery_info.address

        return _show_login_form(self, user_input, errors, placeholders, show_device_id=False)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> TuyaBLEOptionsFlow:
        """Get the options flow for this handler."""
        return TuyaBLEOptionsFlow(config_entry)
