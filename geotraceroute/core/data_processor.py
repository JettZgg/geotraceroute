import logging
from typing import List, Dict, Any, AsyncGenerator, Optional
from geotraceroute.core.traceroute import Traceroute, Hop
from geotraceroute.core.ip_info import IPInfoService, IPInfo
import asyncio
import geoip2.database
import os
import ipaddress

class DataProcessor:
    def __init__(self, test_mode=False):
        """Initialize the DataProcessor with GeoIP databases.

        Args:
            test_mode (bool): If True, do not load GeoIP databases (for testing)
        """
        self.test_mode = test_mode
        if not test_mode:
            base_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data')
            self.city_reader = geoip2.database.Reader(os.path.join(base_path, 'GeoLite2-City.mmdb'))
            self.asn_reader = geoip2.database.Reader(os.path.join(base_path, 'GeoLite2-ASN.mmdb'))
        else:
            self.city_reader = None
            self.asn_reader = None
        
        self.ip_info_service = IPInfoService()

    async def _enrich_hop_data(self, hop: Hop, include_reputation: bool = False, client_info: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Enrich a hop with geographical and network data.
        
        Args:
            hop: Hop object containing IP and timing data
            include_reputation: Whether to include reputation score from IPInfo API
            client_info: Optional client information including location
            
        Returns:
            dict: Enriched hop data with geographical and network information
        """
        result = {
            "hop_number": hop.hop_number,
            "ip": hop.ip,
            "hostname": hop.hostname,
            "rtt_ms": hop.rtt_ms,
            "city": None,
            "country": None,
            "latitude": None,
            "longitude": None,
            "organization": None,
            "asn": None,
            "reputation_score": None
        }
        
        if hop.ip and not hop.ip.startswith('*'):
            try:
                # Validate IP address format
                ipaddress.ip_address(hop.ip)
                
                # Detect local/private IP address
                is_private = False
                try:
                    ip_obj = ipaddress.ip_address(hop.ip)
                    is_private = ip_obj.is_private
                except:
                    # If parsing fails, check prefixes
                    is_private = hop.ip.startswith(('192.168.', '10.', '172.16.', '172.17.', '172.18.', '172.19.', '172.20.', '172.21.', '172.22.', '172.23.', '172.24.', '172.25.', '172.26.', '172.27.', '172.28.', '172.29.', '172.30.', '172.31.'))
                
                # Handle local/private IP address
                if is_private or hop.hop_number == 1:
                    print(f"Detected local/private IP address: {hop.ip}")
                    
                    # Try to get client location information
                    if client_info and client_info.get('latitude') and client_info.get('longitude'):
                        # Use location information provided by client
                        result.update({
                            "city": client_info.get('city'),
                            "country": client_info.get('country'),
                            "latitude": client_info.get('latitude'),
                            "longitude": client_info.get('longitude'),
                            "organization": "Local Network",
                            "asn": None
                        })
                    else:
                        # Try to use default location from configuration file
                        try:
                            from dotenv import load_dotenv
                            import os
                            load_dotenv()
                            
                            default_lat = os.getenv('DEFAULT_LATITUDE')
                            default_lon = os.getenv('DEFAULT_LONGITUDE')
                            default_city = os.getenv('DEFAULT_CITY', 'Unknown')
                            default_country = os.getenv('DEFAULT_COUNTRY', 'Unknown')
                            
                            if default_lat and default_lon:
                                result.update({
                                    "city": default_city,
                                    "country": default_country,
                                    "latitude": float(default_lat),
                                    "longitude": float(default_lon),
                                    "organization": "Local Network",
                                    "asn": None
                                })
                            else:
                                # If no default location configured, use generic values
                                result.update({
                                    "city": "Unknown",
                                    "country": "Local Area",
                                    "latitude": 0.0,
                                    "longitude": 0.0,
                                    "organization": "Local Network",
                                    "asn": None
                                })
                        except Exception as e:
                            print(f"Unable to get default location: {str(e)}")
                            result.update({
                                "city": "Unknown",
                                "country": "Local Area",
                                "latitude": 0.0,
                                "longitude": 0.0,
                                "organization": "Local Network",
                                "asn": None
                            })
                    
                    if include_reputation:
                        result["reputation_score"] = 0.0  # Local IP has no risk
                elif self.test_mode:
                    # Use mock data in test mode
                    result.update({
                        "city": "Mountain View",
                        "country": "United States",
                        "latitude": 37.4056,
                        "longitude": -122.0775,
                        "organization": "Google LLC",
                        "asn": 15169
                    })
                    if include_reputation:
                        result["reputation_score"] = 0.8
                else:
                    location_found = False
                    
                    # Try GeoIP database lookup
                    try:
                        # Get city/location data
                        response = self.city_reader.city(hop.ip)
                        if response.location.latitude and response.location.longitude:
                            result.update({
                                "city": response.city.name,
                                "country": response.country.name,
                                "latitude": response.location.latitude,
                                "longitude": response.location.longitude
                            })
                            location_found = True
                            
                        # Get ASN/organization data
                        asn_response = self.asn_reader.asn(hop.ip)
                        result.update({
                            "organization": asn_response.autonomous_system_organization,
                            "asn": asn_response.autonomous_system_number
                        })
                    except Exception as e:
                        print(f"GeoIP database lookup failed: {str(e)}")
                    
                    # If GeoIP lookup fails, try using IPInfo service
                    if not location_found:
                        try:
                            print(f"Trying to query IP using IPInfo service: {hop.ip}")
                            ip_info = await self.ip_info_service.get_ip_info(hop.ip)
                            
                            if ip_info.latitude and ip_info.longitude:
                                result.update({
                                    "city": ip_info.city,
                                    "country": ip_info.country,
                                    "latitude": ip_info.latitude,
                                    "longitude": ip_info.longitude,
                                    "organization": ip_info.org
                                })
                                location_found = True
                        except Exception as e:
                            print(f"IPInfo service lookup failed: {str(e)}")
                    
                    # For specific IP ranges, if there's still no location data, use static mapping table
                    if not location_found:
                        # Use simple IP prefix mapping logic
                        if hop.ip.startswith('84.116.'):
                            print(f"Using Ireland default location data for IP: {hop.ip}")
                            result.update({
                                "city": "Dublin",
                                "country": "Ireland",
                                "latitude": 53.3498,
                                "longitude": -6.2603,
                                "organization": "Aorta Network"
                            })
                    
                    # Get reputation score
                    if include_reputation:
                        try:
                            ip_info = await self.ip_info_service.get_ip_info(hop.ip)
                            result["reputation_score"] = ip_info.reputation_score
                        except:
                            # If IPInfo fails, keep reputation_score as None
                            pass
                        
            except Exception as e:
                print(f"Error enriching hop data: {str(e)}")
                # If GeoIP lookup fails, data will remain None
                pass
            
        return result

    async def process_traceroute_stream(self, tracer: Traceroute, include_reputation: bool = False) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Process traceroute results as they arrive.
        
        Args:
            tracer: Traceroute instance to stream results from
            include_reputation: Whether to include reputation scores
            
        Yields:
            dict: Enriched hop data with geographical and network information
        """
        async for hop in tracer.run_stream():
            yield await self._enrich_hop_data(hop, include_reputation)

    async def process_traceroute(self, tracer: Traceroute, include_reputation: bool = False) -> Dict[str, Any]:
        """
        Process traceroute results and enrich with geographic data.
        
        Args:
            tracer: Traceroute instance
            include_reputation: Whether to include reputation score
            
        Returns:
            dict: Processed traceroute results with geographic data
        """
        print(f"Processing traceroute: {tracer.target}")
        
        # In test mode, collect hops from run_stream() instead of run()
        if self.test_mode:
            hops = []
            async for hop in tracer.run_stream():
                hops.append(hop)
        else:
            hops = await tracer.run()
            
        print(f"Retrieved {len(hops)} hops")
        
        # Process individual hops
        processed_hops = []
        for hop in hops:
            print(f"Processing hop {hop.hop_number}: {hop.ip}")
            enriched = await self._enrich_hop_data(hop, include_reputation)
            processed_hops.append(enriched)
            
        # Count successful hops (those with valid IPs)
        successful_hops = sum(1 for hop in hops if hop.ip is not None)
        
        result = {
            "target": tracer.target,
            "hops": processed_hops,
            "total_hops": len(hops),
            "successful_hops": successful_hops
        }
        
        print(f"Processing complete: {result}")
        return result

    async def process_traceroute_stream_with_ip_info(self, target: str, max_hops: int = 30) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Process traceroute results and enrich with IP information in real-time.
        
        Args:
            target: Target hostname or IP address
            max_hops: Maximum number of hops
            
        Yields:
            Dict containing enriched hop data
        """
        # Run traceroute
        traceroute = Traceroute(target, max_hops=max_hops)
        async for hop in traceroute.run_stream():
            if hop.ip:
                # Skip local IP addresses
                if hop.ip.startswith(('192.168.', '10.', '172.16.')):
                    enriched_hop = {
                        'hop_number': hop.hop_number,
                        'ip_address': hop.ip,
                        'hostname': hop.hostname,
                        'rtt_ms': hop.rtt_ms,
                        'country': None,
                        'city': None,
                        'latitude': None,
                        'longitude': None,
                        'organization': 'Local Network',
                        'reputation_score': 0.5
                    }
                else:
                    try:
                        # Use asynchronous method
                        ip_info = await self.ip_info_service.get_ip_info(hop.ip)
                        enriched_hop = {
                            'hop_number': hop.hop_number,
                            'ip_address': hop.ip,
                            'hostname': hop.hostname,
                            'rtt_ms': hop.rtt_ms,
                            'country': ip_info.country,
                            'city': ip_info.city,
                            'latitude': ip_info.latitude,
                            'longitude': ip_info.longitude,
                            'organization': ip_info.org,
                            'reputation_score': ip_info.reputation_score
                        }
                    except Exception as e:
                        print(f"Failed to get IP information for {hop.ip}: {str(e)}")
                        enriched_hop = {
                            'hop_number': hop.hop_number,
                            'ip_address': hop.ip,
                            'hostname': hop.hostname,
                            'rtt_ms': hop.rtt_ms,
                            'country': None,
                            'city': None,
                            'latitude': None,
                            'longitude': None,
                            'organization': None,
                            'reputation_score': None
                        }
            else:
                enriched_hop = {
                    'hop_number': hop.hop_number,
                    'ip_address': None,
                    'hostname': None,
                    'rtt_ms': hop.rtt_ms,
                    'country': None,
                    'city': None,
                    'latitude': None,
                    'longitude': None,
                    'organization': None,
                    'reputation_score': None
                }
            
            yield enriched_hop
            # Add small delay to avoid refreshing too quickly
            await asyncio.sleep(0.1)

    async def process_traceroute_with_ip_info(self, target: str, max_hops: int = 30) -> Dict[str, Any]:
        """
        Process traceroute results and enrich with IP information.
        
        Args:
            target: Target hostname or IP address
            max_hops: Maximum number of hops
            
        Returns:
            Dict containing enriched traceroute data
        """
        hops = []
        async for hop in self.process_traceroute_stream_with_ip_info(target, max_hops):
            hops.append(hop)
        
        return {
            'target': target,
            'hops': hops,
            'total_hops': len(hops),
            'successful_hops': len([h for h in hops if h['ip_address']])
        }

    def __del__(self):
        """Cleanup database readers when object is destroyed."""
        try:
            if self.city_reader:
                self.city_reader.close()
            if self.asn_reader:
                self.asn_reader.close()
        except:
            pass 