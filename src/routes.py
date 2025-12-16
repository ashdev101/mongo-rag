"""API route handlers."""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from typing import Dict, Any
from datetime import datetime
import logging
import json

from models import Message, TokenValidationResponse, HealthResponse, CombinedResponse
from auth import verify_token, extract_user_info
from app import combined_execute

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat()
    }


@router.get("/api/me")
async def get_current_user(token_data: Dict[str, Any] = Depends(verify_token)):
    """
    Get current authenticated user information.
    Returns user details extracted from the validated JWT token.
    """
    try:
        user_info = extract_user_info(token_data)
        
        # Add additional token claims if available
        return {
            "user": user_info,
            "claims": {
                "oid": token_data.get("oid"),
                "tid": token_data.get("tid"),
                "iss": token_data.get("iss"),
                "aud": token_data.get("aud"),
                "scp": token_data.get("scp"),
                "roles": token_data.get("roles", []),
            }
        }
    except Exception as e:
        logger.exception("Error retrieving user information")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve user information: {str(e)}"
        )


@router.post("/api/validate-token", response_model=TokenValidationResponse)
async def validate_token(token_data: Dict[str, Any] = Depends(verify_token)):
    """
    Validate if the provided token is valid.
    Token is validated via dependency.
    """
    try:
        user_info = extract_user_info(token_data)
        return {
            "valid": True,
            "user": user_info
        }
    except Exception as e:
        return {
            "valid": False,
            "error": str(e)
        }


@router.post("/api/messages", response_model=CombinedResponse)
async def send_message(
    user_message: Message,
    token_data: Dict[str, Any] = Depends(verify_token)
):
    """
    Receive a message from authenticated user and return response.
    This endpoint calls combined_execute from app.py as the entry point.
    Token is validated via dependency.
    """
    try:
        user_info = extract_user_info(token_data)
        email = user_info.get("email") or user_info.get("upn") or user_info.get("preferred_username", "")
        
        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not extract email from user info"
            )
        
        logger.info("Processing sync query from authenticated user")
        
        # Call combined_execute function from app.py
        router_output, final_output = combined_execute(email, user_message.text)
        
        # Parse router output if it's a string
        try:
            router_data = json.loads(router_output) if isinstance(router_output, str) else router_output
        except:
            router_data = {"raw": router_output}
        
        return {
            "router_output": router_data,
            "final_output": final_output
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error in send_message")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Server error: {str(e)}"
        )


@router.post("/api/query", response_model=CombinedResponse)
async def query_sync(
    user_message: Message,
    token_data: Dict[str, Any] = Depends(verify_token)
):
    """
    Synchronous endpoint that calls combined_execute and returns complete response.
    This is a non-streaming alternative to /api/messages.
    Token is validated via dependency.
    """
    try:
        user_info = extract_user_info(token_data)
        email = user_info.get("email") or user_info.get("upn") or user_info.get("preferred_username", "")
        
        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not extract email from user info"
            )
        
        logger.info(f"Processing sync query from authenticated user")
        
        # Call combined_execute function from app.py
        router_output, final_output = combined_execute(email, user_message.text)
        
        # Parse router output if it's a string
        try:
            router_data = json.loads(router_output) if isinstance(router_output, str) else router_output
        except:
            router_data = {"raw": router_output}
        
        return {
            "router_output": router_data,
            "final_output": final_output
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error in query_sync")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Server error: {str(e)}"
        )
