import pytest
from unittest.mock import patch, MagicMock, PropertyMock
import os
import sys
import asyncio
from geotraceroute.core.data_processor import DataProcessor
from geotraceroute.core.traceroute import Traceroute, Hop
from geotraceroute.core.ip_info import IPInfoService, IPInfo
import ipaddress

# Add the project root directory to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

@pytest.fixture
def data_processor():
    """创建DataProcessor实例"""
    return DataProcessor(test_mode=True)

@pytest.fixture
def mock_geoip():
    """创建模拟的GeoIP数据库"""
    with patch('geotraceroute.core.data_processor.geoip2.database.Reader') as mock:
        reader = mock.return_value
        # mock city database response
        city_response = MagicMock()
        city_response.city.name = "Mountain View"
        city_response.country.name = "United States"
        city_response.location.latitude = 37.4056
        city_response.location.longitude = -122.0775
        reader.city.return_value = city_response
        
        # mock ASN database response
        asn_response = MagicMock()
        asn_response.autonomous_system_organization = "Google LLC"
        asn_response.autonomous_system_number = 15169
        reader.asn.return_value = asn_response
        
        yield reader

@pytest.fixture
def mock_ip_info():
    """创建模拟的IPInfo服务"""
    with patch('geotraceroute.core.ip_info.IPInfoService.get_ip_info') as mock:
        ip_info = IPInfo(
            ip="8.8.8.8",
            country="United States",
            city="Mountain View",
            latitude=37.4056,
            longitude=-122.0775,
            org="Google LLC",
            reputation_score=0.8
        )
        mock.return_value = ip_info
        yield mock

@pytest.mark.asyncio
async def test_process_traceroute_success(data_processor, mock_geoip, mock_ip_info):
    """测试成功的traceroute处理"""
    # create test data
    hops = [
        Hop(1, "192.168.1.1", None, [1.0]),
        Hop(2, "8.8.8.8", None, [2.0, 2.1])
    ]
    
    tracer = Traceroute("example.com")
    
    async def mock_run_stream():
        for hop in hops:
            yield hop
    
    with patch.object(tracer, 'run_stream', side_effect=mock_run_stream):
        result = await data_processor.process_traceroute(tracer, include_reputation=True)
        
        assert result["target"] == "example.com"
        assert len(result["hops"]) == 2
        assert result["total_hops"] == 2
        assert result["successful_hops"] == 2
        
        # check the first hop
        assert result["hops"][0]["hop_number"] == 1
        assert result["hops"][0]["ip"] == "192.168.1.1"
        assert result["hops"][0]["rtt_ms"] == [1.0]
        
        # check the second hop
        assert result["hops"][1]["hop_number"] == 2
        assert result["hops"][1]["ip"] == "8.8.8.8"
        assert result["hops"][1]["rtt_ms"] == [2.0, 2.1]
        assert result["hops"][1]["country"] == "United States"
        assert result["hops"][1]["city"] == "Mountain View"
        assert result["hops"][1]["latitude"] == 37.4056
        assert result["hops"][1]["longitude"] == -122.0775
        assert result["hops"][1]["organization"] == "Google LLC"
        assert result["hops"][1]["asn"] == 15169
        assert result["hops"][1]["reputation_score"] == 0.8

@pytest.mark.asyncio
async def test_process_traceroute_with_timeout(data_processor, mock_geoip):
    """测试包含超时的traceroute处理"""
    hops = [
        Hop(1, "192.168.1.1", None, [1.0]),
        Hop(2, None, None, None),  # timeout hop
        Hop(3, "8.8.8.8", None, [3.0])
    ]
    
    tracer = Traceroute("example.com")
    
    async def mock_run_stream():
        for hop in hops:
            yield hop
    
    with patch.object(tracer, 'run_stream', side_effect=mock_run_stream):
        result = await data_processor.process_traceroute(tracer)
        
        assert result["target"] == "example.com"
        assert len(result["hops"]) == 3
        assert result["total_hops"] == 3
        assert result["successful_hops"] == 2
        
        # check timeout hop
        assert result["hops"][1]["ip"] is None
        assert result["hops"][1]["rtt_ms"] is None

