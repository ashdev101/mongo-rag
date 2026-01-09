"""API route handlers."""
import os
from fastapi import APIRouter, Depends, HTTPException, Request, status , Response
from fastapi.responses import FileResponse, JSONResponse
from typing import Dict, Any
from datetime import datetime
import re
import logging
import json
import time

from backend.models import Message, TokenValidationResponse, HealthResponse, CombinedResponse , SharePointMessage
from backend.auth import verify_token, extract_user_info
from app import combined_execute , combined_execute_api
from backend.config import Settings
from backend.security.browser import enforce_browser_request
from backend.security.browser_token import issue_browser_token , validate_browser_token
from backend.security.csrf import issue_csrf, validate_csrf

from rbac_onepager import rbac_onepager

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
            "user": user_info
        }
    except Exception as e:
        logger.exception("Error retrieving user information")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve user information: {str(e)}"
        )

@router.get("/api/init")    
async def init(request: Request, response: Response):
    # enforce_browser_request(request)

    browser_token = issue_browser_token(request)
    csrf_token = issue_csrf(browser_token)

    response.set_cookie(
        key="browser_token",
        value=browser_token,
        httponly=True,
        secure=True,
        samesite="none",
        path="/"
    )

    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=True,
        secure=True,
        samesite="none",
        path="/"
    )

    return {"token":csrf_token }


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
        
        result = await combined_execute_api(email, user_message.text)

        print(f"Result: {result}")

        # Handle file response
        if result.type == "file":
            file_path = result.content
            if not os.path.exists(file_path):
                raise HTTPException(status_code=404, detail="File not found")
            return FileResponse(
                path=file_path,
                filename=os.path.basename(file_path),
                media_type="application/pdf",
            )
    
        return {
            "router_output": {"type": result.type},
            "final_output": result.content
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
    
@router.post("/api/secure-query", response_model=CombinedResponse)
async def secure_query(
    user_message: SharePointMessage,
    request: Request,
):
    """
    Browser-only, site-locked endpoint.
    No Azure AD / JWT involved.
    """

    # 1. Browser enforcement
    # enforce_browser_request(request)

    # 2. Browser token
    # browser_payload = validate_browser_token(request)
    # browser_token = request.cookies.get("browser_token")

    # 3. CSRF
    # validate_csrf(request, browser_token)

    # 5. Business logic
    result = await combined_execute_api(
        user_message.email,
        user_message.text,
    )

    # ✅ USE ATTRIBUTES, NOT DICT ACCESS
    if result.type == "file":
        file_path = result.content

        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")

        return FileResponse(
            path=file_path,
            filename=os.path.basename(file_path),
            media_type="application/pdf",
        )

    # TEXT RESPONSE
    return JSONResponse(
        content={
            "final_output": result.content
        }
    )

@router.post("/api/test/secure-query", response_model=CombinedResponse)
async def test_secure_query(
    user_message: SharePointMessage,
    request: Request,
):
    """
    Browser-only, site-locked endpoint.
    No Azure AD / JWT involved.
    """

    # 1. Browser enforcement
    # enforce_browser_request(request)

    # 2. Browser token
    # browser_payload = validate_browser_token(request)
    # browser_token = request.cookies.get("browser_token")

    # 3. CSRF
    # validate_csrf(request, browser_token)

    # 5. Business logic
    result = await combined_execute_api(
        user_message.email,
        user_message.text,
    )

    # ✅ USE ATTRIBUTES, NOT DICT ACCESS
    if result.type == "file":
        file_path = result.content

        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")

        return FileResponse(
            path=file_path,
            filename=os.path.basename(file_path),
            media_type="application/pdf",
        )

    # TEXT RESPONSE
    return JSONResponse(
        content={
            "final_output": result.content
        }
    )
