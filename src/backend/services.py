"""Service layer for chat streaming functionality."""
from typing import AsyncGenerator, Dict, Any
from fastapi import Request
import asyncio
import logging
import json

from app import combined_execute

logger = logging.getLogger(__name__)


async def stream_combined_response(
    query: str, 
    user_info: Dict[str, Any],
    request: Request
) -> AsyncGenerator[str, None]:
    """
    Generate streaming response using combined_execute function.
    
    Args:
        query: User's message
        user_info: Dictionary with user information
        request: FastAPI request object for disconnect detection
        
    Yields:
        SSE formatted string chunks
    """
    try:
        # Extract email from user_info
        email = user_info.get("email") or user_info.get("upn") or user_info.get("preferred_username", "")
        
        if not email:
            yield "data: {\"error\": \"Could not extract email from user info\"}\n\n"
            yield "data: [DONE]\n\n"
            return
        
        logger.info(f"Processing query ({len(query)} chars)")
        
        # Call combined_execute function from app.py
        router_output, final_output = combined_execute(email, query)
        
        # Parse router output if it's a string
        try:
            router_data = json.loads(router_output) if isinstance(router_output, str) else router_output
        except:
            router_data = {"raw": router_output}
        
        # Send router information first
        router_chunk = json.dumps({"type": "router", "data": router_data})
        yield f"data: {router_chunk}\n\n"
        
        if await request.is_disconnected():
            logger.info("Client disconnected during streaming")
            return
        
        await asyncio.sleep(0.1)
        
        # Stream the final output word by word for better UX
        if isinstance(final_output, str) and final_output:
            words = final_output.split()
            for i, word in enumerate(words):
                if await request.is_disconnected():
                    logger.info("Client disconnected during streaming")
                    break
                
                chunk = json.dumps({"type": "response", "data": word + (" " if i < len(words) - 1 else "")})
                yield f"data: {chunk}\n\n"
                await asyncio.sleep(0.05)  # Simulate streaming delay
        else:
            # Send as a single chunk if not a string
            final_chunk = json.dumps({"type": "response", "data": str(final_output)})
            yield f"data: {final_chunk}\n\n"
        
        # Send completion marker if not disconnected
        if not await request.is_disconnected():
            yield "data: [DONE]\n\n"
            
    except asyncio.CancelledError:
        logger.info("Stream cancelled by client")
        raise
    except Exception as e:
        logger.exception("Error in stream_combined_response")
        error_chunk = json.dumps({"type": "error", "data": str(e)})
        yield f"data: {error_chunk}\n\n"
        yield "data: [DONE]\n\n"


async def stream_event_generator(
    query: str,
    user_info: Dict[str, Any],
    request: Request
) -> AsyncGenerator[Dict[str, str], None]:
    """
    Wrapper generator for EventSourceResponse compatibility.
    
    Args:
        query: User's message
        user_info: Dictionary with user information
        request: FastAPI request object
        
    Yields:
        Dictionary with 'data' key containing response chunks
    """
    try:
        email = user_info.get("email") or user_info.get("upn") or user_info.get("preferred_username", "")
        
        if not email:
            yield {"data": json.dumps({"error": "Could not extract email from user info"})}
            yield {"data": "[DONE]"}
            return
        
        logger.info(f"Processing query ({len(query)} chars)")
        
        # Call combined_execute function from app.py
        router_output, final_output = combined_execute(email, query)
        
        # Parse router output if it's a string
        try:
            router_data = json.loads(router_output) if isinstance(router_output, str) else router_output
        except:
            router_data = {"raw": router_output}
        
        # Send router information first
        yield {"data": json.dumps({"type": "router", "data": router_data})}
        
        if await request.is_disconnected():
            return
        
        await asyncio.sleep(0.1)
        
        # Stream the final output word by word
        if isinstance(final_output, str) and final_output:
            words = final_output.split()
            for i, word in enumerate(words):
                if await request.is_disconnected():
                    break
                
                yield {"data": json.dumps({"type": "response", "data": word + (" " if i < len(words) - 1 else "")})}
                await asyncio.sleep(0.05)
        else:
            yield {"data": json.dumps({"type": "response", "data": str(final_output)})}
        
        # Send completion marker
        if not await request.is_disconnected():
            yield {"data": "[DONE]"}
            
    except asyncio.CancelledError:
        logger.info("Stream cancelled by client")
        raise
    except Exception as e:
        logger.exception("Error in stream_event_generator")
        yield {"data": json.dumps({"type": "error", "data": str(e)})}
        yield {"data": "[DONE]"}
