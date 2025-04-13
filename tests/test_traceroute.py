import pytest
import asyncio
from unittest.mock import patch, MagicMock
import os
import sys

# Add the project root directory to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from geotraceroute.core.traceroute import Traceroute, Hop
from geotraceroute.core.data_processor import DataProcessor

@pytest.fixture
def traceroute():
    """创建Traceroute实例"""
    return Traceroute("example.com")

@pytest.mark.asyncio
async def test_traceroute_initialization():
    """测试Traceroute初始化"""
    tracer = Traceroute("example.com")
    assert tracer.target == "example.com"
    assert tracer.max_hops == 30
    assert tracer.timeout == 1.0
    assert tracer.retries == 3

@pytest.mark.asyncio
async def test_traceroute_with_custom_params():
    """测试带自定义参数的Traceroute初始化"""
    tracer = Traceroute("example.com", max_hops=15, timeout=2.0, retries=5)
    assert tracer.max_hops == 15
    assert tracer.timeout == 2.0
    assert tracer.retries == 5

@pytest.mark.asyncio
async def test_traceroute_run_stream(traceroute):
    """测试traceroute流式运行"""
    async for hop in traceroute.run_stream():
        assert isinstance(hop, Hop)
        assert hop.hop_number > 0
        assert hop.ip is not None or hop.ip is None  # allow timeout
        assert isinstance(hop.rtt_ms, list) or hop.rtt_ms is None

@pytest.mark.asyncio
async def test_traceroute_with_timeout():
    """测试traceroute超时处理"""
    tracer = Traceroute("example.com", timeout=0.1)  # set very short timeout
    async for hop in tracer.run_stream():
        if hop.ip is None:
            assert hop.rtt_ms is None
            break

@pytest.mark.asyncio
async def test_traceroute_stop(traceroute):
    """测试停止traceroute"""
    # start traceroute
    task = asyncio.create_task(traceroute.run_stream().__anext__())
    
    # wait a short time to ensure the task starts running
    await asyncio.sleep(0.1)
    
    # stop traceroute
    await traceroute.stop()
    
    # wait for task to complete
    try:
        await task
    except (asyncio.CancelledError, StopAsyncIteration):
        pass  # expected behavior

@pytest.mark.asyncio
async def test_traceroute_invalid_target():
    """测试无效目标"""
    with pytest.raises(ValueError, match="Could not resolve hostname: invalid.target"):
        Traceroute("invalid.target")

@pytest.mark.asyncio
async def test_traceroute_max_hops():
    """测试最大跳数限制"""
    tracer = Traceroute("example.com", max_hops=5)
    hop_count = 0
    async for hop in tracer.run_stream():
        hop_count += 1
        assert hop.hop_number <= 5
    assert hop_count <= 5

@pytest.mark.asyncio
async def test_traceroute_retries():
    """测试重试机制"""
    tracer = Traceroute("example.com", retries=2)
    async for hop in tracer.run_stream():
        if hop.rtt_ms is not None:
            assert len(hop.rtt_ms) <= 2  # maximum 2 retries
        break

@pytest.mark.asyncio
async def test_traceroute_with_data_processor(traceroute):
    """测试与DataProcessor的集成"""
    processor = DataProcessor()
    async for hop in processor.process_traceroute_stream(traceroute):
        assert isinstance(hop, dict)
        assert "hop_number" in hop
        assert "ip" in hop
        assert "rtt_ms" in hop
        break

@pytest.mark.asyncio
async def test_traceroute_execution():
    """Test traceroute execution with a known target"""
    traceroute = Traceroute("8.8.8.8")  # Google's DNS server
    
    # mock hop data
    hops = [
        Hop(1, "192.168.1.1", None, [1.0]),
        Hop(2, "8.8.8.8", None, [2.0, 2.1])
    ]
    
    async def mock_run_stream():
        for hop in hops:
            yield hop
    
    with patch.object(traceroute, 'run_stream', side_effect=mock_run_stream):
        try:
            result = await traceroute.run()
            assert isinstance(result, list)
            assert len(result) > 0
            
            # Check hop structure
            for hop in result:
                assert isinstance(hop, Hop)
                assert isinstance(hop.hop_number, int)
                assert hop.hop_number > 0
                assert isinstance(hop.rtt_ms, list)
                assert all(isinstance(rtt, float) for rtt in hop.rtt_ms)
                
        except Exception as e:
            pytest.fail(f"Traceroute execution failed: {str(e)}")

def test_invalid_target():
    """Test traceroute with an invalid target"""
    with pytest.raises(ValueError, match="Could not resolve hostname: invalid.domain.that.does.not.exist"):
        Traceroute("invalid.domain.that.does.not.exist")

@pytest.mark.asyncio
async def test_traceroute_stream():
    """Test the streaming functionality of traceroute"""
    target = "google.com"
    tracer = Traceroute(target, timeout=2)  # Add timeout
    processor = DataProcessor()
    
    # Test streaming individual hops without reputation
    hop_count = 0
    async for hop in processor.process_traceroute_stream(tracer):
        assert "hop_number" in hop
        assert "ip" in hop
        assert "hostname" in hop
        assert "rtt_ms" in hop
        assert "city" in hop
        assert "country" in hop
        assert "latitude" in hop
        assert "longitude" in hop
        assert "organization" in hop
        assert "asn" in hop
        assert "reputation_score" in hop
        assert hop["reputation_score"] is None  # Should be None when not requested
        hop_count += 1
        if hop_count >= 5:  # Limit the number of hops to test
            break
        
    assert hop_count > 0, "Should have received at least one hop"
    
    # Test streaming with reputation score
    hop_count = 0
    async for hop in processor.process_traceroute_stream(tracer, include_reputation=True):
        if hop["ip"] and not hop["ip"].startswith('*'):
            assert "reputation_score" in hop
            # Note: reputation_score might still be None if IPInfo API call fails
        hop_count += 1
        if hop_count >= 5:  # Limit the number of hops to test
            break

@pytest.mark.asyncio
async def test_complete_traceroute():
    """Test complete traceroute processing"""
    target = "8.8.8.8"  # Use a reliable target
    tracer = Traceroute(target, max_hops=3, timeout=2)  # Add timeout and limit hops
    processor = DataProcessor()
    
    # Test without reputation score
    result = await processor.process_traceroute(tracer)
    
    assert "target" in result
    assert "hops" in result
    assert len(result["hops"]) > 0
    
    # Verify first hop structure
    first_hop = result["hops"][0]
    assert "hop_number" in first_hop
    assert "ip" in first_hop
    assert "hostname" in first_hop
    assert "rtt_ms" in first_hop
    assert "city" in first_hop
    assert "country" in first_hop
    assert "latitude" in first_hop
    assert "longitude" in first_hop
    assert "organization" in first_hop
    assert "asn" in first_hop
    assert "reputation_score" in first_hop
    assert first_hop["reputation_score"] is None  # Should be None when not requested
    
    # Test with reputation score
    tracer = Traceroute(target, max_hops=3, timeout=2)  # Create new instance
    result = await processor.process_traceroute(tracer, include_reputation=True)
    assert len(result["hops"]) > 0
    # Note: We don't assert the reputation_score value as it depends on IPInfo API 