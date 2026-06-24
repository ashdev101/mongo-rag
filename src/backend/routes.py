"""API route handlers."""
import os
import logging
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse, JSONResponse
from typing import Dict, Any
from datetime import datetime
import json
import time

from backend.models import Message, TestSharePointMessage, TokenValidationResponse, HealthResponse, CombinedResponse , SharePointMessage
from backend.auth import verify_token, extract_user_info
from app import combined_execute , combined_execute_api
from backend.validation import get_validated_email
from backend.logging_config import get_logger, log_with_context, log_with_request

from rbac_onepager import rbac_onepager

logger = get_logger(__name__)

router = APIRouter()


@router.get("/api/health", response_model=HealthResponse)
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
    request: Request,
    token_data: Dict[str, Any] = Depends(verify_token)
):
    """
    Receive a message from authenticated user and return response.
    This endpoint calls combined_execute from app.py as the entry point.
    Token is validated via dependency.
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    try:
        user_info = extract_user_info(token_data)
        email = get_validated_email(user_info)
        
        log_with_request(logger, logging.INFO, f"Processing message from user: {email}", request_id, user_email=email)
        log_with_request(logger, logging.DEBUG, f"Message text: {user_message.text[:100]}...", request_id)
        
        start_time = time.time()
        result = await combined_execute_api(email, user_message.text)
        processing_time = time.time() - start_time

        log_with_request(
            logger, logging.INFO,
            "Message processed successfully",
            request_id,
            user_email=email,
            result_type=result.type,
            duration=round(processing_time, 3)
        )

        # Handle file response
        if result.type == "file":
            file_path = result.content
            if not os.path.exists(file_path):
                log_with_request(logger, logging.ERROR, f"File not found: {file_path}", request_id)
                raise HTTPException(status_code=404, detail="File not found")
            
            log_with_request(logger, logging.INFO, f"Returning file response: {os.path.basename(file_path)}", request_id)
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
        log_with_request(
            logger, logging.ERROR,
            f"Error in send_message: {str(e)}",
            request_id,
            user_email=email if 'email' in locals() else "unknown"
        )
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
        email = get_validated_email(user_info)
        
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
    token_data: Dict[str, Any] = Depends(verify_token)
):
    """
    Browser-only, site-locked endpoint.
    No Azure AD / JWT involved.
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    user_info = extract_user_info(token_data)

    mappings = {
        "soorajn349@tataplay.com" : "Shayanta.Chaudhuri@tataplay.com" ,
        "samratha738@tataplay.com" : "Pallavi.Kaushik@tataplay.com",
        "ponugapatiav142@tataplay.com" : "Niranjan.Patnaik@tataplay.com",
        "vidyah018@tataplay.com" : "mollyt@tataplay.com",
    }

    original_email = get_validated_email(user_info)
    # 4. User mapping
    if original_email in mappings:
        original_email = mappings[original_email]
        logger.info(f"[{request_id}] Email mapped: {original_email} -> {original_email}")

    logger.info(f"[{request_id}] Processing secure query from: {original_email}")
    logger.debug(f"[{request_id}] Query: {user_message.text[:100]}...")

    # 5. Business logic
    start_time = time.time()
    result = await combined_execute_api(
        original_email,
        user_message.text,
    )
    processing_time = time.time() - start_time
    
    logger.info(
        f"[{request_id}] Secure query processed",
        extra={
            "user_email": original_email,
            "result_type": result.type,
            "processing_time": round(processing_time, 3)
        }
    )

    # ✅ USE ATTRIBUTES, NOT DICT ACCESS
    if result.type == "file":
        file_path = result.content

        if not os.path.exists(file_path):
            logger.error(f"[{request_id}] File not found: {file_path}")
            raise HTTPException(status_code=404, detail="File not found")

        logger.info(f"[{request_id}] Returning file: {os.path.basename(file_path)}")
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
    user_message: TestSharePointMessage,
    request: Request,
):
    """
    Browser-only, site-locked endpoint.
    No Azure AD / JWT involved.
    """

    # 5. Business logic
    email = get_validated_email({"email": user_message.email})
    result = await combined_execute_api(
        email,
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
