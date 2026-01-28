"""Pydantic models for request/response validation."""
from pydantic import BaseModel
from typing import Optional, Dict, Any


class Message(BaseModel):
    """Message request model."""
    text: str
    sender: Optional[str] = "user"

class SharePointMessage(BaseModel):
    """Message request model for Sharepoint."""
    text: str
    # email: str

class TestSharePointMessage(BaseModel):
    """Message request model for Sharepoint."""
    text: str
    email: str


class MessageResponse(BaseModel):
    """Message response model."""
    id: int
    text: str
    sender: str
    timestamp: str
    user: Optional[str] = None


class ChatResponse(BaseModel):
    """Chat response model."""
    success: bool
    message: str
    user_info: Optional[dict] = None


class CombinedResponse(BaseModel):
    """Combined execute response model."""
    router_output: Dict[str, Any]
    final_output: str


class TokenValidationResponse(BaseModel):
    """Token validation response model."""
    valid: bool
    user: Optional[dict] = None
    error: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str
    timestamp: str
