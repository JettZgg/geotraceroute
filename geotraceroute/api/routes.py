from fastapi import APIRouter, HTTPException, Request, Query, Depends
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
import json
import logging
from geotraceroute.core.data_processor import DataProcessor
from geotraceroute.core.traceroute import Traceroute
from geotraceroute.core.ip_info import IPInfoService
from geotraceroute.api.models import TracerouteRequest, ClientLocation
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "web" / "templates"))

# Create DataProcessor instance
data_processor = DataProcessor(test_mode='PYTEST_CURRENT_TEST' in os.environ)
current_traceroute = None
ip_info_service = IPInfoService()

# Get client location information
async def get_client_location(request: Request, 
                             client_lat: float = Query(None, description="Client latitude"),
                             client_lon: float = Query(None, description="Client longitude"),
                             client_city: str = Query(None, description="Client city"),
                             client_country: str = Query(None, description="Client country")):
    """Get client location information, prioritizing query parameters, then attempt to determine based on client IP"""
    if client_lat and client_lon:
        logger.info(f"Using client-provided location info: lat={client_lat}, lon={client_lon}")
        return {
            "latitude": client_lat,
            "longitude": client_lon,
            "city": client_city,
            "country": client_country
        }
    
    # Try to determine location based on client IP
    try:
        client_ip = request.client.host
        # Skip if local testing
        if client_ip in ('127.0.0.1', 'localhost', '::1'):
            return None
        
        logger.info(f"Attempting to determine client IP location: {client_ip}")
        ip_info = await ip_info_service.get_ip_info(client_ip)
        
        if ip_info and ip_info.latitude and ip_info.longitude:
            logger.info(f"Successfully determined client location: {ip_info.city}, {ip_info.country}")
            return {
                "latitude": ip_info.latitude,
                "longitude": ip_info.longitude,
                "city": ip_info.city,
                "country": ip_info.country
            }
    except Exception as e:
        logger.error(f"Failed to determine client location: {str(e)}")
    
    return None

async def traceroute_generator(target: str, max_hops: int, include_reputation: bool = False, api_key: str = None, client_location: dict = None):
    """Generate traceroute results in real-time."""
    tracer = None
    try:
        # Log start information for debugging
        logger.info(f"Starting traceroute to {target} with max_hops={max_hops}, include_reputation={include_reputation}")
        
        tracer = Traceroute(target, max_hops=max_hops)
        global current_traceroute
        current_traceroute = tracer
        
        # Set API key if provided
        if api_key:
            ip_info_service.api_key = api_key
            logger.info("Using provided API key")
        
        if client_location:
            logger.info(f"Using client location information: {client_location}")
        
        hop_count = 0
        async for hop in data_processor.process_traceroute_stream(tracer, include_reputation=include_reputation):
            # Use client location information for the first hop
            if hop['hop_number'] == 1 and client_location:
                hop.update({
                    "city": client_location.get('city'),
                    "country": client_location.get('country'),
                    "latitude": client_location.get('latitude'),
                    "longitude": client_location.get('longitude')
                })
            
            hop_count += 1
            logger.info(f"Yielding hop #{hop_count}: {hop.get('ip', '*')}")
            # Add 'hop' field to match test expectations
            hop_data = hop.copy()
            hop_data['hop'] = hop_data['hop_number']
            hop_data['rtt'] = hop_data['rtt_ms'][0] if hop_data['rtt_ms'] and len(hop_data['rtt_ms']) > 0 else 0
            yield f"data: {json.dumps(hop_data)}\n\n"
            
        # Log completion message
        logger.info(f"Traceroute to {target} completed with {hop_count} hops")
        
        # Send completion message
        yield f"data: {json.dumps({'status': 'completed'})}\n\n"
    except Exception as e:
        logger.error(f"Error in traceroute: {str(e)}")
        error_data = {"error": str(e)}
        yield f"data: {json.dumps(error_data)}\n\n"
    finally:
        if tracer:
            logger.info(f"Stopping traceroute to {target}")
            await tracer.stop()
            if current_traceroute == tracer:
                current_traceroute = None
        # Send final completion message
        yield "data: {\"done\": true}\n\n"

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

