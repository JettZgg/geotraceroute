import pytest
from unittest.mock import patch, MagicMock
from geotraceroute.core.traceroute import Traceroute, Hop
from geotraceroute.core.ip_info import IPInfo

# Test data
TEST_TARGET = "example.com"
TEST_IP = "8.8.8.8"
TEST_HOPS = [
    Hop(1, "192.168.1.1", None, [1.0]),
    Hop(2, TEST_IP, None, [2.0, 2.1])
]

# Test IP information
TEST_IP_INFO = IPInfo(
    ip=TEST_IP,
    country="United States",
    city="Mountain View",
    latitude=37.4056,
    longitude=-122.0775,
    org="Google LLC",
    reputation_score=0.8
)

def async_generator(items):
    """Convert a list to an async generator"""
    async def gen():
        for item in items:
            yield item
    return gen()

@pytest.fixture
def mock_traceroute():
    """Create a mocked Traceroute instance"""
    with patch('geotraceroute.core.traceroute.Traceroute') as mock:
        tracer = mock.return_value
        tracer.run_stream.return_value = async_generator(TEST_HOPS)
        yield tracer

@pytest.fixture
def mock_data_processor():
    """Create a mocked DataProcessor instance"""
    with patch('geotraceroute.core.data_processor.DataProcessor') as mock:
        processor = mock.return_value
        processor.process_traceroute_stream.return_value = async_generator([
            {
                "hop_number": 1,
                "ip": "192.168.1.1",
                "rtt_ms": [1.0]
            },
            {
                "hop_number": 2,
                "ip": TEST_IP,
                "rtt_ms": [2.0, 2.1],
                "country": "United States",
                "city": "Mountain View",
                "latitude": 37.4056,
                "longitude": -122.0775,
                "organization": "Google LLC",
                "asn": 15169,
                "reputation_score": 0.8
            }
        ])
        yield processor

@pytest.fixture
def mock_ip_info():
    """Create a mocked IPInfoService"""
    with patch('geotraceroute.core.ip_info.IPInfoService.get_ip_info') as mock:
        mock.return_value = TEST_IP_INFO
        yield mock 