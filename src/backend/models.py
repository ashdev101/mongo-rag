"""Pydantic models for request/response validation."""
from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, Dict, Any


class Message(BaseModel):
    """Message request model."""
    text: str
    sender: Optional[str] = "user"

class SharePointMessage(BaseModel):
    """Message request model for Sharepoint."""
    text: str

class TestSharePointMessage(BaseModel):
    """Message request model for Sharepoint."""
    text: str
    email: EmailStr

    @field_validator("email")
    @classmethod
    def validate_email_length(cls, v: str) -> str:
        if len(v) < 5 or len(v) > 254:
            raise ValueError("email must be between 5 and 254 characters")
        return v


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
