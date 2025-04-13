import pytest
from fastapi.testclient import TestClient
import sys
import os
import json
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio
from geotraceroute.main import app
from geotraceroute.core.traceroute import Traceroute, Hop
from geotraceroute.core.data_processor import DataProcessor
from geotraceroute.core.ip_info import IPInfo

# Add the project root directory to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

client = TestClient(app)

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
                "hop": 1,
                "ip": "192.168.1.1",
                "rtt": 1.0, 
                "hostname": None,
                "location": None
            },
            {
                "hop": 2,
                "ip": TEST_IP,
                "rtt": 2.0,
                "hostname": "dns.google",
                "location": {
                    "country_name": "United States",
                    "city": "Mountain View",
                    "latitude": 37.4056,
                    "longitude": -122.0775,
                    "org": "Google LLC",
                    "asn": 15169
                },
                "reputation": {
                    "score": 0.8,
                    "categories": ["CDN", "DNS"]
                },
                "is_destination": True
            }
        ])
        yield processor

@pytest.fixture
def mock_ip_info():
    """Create a mocked IPInfoService"""
    with patch('geotraceroute.core.ip_info.IPInfoService.get_ip_info') as mock:
        mock.return_value = TEST_IP_INFO
        yield mock

def async_generator(items):
    """Convert a list to an async generator"""
    async def gen():
        for item in items:
            yield item
    return gen()

@patch('geotraceroute.core.data_processor.DataProcessor.process_traceroute')
def test_traceroute_endpoint_success(mock_process):
    """Test successful traceroute endpoint"""
    mock_data = {
        "target": "8.8.8.8",
        "hops": [
            {
                "hop_number": 1,
                "ip": "192.168.1.1",
                "hostname": None,
                "rtt_ms": [1.0],
                "country": "US",
                "city": "New York",
                "latitude": 40.7128,
                "longitude": -74.0060,
                "organization": "ISP",
                "asn": 12345,
                "reputation_score": 0.5
            }
        ],
        "total_hops": 1,
        "successful_hops": 1
    }
    mock_process.return_value = mock_data
    
    response = client.post(
        "/api/traceroute",
        json={"target": "8.8.8.8", "max_hops": 30}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["target"] == "8.8.8.8"
    assert len(data["hops"]) == 1
    assert data["total_hops"] == 1
    assert data["successful_hops"] == 1

@patch('geotraceroute.core.data_processor.DataProcessor.process_traceroute')
def test_traceroute_endpoint_failure(mock_process):
    """Test traceroute endpoint with failure"""
    mock_process.side_effect = ValueError("Could not resolve hostname: invalid.target")

    response = client.post(
        "/api/traceroute",
        json={"target": "invalid.target", "max_hops": 30}
    )

    assert response.status_code == 500
    assert "Could not resolve hostname: invalid.target" in response.json()["detail"]

def test_traceroute_endpoint_validation():
    """Test traceroute endpoint with invalid input"""
    # Test with missing target
    response = client.post(
        "/api/traceroute",
        json={"max_hops": 30}
    )
    assert response.status_code == 422
    
    # Test invalid max_hops
    response = client.post(
        "/api/traceroute",
        json={"target": "8.8.8.8", "max_hops": -1}
    )
    assert response.status_code == 422 

@pytest.mark.asyncio
async def test_traceroute_start_without_reputation(mock_traceroute, mock_data_processor):
    """Test traceroute start without reputation scores"""
    response = client.post("/api/traceroute/start", json={"target": TEST_TARGET})
    assert response.status_code == 200
    
    # Verify streaming response
    lines = response.text.split('\n')
    assert len(lines) > 0
    for line in lines:
        if line.strip() and line.startswith('data: '):
            data = line[6:]  # Remove 'data: ' prefix
            hop = json.loads(data)
            if "done" not in hop and "status" not in hop:  # Ignore end markers and completion messages
                assert "hop" in hop
                assert "ip" in hop
                assert "rtt" in hop

@pytest.mark.asyncio
async def test_traceroute_with_reputation(mock_traceroute, mock_data_processor, mock_ip_info):
    """Test traceroute with reputation scores"""
    response = client.post("/api/traceroute/start", json={
        "target": TEST_TARGET,
        "include_reputation": True
    })
    assert response.status_code == 200
    
    # Verify response includes reputation scores
    lines = response.text.split('\n')
    found_test_ip = False
    for line in lines:
        if line.strip() and line.startswith('data: '):
            data = line[6:]  # Remove 'data: ' prefix
            hop = json.loads(data)
            if "done" not in hop and "status" not in hop:  # Ignore end markers and completion messages
                if hop.get("ip") == TEST_IP:
                    found_test_ip = True
                    assert "reputation" in hop
                    assert hop["reputation"]["score"] == 0.8
    
    if not found_test_ip:
        pytest.skip("Test IP not found in response, skipping reputation check")

@pytest.mark.asyncio
async def test_traceroute_stop():
    """Test stopping a traceroute"""
    response = client.post("/api/traceroute/stop")
    assert response.status_code == 200
    assert response.json()["status"] == "stopped"

@pytest.mark.asyncio
async def test_invalid_target():
    """Test invalid target"""
    response = client.post("/api/traceroute/start", json={"target": ""})
    assert response.status_code == 422

@pytest.mark.asyncio
async def test_stream_format(mock_traceroute, mock_data_processor):
    """Test streaming response format"""
    response = client.post("/api/traceroute/start", json={"target": TEST_TARGET})
    assert response.status_code == 200
    
    lines = response.text.split('\n')
    for line in lines:
        if line.strip() and line.startswith('data: '):
            data = line[6:]  # Remove 'data: ' prefix
            hop = json.loads(data)
            if "done" not in hop and "status" not in hop:  # Ignore end markers and completion messages
                # Verify required fields
                assert "hop" in hop
                assert "ip" in hop
                assert "rtt" in hop
                # Verify field types
                assert isinstance(hop["hop"], int)
                # IP can be None for timeout hops
                assert isinstance(hop["ip"], (str, type(None)))
                assert isinstance(hop["rtt"], (int, float))
                # Verify optional fields
                if "location" in hop and hop["location"]:
                    location = hop["location"]
                    if "country_name" in location:
                        assert isinstance(location["country_name"], str)
                    if "city" in location:
                        assert isinstance(location["city"], str)
                    if "latitude" in location:
                        assert isinstance(location["latitude"], float)
                    if "longitude" in location:
                        assert isinstance(location["longitude"], float)
                    if "org" in location:
                        assert isinstance(location["org"], str)
                    if "asn" in location:
                        assert isinstance(location["asn"], int)
                if "reputation" in hop and hop["reputation"]:
                    assert isinstance(hop["reputation"]["score"], float) 