@pytest.mark.asyncio
async def test_enrich_hop_data_basic(data_processor, mock_geoip):
    """测试基本的跳转点数据丰富"""
    # Use hop_number=2 to avoid first-hop special handling
    hop = Hop(2, "8.8.8.8", None, [1.0])
    # Patch ipaddress.ip_address.is_private to return False
    with patch('ipaddress.IPv4Address.is_private', new_callable=PropertyMock, return_value=False):
        with patch('ipaddress.IPv6Address.is_private', new_callable=PropertyMock, return_value=False):
            enriched = await data_processor._enrich_hop_data(hop)
    
    assert enriched["hop_number"] == 2
    assert enriched["ip"] == "8.8.8.8"
    assert enriched["rtt_ms"] == [1.0]
    assert enriched["country"] == "United States"
    assert enriched["city"] == "Mountain View"
    assert enriched["latitude"] == 37.4056
    assert enriched["longitude"] == -122.0775
    assert enriched["organization"] == "Google LLC"
    assert enriched["asn"] == 15169

@pytest.mark.asyncio
async def test_enrich_hop_data_with_reputation(data_processor, mock_geoip, mock_ip_info):
    """测试带信誉评分的跳转点数据丰富"""
    hop = Hop(1, "8.8.8.8", None, [1.0])
    # Patch ipaddress.ip_address.is_private to return False
    with patch('ipaddress.IPv4Address.is_private', new_callable=PropertyMock, return_value=False):
        with patch('ipaddress.IPv6Address.is_private', new_callable=PropertyMock, return_value=False):
            # Set hop_number to 2 to avoid first-hop detection
            hop.hop_number = 2
            enriched = await data_processor._enrich_hop_data(hop, include_reputation=True)
    
    assert enriched["reputation_score"] == 0.8

@pytest.mark.asyncio
async def test_enrich_hop_data_invalid_ip(data_processor):
    """测试无效IP的跳转点数据丰富"""
    hop = Hop(1, "invalid.ip", None, [1.0])
    enriched = await data_processor._enrich_hop_data(hop)
    
    assert enriched["ip"] == "invalid.ip"
    assert enriched["country"] is None
    assert enriched["city"] is None
    assert enriched["latitude"] is None
    assert enriched["longitude"] is None
    assert enriched["organization"] is None
    assert enriched["asn"] is None
    assert enriched["reputation_score"] is None

@pytest.mark.asyncio
async def test_process_traceroute_stream(data_processor, mock_geoip, mock_ip_info):
    """测试流式处理traceroute结果"""
    hops = [
        Hop(1, "192.168.1.1", None, [1.0]),
        Hop(2, "8.8.8.8", None, [2.0, 2.1])
    ]
    
    tracer = Traceroute("example.com")
    
    async def mock_run_stream():
        for hop in hops:
            yield hop
    
    with patch.object(tracer, 'run_stream', side_effect=mock_run_stream):
        results = []
        async for hop in data_processor.process_traceroute_stream(tracer, include_reputation=True):
            results.append(hop)
        
        assert len(results) == 2
        assert results[0]["ip"] == "192.168.1.1"
        assert results[1]["ip"] == "8.8.8.8"
        assert results[1]["reputation_score"] == 0.8

@pytest.mark.asyncio
async def test_process_traceroute_complete(data_processor, mock_geoip, mock_ip_info):
    """测试完整的traceroute处理流程"""
    hops = [
        Hop(1, "192.168.1.1", None, [1.0]),
        Hop(2, "8.8.8.8", None, [2.0, 2.1])
    ]
    
    tracer = Traceroute("example.com")
    
    async def mock_run_stream():
        for hop in hops:
            yield hop
    
    with patch.object(tracer, 'run_stream', side_effect=mock_run_stream):
        result = await data_processor.process_traceroute(tracer, include_reputation=True)
        
        assert result["target"] == "example.com"
        assert len(result["hops"]) == 2
        assert result["total_hops"] == 2
        assert result["successful_hops"] == 2
        
        # verify all hops are processed correctly
        for hop in result["hops"]:
            assert "hop_number" in hop
            assert "ip" in hop
            assert "rtt_ms" in hop
            if hop["ip"] == "8.8.8.8":
                assert hop["reputation_score"] == 0.8

@pytest.mark.asyncio
async def test_geoip_database_availability():
    """测试GeoIP数据库可用性"""
    # ensure database files exist
    base_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
    assert os.path.exists(os.path.join(base_path, 'GeoLite2-City.mmdb'))
    assert os.path.exists(os.path.join(base_path, 'GeoLite2-ASN.mmdb')) 