import os
import requests
import aiohttp
from typing import Dict, Optional
from dataclasses import dataclass
from dotenv import load_dotenv
import asyncio

load_dotenv()

@dataclass
class IPInfo:
    ip: str
    country: Optional[str]
    city: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    org: Optional[str]
    reputation_score: Optional[float]

class IPInfoService:
    def __init__(self):
        # No longer getting API key from environment variables, default is None
        self._api_key = None
        self._session = None
    
    @property
    def api_key(self):
        return self._api_key
    
    @api_key.setter
    def api_key(self, value):
        self._api_key = value
    
    async def _get_session(self):
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def get_ip_info(self, ip: str) -> IPInfo:
        """
        Get IP information from API (async version).
        
        Args:
            ip: IP address to query
            
        Returns:
            IPInfo: IP information including location and reputation
        """
        # Fetch from API asynchronously
        try:
            headers = {}
            if self._api_key:
                headers['Authorization'] = f'Bearer {self._api_key}'

            session = await self._get_session()
            async with session.get(
                f'https://ipinfo.io/{ip}/json',
                headers=headers,
                timeout=5
            ) as response:
                if response.status != 200:
                    raise Exception(f"API request failed with status {response.status}")
                
                data = await response.json()
                return self._parse_ip_info(ip, data)
            
        except Exception as e:  # Catch all exceptions
            print(f"Error getting IP info for {ip}: {str(e)}")
            # If API fails, return minimal info
            return IPInfo(
                ip=ip,
                country=None,
                city=None,
                latitude=None,
                longitude=None,
                org=None,
                reputation_score=None
            )
    
    # Backwards compatibility method - non-async version
    def get_ip_info_sync(self, ip: str) -> IPInfo:
        """
        Get IP information from API (sync version).
        
        Args:
            ip: IP address to query
            
        Returns:
            IPInfo: IP information including location and reputation
        """
        # Fetch from API
        try:
            headers = {}
            if self._api_key:
                headers['Authorization'] = f'Bearer {self._api_key}'

            response = requests.get(
                f'https://ipinfo.io/{ip}/json',
                headers=headers,
                timeout=5
            )
            response.raise_for_status()
            
            data = response.json()
            return self._parse_ip_info(ip, data)
            
        except Exception as e:  # Catch all exceptions
            print(f"Error getting IP info for {ip}: {str(e)}")
            # If API fails, return minimal info
            return IPInfo(
                ip=ip,
                country=None,
                city=None,
                latitude=None,
                longitude=None,
                org=None,
                reputation_score=None
            )

    def _parse_ip_info(self, ip: str, data: Dict) -> IPInfo:
        """
        Parse IP info API response into IPInfo object.
        """
        try:
            loc = data.get('loc', '').split(',')
            latitude = float(loc[0]) if loc and loc[0] else None
            longitude = float(loc[1]) if len(loc) > 1 and loc[1] else None
            
            return IPInfo(
                ip=ip,
                country=data.get('country'),
                city=data.get('city'),
                latitude=latitude,
                longitude=longitude,
                org=data.get('org'),
                reputation_score=self._calculate_reputation_score(data)
            )
        except (ValueError, TypeError):
            # If parsing fails, return minimal info
            return IPInfo(
                ip=ip,
                country=None,
                city=None,
                latitude=None,
                longitude=None,
                org=None,
                reputation_score=None
            )

    def _calculate_reputation_score(self, data: Dict) -> float:
        """
        Calculate a simple reputation score based on available data.
        This is a placeholder for a more sophisticated scoring system.
        """
        score = 0.5  # Default score
        
        # Adjust score based on organization type
        org = data.get('org', '').lower()
        if 'google' in org or 'cloudflare' in org:
            score += 0.3
        elif 'amazon' in org or 'microsoft' in org:
            score += 0.2
            
        return min(max(score, 0), 1)  # Ensure score is between 0 and 1

    async def close(self):
        """Close the aiohttp session when done."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None 