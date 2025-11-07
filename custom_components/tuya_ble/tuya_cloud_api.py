"""Tuya Cloud API client - standalone implementation without tinytuya dependency."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)


class TuyaCloudAPIError(Exception):
    """Tuya Cloud API error."""
    pass


class TuyaCloudAPI:
    """Standalone Tuya Cloud API client."""

    def __init__(
        self,
        api_region: str,
        api_key: str,
        api_secret: str,
        api_device_id: str | None = None,
    ) -> None:
        """Initialize Tuya Cloud API client.
        
        Args:
            api_region: Tuya API region code (e.g., 'us', 'eu', 'cn', 'in')
            api_key: Tuya Cloud API key (Access ID)
            api_secret: Tuya Cloud API secret
            api_device_id: Optional device ID for initial API calls
        """
        self.api_region = api_region.lower()
        self.api_key = api_key
        self.api_secret = api_secret
        self.api_device_id = api_device_id
        self.token: str | None = None
        self.error: dict[str, Any] | None = None
        self._session: aiohttp.ClientSession | None = None
        
        # Set API endpoint based on region
        self.url_host = self._get_url_host(api_region)
    
    def _get_url_host(self, region: str) -> str:
        """Get API endpoint URL for the specified region."""
        region = region.lower()
        endpoints = {
            "cn": "openapi.tuyacn.com",          # China Data Center
            "us": "openapi.tuyaus.com",          # Western America Data Center
            "az": "openapi.tuyaus.com",          # Western America Data Center (alias)
            "us-e": "openapi-ueaz.tuyaus.com",   # Eastern America Data Center
            "ue": "openapi-ueaz.tuyaus.com",     # Eastern America Data Center (alias)
            "eu": "openapi.tuyaeu.com",          # Central Europe Data Center
            "eu-w": "openapi-weaz.tuyaeu.com",   # Western Europe Data Center
            "we": "openapi-weaz.tuyaeu.com",     # Western Europe Data Center (alias)
            "in": "openapi.tuyain.com",          # India Data Center
            "sg": "openapi-sg.iotbing.com",      # Singapore Data Center
        }
        return endpoints.get(region, "openapi.tuyaeu.com")  # Default to EU
    
    def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def close(self) -> None:
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()
    
    def _generate_signature(
        self,
        payload: str,
    ) -> str:
        """Generate HMAC-SHA256 signature."""
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            msg=payload.encode('utf-8'),
            digestmod=hashlib.sha256
        ).hexdigest().upper()
        return signature
    
    async def _make_request(
        self,
        uri: str,
        method: str = "GET",
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make HTTP request to Tuya Cloud API.
        
        Args:
            uri: API endpoint URI (e.g., 'token?grant_type=1')
            method: HTTP method (GET, POST, etc.)
            data: POST body data
            params: Query parameters
            
        Returns:
            Response dictionary from API
        """
        # Build URL
        if uri.startswith('/'):
            url = f"https://{self.url_host}{uri}"
        elif uri.startswith('http'):
            url = uri
        else:
            url = f"https://{self.url_host}/v1.0/{uri}"
        
        # Prepare headers
        timestamp = str(int(time.time() * 1000))
        headers = {
            "client_id": self.api_key,
            "sign_method": "HMAC-SHA256",
            "t": timestamp,
        }
        
        # Prepare body
        body = ""
        if data:
            body = json.dumps(data)
            headers["Content-Type"] = "application/json"
        
        # Generate signature
        if self.token is None:
            # OAuth token request
            payload = self.api_key + timestamp
            headers["secret"] = self.api_secret
        else:
            # Service management request
            payload = self.api_key + self.token + timestamp
            headers["access_token"] = self.token
        
        # Add body hash to payload (new signing algorithm)
        content_sha256 = hashlib.sha256(body.encode('utf-8')).hexdigest()
        payload += f"{method}\n{content_sha256}\n\n"
        
        # Add URL path to payload
        url_path = '/' + url.split('//', 1)[-1].split('/', 1)[-1]
        payload += url_path
        
        signature = self._generate_signature(payload)
        headers["sign"] = signature
        
        _LOGGER.debug(
            "Making %s request to %s with headers: %s",
            method,
            url,
            {k: v for k, v in headers.items() if k not in ["secret", "access_token", "sign"]}
        )
        
        # Make request
        session = self._get_session()
        try:
            if method == "GET":
                async with session.get(url, headers=headers, params=params) as response:
                    response_text = await response.text()
                    _LOGGER.debug("Response status: %s, body: %s", response.status, response_text)
                    result = json.loads(response_text)
            else:
                async with session.post(url, headers=headers, data=body, params=params) as response:
                    response_text = await response.text()
                    _LOGGER.debug("Response status: %s, body: %s", response.status, response_text)
                    result = json.loads(response_text)
            
            return result
        except Exception as e:
            _LOGGER.error("Request failed: %s", str(e))
            raise TuyaCloudAPIError(f"Request failed: {str(e)}") from e
    
    async def get_token(self) -> str | None:
        """Get OAuth token from Tuya Cloud.
        
        Returns:
            Access token if successful, None otherwise
        """
        try:
            response = await self._make_request("token?grant_type=1", method="GET")
            
            if not response.get("success"):
                error_msg = response.get("msg", "Unknown error")
                _LOGGER.error("Failed to get token: %s", error_msg)
                self.error = {
                    "success": False,
                    "msg": error_msg,
                    "code": response.get("code"),
                }
                return None
            
            self.token = response["result"]["access_token"]
            self.error = None
            _LOGGER.debug("Successfully obtained access token")
            return self.token
            
        except Exception as e:
            _LOGGER.error("Exception getting token: %s", str(e))
            self.error = {
                "success": False,
                "msg": str(e),
                "code": None,
            }
            return None
    
    async def get_user_id(self, device_id: str) -> str | None:
        """Get user ID for a device.
        
        Args:
            device_id: Device ID
            
        Returns:
            User ID if successful, None otherwise
        """
        if not self.token:
            await self.get_token()
            if not self.token:
                return None
        
        try:
            uri = f"devices/{device_id}"
            response = await self._make_request(uri, method="GET")
            
            if not response.get("success"):
                error_msg = response.get("msg", "Unknown error")
                _LOGGER.error("Failed to get user ID: %s", error_msg)
                return None
            
            return response["result"]["uid"]
            
        except Exception as e:
            _LOGGER.error("Exception getting user ID: %s", str(e))
            return None
    
    async def get_devices(self, user_id: str | None = None) -> dict[str, Any]:
        """Get list of devices from Tuya Cloud.
        
        Args:
            user_id: Optional user ID to get devices for specific user
            
        Returns:
            Dictionary with 'success' and 'result' keys containing device list
        """
        if not self.token:
            await self.get_token()
            if not self.token:
                return {"success": False, "msg": "Failed to get token"}
        
        try:
            if user_id:
                # Get devices for specific user
                uri = f"users/{user_id}/devices"
            elif self.api_device_id:
                # Get user ID from device ID, then get devices
                user_id = await self.get_user_id(self.api_device_id)
                if not user_id:
                    return {"success": False, "msg": "Failed to get user ID"}
                uri = f"users/{user_id}/devices"
            else:
                # Get all devices
                uri = "/v1.0/iot-01/associated-users/devices"
            
            response = await self._make_request(uri, method="GET")
            
            if not response.get("success"):
                error_msg = response.get("msg", "Unknown error")
                _LOGGER.error("Failed to get devices: %s", error_msg)
                return response
            
            _LOGGER.debug("Successfully retrieved %d devices", len(response.get("result", [])))
            return response
            
        except Exception as e:
            _LOGGER.error("Exception getting devices: %s", str(e))
            return {"success": False, "msg": str(e)}
    
    async def cloud_request(
        self,
        url: str,
        method: str = "GET",
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make a generic cloud request.
        
        Args:
            url: API endpoint URL or path
            method: HTTP method (GET, POST, etc.)
            data: POST body data
            params: Query parameters
            
        Returns:
            Response dictionary from API
        """
        if not self.token:
            await self.get_token()
            if not self.token:
                return {"success": False, "msg": "Failed to get token"}
        
        try:
            return await self._make_request(url, method=method, data=data, params=params)
        except Exception as e:
            _LOGGER.error("Cloud request failed: %s", str(e))
            return {"success": False, "msg": str(e)}