@router.get("/traceroute/{target}")
async def traceroute_stream(
    request: Request,
    target: str, 
    max_hops: int = 30, 
    include_reputation: bool = True,
    api_key: str = Query(None, description="IPInfo API key"),
    client_location: dict = Depends(get_client_location)
):
    """
    Stream traceroute results for a target.
    
    Args:
        target: The hostname or IP to traceroute to
        max_hops: Maximum number of hops
        include_reputation: Whether to include reputation scores
        api_key: IPInfo API key for geolocation and reputation data
        client_location: Client location information
        
    Returns:
        StreamingResponse: Server-sent events stream of hop data
    """
    return StreamingResponse(
        traceroute_generator(target, max_hops, include_reputation, api_key, client_location),
        media_type="text/event-stream"
    )

@router.post("/traceroute/stop")
async def stop_traceroute():
    """Stop the current traceroute process"""
    global current_traceroute
    try:
        if current_traceroute:
            await current_traceroute.stop()
            current_traceroute = None
        return {"status": "stopped"}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

@router.post("/traceroute/start")
async def start_traceroute(
    request: Request,
    req: TracerouteRequest,
    api_key: str = Query(None, description="IPInfo API key"),
    client_location: dict = Depends(get_client_location)
):
    """Start traceroute and return streaming response"""
    try:
        return StreamingResponse(
            traceroute_generator(
                req.target,
                req.max_hops,
                req.include_reputation,
                api_key,
                client_location
            ),
            media_type="text/event-stream"
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

@router.post("/traceroute")
async def run_traceroute(
    request: Request,
    req: TracerouteRequest,
    api_key: str = Query(None, description="IPInfo API key"),
    client_location: dict = Depends(get_client_location)
):
    """Run complete traceroute and return results."""
    tracer = None
    try:
        logger.info(f"Running traceroute to {req.target}")
        tracer = Traceroute(req.target, max_hops=req.max_hops)
        
        # Set API key if provided
        if api_key:
            ip_info_service.api_key = api_key
            
        # Get location information and pass to processor
        result = await data_processor.process_traceroute(
            tracer,
            include_reputation=req.include_reputation
        )
        
        # If client location information is available, apply to first hop
        if client_location and result['hops'] and len(result['hops']) > 0:
            first_hop = result['hops'][0]
            first_hop.update({
                "city": client_location.get('city'),
                "country": client_location.get('country'),
                "latitude": client_location.get('latitude'),
                "longitude": client_location.get('longitude')
            })
            
        return result
    except Exception as e:
        logger.error(f"Error in traceroute: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if tracer:
            await tracer.stop()

@router.get("/traceroute/{target}/summary")
async def traceroute_summary(
    request: Request,
    target: str, 
    max_hops: int = 30, 
    include_reputation: bool = False,
    api_key: str = Query(None, description="IPInfo API key"),
    client_location: dict = Depends(get_client_location)
):
    """
    Get complete traceroute results for a target.
    
    Args:
        target: The hostname or IP to traceroute to
        max_hops: Maximum number of hops
        include_reputation: Whether to include reputation scores
        api_key: IPInfo API key for geolocation and reputation data
        client_location: Client location information
        
    Returns:
        dict: Summary of traceroute results
    """
    try:
        tracer = Traceroute(target, max_hops=max_hops)
        
        # Set API key if provided
        if api_key:
            ip_info_service.api_key = api_key
            
        result = await data_processor.process_traceroute(tracer, include_reputation=include_reputation)
        
        # If client location information is available, apply to first hop
        if client_location and result['hops'] and len(result['hops']) > 0:
            first_hop = result['hops'][0]
            first_hop.update({
                "city": client_location.get('city'),
                "country": client_location.get('country'),
                "latitude": client_location.get('latitude'),
                "longitude": client_location.get('longitude')
            })
            
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 