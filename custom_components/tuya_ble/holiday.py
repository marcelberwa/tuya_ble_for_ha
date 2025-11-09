"""Holiday mode helper for Tuya BLE thermostat."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

from .tuya_ble import TuyaBLEDevice, TuyaBLEDataPointType

_LOGGER = logging.getLogger(__name__)


class HolidayModeHelper:
    """Helper class to manage holiday mode configuration for hkdvdvef thermostat."""
    
    @staticmethod
    def build_holiday_data(
        temperature: float,
        start_date: str,  # Format: "YYYY-MM-DD"
        end_date: str,    # Format: "YYYY-MM-DD"
        start_hour: int = 0,
        start_minute: int = 0,
        end_hour: int = 0,
        end_minute: int = 0,
    ) -> bytes | None:
        """Build 8-byte holiday configuration data.
        
        Format:
        - Byte 0: Start year offset from 2000
        - Byte 1: Start month
        - Byte 2: Start day
        - Byte 3: Start hour
        - Byte 4: Start minute
        - Byte 5: Temperature (0.5°C steps)
        - Bytes 6-7: Duration in hours (16-bit big-endian)
        """
        try:
            # Parse dates
            start_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(
                hour=start_hour, minute=start_minute
            )
            end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(
                hour=end_hour, minute=end_minute
            )
            
            # Validate
            if start_dt >= end_dt:
                _LOGGER.error("Start date must be before end date")
                return None
            
            if temperature < 0.5 or temperature > 29.5:
                _LOGGER.error("Temperature must be between 0.5 and 29.5°C")
                return None
            
            # Calculate duration in hours
            duration_delta = end_dt - start_dt
            duration_hours = int(duration_delta.total_seconds() / 3600)
            
            if duration_hours > 65535:
                _LOGGER.error("Duration too long (max 65535 hours)")
                return None
            
            # Build 8-byte holiday data
            holiday_data = bytearray(8)
            
            # Bytes 0-4: Start date/time
            holiday_data[0] = (start_dt.year - 2000) & 0xFF
            holiday_data[1] = start_dt.month & 0xFF
            holiday_data[2] = start_dt.day & 0xFF
            holiday_data[3] = start_dt.hour & 0xFF
            holiday_data[4] = start_dt.minute & 0xFF
            
            # Byte 5: Temperature (0.5°C steps, so multiply by 2)
            temp_raw = int(temperature * 2) & 0xFF
            holiday_data[5] = temp_raw
            
            # Bytes 6-7: Duration in hours (16-bit big-endian)
            holiday_data[6] = (duration_hours >> 8) & 0xFF  # High byte
            holiday_data[7] = duration_hours & 0xFF         # Low byte
            
            _LOGGER.debug(
                f"Built holiday data: {temperature}°C, "
                f"{start_date} {start_hour:02d}:{start_minute:02d} to "
                f"{end_date} {end_hour:02d}:{end_minute:02d} "
                f"({duration_hours} hours)"
            )
            
            return bytes(holiday_data)
            
        except ValueError as e:
            _LOGGER.error(f"Invalid date format: {e}")
            return None
        except Exception as e:
            _LOGGER.error(f"Error building holiday data: {e}")
            return None
    
    @staticmethod
    async def set_holiday_mode(
        device: TuyaBLEDevice,
        temperature: float,
        start_date: str,
        end_date: str,
        start_hour: int = 0,
        start_minute: int = 0,
        end_hour: int = 0,
        end_minute: int = 0,
    ) -> bool:
        """Set holiday mode configuration on device (DP103)."""
        try:
            # Build holiday data
            holiday_data = HolidayModeHelper.build_holiday_data(
                temperature=temperature,
                start_date=start_date,
                end_date=end_date,
                start_hour=start_hour,
                start_minute=start_minute,
                end_hour=end_hour,
                end_minute=end_minute,
            )
            
            if holiday_data is None:
                return False
            
            # Set DP103
            datapoint = device.datapoints.get_or_create(
                103,
                TuyaBLEDataPointType.DT_RAW,
                holiday_data,
            )
            
            if datapoint:
                await datapoint.set_value(holiday_data)
                _LOGGER.info(f"Holiday mode configured: {temperature}°C")
                return True
            else:
                _LOGGER.error("Failed to create datapoint for holiday mode")
                return False
                
        except Exception as e:
            _LOGGER.error(f"Failed to set holiday mode: {e}")
            return False
    
    @staticmethod
    def parse_holiday_data(raw_data: bytes) -> dict | None:
        """Parse holiday data from device (DP103)."""
        try:
            if not isinstance(raw_data, bytes) or len(raw_data) < 8:
                return None
            
            # Parse 8-byte format
            start_year = 2000 + raw_data[0]
            start_month = raw_data[1]
            start_day = raw_data[2]
            start_hour = raw_data[3]
            start_minute = raw_data[4]
            
            temp_raw = raw_data[5]
            temperature = temp_raw / 2.0
            
            duration_hours = (raw_data[6] << 8) | raw_data[7]
            
            # Calculate end date/time
            start_dt = datetime(start_year, start_month, start_day, start_hour, start_minute)
            end_dt = start_dt + timedelta(hours=duration_hours)
            
            return {
                "enabled": temperature > 0,
                "temperature": temperature,
                "start_date": start_dt.strftime("%Y-%m-%d"),
                "start_time": start_dt.strftime("%H:%M"),
                "end_date": end_dt.strftime("%Y-%m-%d"),
                "end_time": end_dt.strftime("%H:%M"),
                "duration_hours": duration_hours,
            }
            
        except Exception as e:
            _LOGGER.error(f"Error parsing holiday data: {e}")
            return None
