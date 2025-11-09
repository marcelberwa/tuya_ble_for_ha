"""The Tuya BLE integration."""
from __future__ import annotations

import logging
import voluptuous as vol

from bleak_retry_connector import BLEAK_RETRY_EXCEPTIONS as BLEAK_EXCEPTIONS, get_device

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth.match import ADDRESS, BluetoothCallbackMatcher
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady

from .tuya_ble import TuyaBLEDevice

from .cloud import HASSTuyaBLEDeviceManager
from .const import DOMAIN
from .devices import TuyaBLECoordinator, TuyaBLEData, get_device_product_info
from .holiday import HolidayModeHelper

PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SELECT,
    Platform.SWITCH,
    Platform.TEXT,
]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Tuya BLE from a config entry."""
    address: str = entry.data[CONF_ADDRESS]
    ble_device = bluetooth.async_ble_device_from_address(
        hass, address.upper(), True
    ) or await get_device(address)
    if not ble_device:
        raise ConfigEntryNotReady(
            f"Could not find Tuya BLE device with address {address}"
        )
    manager = HASSTuyaBLEDeviceManager(hass, entry.options.copy())
    device = TuyaBLEDevice(manager, ble_device)
    await device.initialize()
    product_info = get_device_product_info(device)

    coordinator = TuyaBLECoordinator(hass, device)

    '''
    try:
        await device.update()
    except BLEAK_EXCEPTIONS as ex:
        raise ConfigEntryNotReady(
            f"Could not communicate with Tuya BLE device with address {address}"
        ) from ex
    '''
    hass.add_job(device.update())

    @callback
    def _async_update_ble(
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        """Update from a ble callback."""
        device.set_ble_device_and_advertisement_data(
            service_info.device, service_info.advertisement
        )

    entry.async_on_unload(
        bluetooth.async_register_callback(
            hass,
            _async_update_ble,
            BluetoothCallbackMatcher({ADDRESS: address}),
            bluetooth.BluetoothScanningMode.ACTIVE,
        )
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = TuyaBLEData(
        entry.title,
        device,
        product_info,
        manager,
        coordinator,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    async def _async_stop(event: Event) -> None:
        """Close the connection."""
        await device.stop()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_stop)
    )
    
    # Register holiday mode service
    async def handle_set_holiday_mode(call):
        """Handle set_holiday_mode service call."""
        device_id = call.data.get("device_id")
        temperature = call.data.get("temperature")
        start_date = call.data.get("start_date")
        end_date = call.data.get("end_date")
        start_hour = call.data.get("start_hour", 0)
        start_minute = call.data.get("start_minute", 0)
        end_hour = call.data.get("end_hour", 0)
        end_minute = call.data.get("end_minute", 0)
        
        # Find the device
        if device.device_id == device_id:
            await HolidayModeHelper.set_holiday_mode(
                device=device,
                temperature=temperature,
                start_date=start_date,
                end_date=end_date,
                start_hour=start_hour,
                start_minute=start_minute,
                end_hour=end_hour,
                end_minute=end_minute,
            )
    
    hass.services.async_register(
        DOMAIN,
        "set_holiday_mode",
        handle_set_holiday_mode,
        schema=vol.Schema({
            vol.Required("device_id"): str,
            vol.Required("temperature"): vol.Range(min=0.5, max=29.5),
            vol.Required("start_date"): str,  # YYYY-MM-DD
            vol.Required("end_date"): str,    # YYYY-MM-DD
            vol.Optional("start_hour", default=0): vol.Range(min=0, max=23),
            vol.Optional("start_minute", default=0): vol.Range(min=0, max=59),
            vol.Optional("end_hour", default=0): vol.Range(min=0, max=23),
            vol.Optional("end_minute", default=0): vol.Range(min=0, max=59),
        }),
    )
    
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    data: TuyaBLEData = hass.data[DOMAIN][entry.entry_id]
    if entry.title != data.title:
        await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        data: TuyaBLEData = hass.data[DOMAIN].pop(entry.entry_id)
        await data.device.stop()

    return unload_ok
