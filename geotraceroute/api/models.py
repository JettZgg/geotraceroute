from pydantic import BaseModel, Field
from typing import Optional, List

class TracerouteRequest(BaseModel):
    target: str = Field(..., min_length=1, description="Target hostname or IP address")
    max_hops: Optional[int] = Field(
        default=30,
        ge=1,
        le=64,
        description="Maximum number of hops (1-64)"
    )
    include_reputation: Optional[bool] = False

class ClientLocation(BaseModel):
    latitude: float = Field(..., description="客户端纬度")
    longitude: float = Field(..., description="客户端经度")
    city: Optional[str] = Field(None, description="客户端城市")
    country: Optional[str] = Field(None, description="客户端国家")

class HopInfo(BaseModel):
    hop_number: int
    ip: Optional[str]
    hostname: Optional[str]
    rtt_ms: List[float]
    country: Optional[str]
    city: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    organization: Optional[str]
    asn: Optional[int]
    reputation_score: Optional[float]

class TracerouteResponse(BaseModel):
    target: str
    hops: List[HopInfo]
    total_hops: int
    successful_hops: int 