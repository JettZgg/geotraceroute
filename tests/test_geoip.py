import pytest
from unittest.mock import patch, MagicMock
import asyncio
import sys
import os

# Add project root directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from geotraceroute.core.traceroute import Traceroute, Hop
from geotraceroute.core.data_processor import DataProcessor

@pytest.mark.asyncio
async def test_geoip_databases():
    """Test both GeoIP databases with a known IP"""
    processor = DataProcessor(test_mode=True)
    
    # Use Google DNS as test target, allowing more hops
    tracer = Traceroute("8.8.8.8", max_hops=5)
    
    # mock hop data
    hops = [
        Hop(1, "192.168.1.1", None, [1.0]),
        Hop(2, "8.8.8.8", None, [2.0, 2.1])
    ]
    
    async def mock_run_stream():
        for hop in hops:
            yield hop
    
    with patch.object(tracer, 'run_stream', side_effect=mock_run_stream):
        result = await processor.process_traceroute(tracer)
        
        # verify basic data structure
        assert "target" in result
        assert "hops" in result
        assert len(result["hops"]) > 0
        
        # find the first valid hop
        valid_hop = None
        for hop in result["hops"]:
            if hop['ip'] and not hop['ip'].startswith('*'):
                valid_hop = hop
                break
        
        assert valid_hop is not None, "Should have at least one valid hop"
        
        # print detailed information for inspection
        print("\nGeoIP Test Results:")
        print(f"IP: {valid_hop['ip']}")
        print(f"Hostname: {valid_hop['hostname']}")
        print(f"City: {valid_hop['city']}")
        print(f"Country: {valid_hop['country']}")
        print(f"Coordinates: ({valid_hop['latitude']}, {valid_hop['longitude']})")
        print(f"Organization: {valid_hop['organization']}")
        print(f"ASN: {valid_hop['asn']}")

@pytest.mark.asyncio
async def test_reputation_score():
    """Test reputation score functionality"""
    processor = DataProcessor(test_mode=True)
    
    # Use Google DNS as test target, allowing more hops
    tracer = Traceroute("8.8.8.8", max_hops=5)
    
    # mock hop data
    hops = [
        Hop(1, "192.168.1.1", None, [1.0]),
        Hop(2, "8.8.8.8", None, [2.0, 2.1])
    ]
    
    async def mock_run_stream():
        for hop in hops:
            yield hop
    
    with patch.object(tracer, 'run_stream', side_effect=mock_run_stream):
        # test without reputation score
        result = await processor.process_traceroute(tracer, include_reputation=False)
        
        # find the first valid hop
        valid_hop = None
        for hop in result["hops"]:
            if hop['ip'] and not hop['ip'].startswith('*'):
                valid_hop = hop
                break
        
        assert valid_hop is not None, "Should have at least one valid hop"
        assert valid_hop["reputation_score"] is None, "Reputation score should be None when not requested"
        
        # test with reputation score
        result = await processor.process_traceroute(tracer, include_reputation=True)
        
        # find the first valid hop
        valid_hop = None
        for hop in result["hops"]:
            if hop['ip'] and not hop['ip'].startswith('*'):
                valid_hop = hop
                break
        
        assert valid_hop is not None, "Should have at least one valid hop"
        print(f"\nReputation Score: {valid_hop['reputation_score']}")
        
        # reputation score might be None (if API call fails), or a float
        if valid_hop["reputation_score"] is not None:
            assert isinstance(valid_hop["reputation_score"], float), "Reputation score should be a float"
            assert 0 <= valid_hop["reputation_score"] <= 1, "Reputation score should be between 0 and 1"

@pytest.mark.asyncio
async def test_multiple_hops():
    """Test GeoIP data for multiple hops"""
    processor = DataProcessor(test_mode=True)
    
    # Use a more distant target to get multiple hops
    tracer = Traceroute("www.google.com", max_hops=5)
    
    # mock hop data
    hops = [
        Hop(1, "192.168.1.1", None, [1.0]),
        Hop(2, "8.8.8.8", None, [2.0, 2.1]),
        Hop(3, "8.8.4.4", None, [3.0, 3.1])
    ]
    
    async def mock_run_stream():
        for hop in hops:
            yield hop
    
    with patch.object(tracer, 'run_stream', side_effect=mock_run_stream):
        result = await processor.process_traceroute(tracer)
        
        print("\nMultiple Hops Test:")
        for hop in result["hops"]:
            if hop['ip'] and not hop['ip'].startswith('*'):
                print(f"\nHop {hop['hop_number']}:")
                print(f"IP: {hop['ip']}")
                print(f"Location: {hop['city']}, {hop['country']}")
                print(f"Organization: {hop['organization']} (ASN: {hop['asn']})")
                
                # verify data for each valid hop
                assert hop['city'] is not None or hop['country'] is not None, "Should have some location data"
                assert hop['organization'] is not None, "Should have organization data"
                if hop['asn'] is not None:
                    assert isinstance(hop['asn'], int), "Should have valid ASN" 