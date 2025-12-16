"""JWT token validation utilities."""
from fastapi import HTTPException, Header, status
from typing import Optional, Dict, Any
import jwt
from jwt import PyJWKClient
from functools import lru_cache
import logging
from datetime import datetime, timezone

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@lru_cache(maxsize=1)
def get_jwks_client() -> PyJWKClient:
    """Get cached JWKS client for token validation."""
    return PyJWKClient(settings.JWKS_URL)


async def verify_token(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    """
    Dependency to validate JWT token in Authorization header.
    Uses Azure AD JWKS for signature verification.
    
    Args:
        authorization: Authorization header with Bearer token
        
    Returns:
        Decoded token payload with user information
        
    Raises:
        HTTPException: If token is invalid or missing
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise ValueError("Invalid authentication scheme")
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format. Use: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        # Verify token signature and claims
        jwks_client = get_jwks_client()
        signing_key = jwks_client.get_signing_key_from_jwt(token)

        decoded = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.ALLOWED_AUDIENCES,
            issuer=settings.ALLOWED_ISSUERS,
        )

        logger.info("Token validated successfully")

        # Check token expiration manually
        exp = decoded.get("exp")
        if exp:
            exp_datetime = datetime.fromtimestamp(exp, tz=timezone.utc)
            now = datetime.now(timezone.utc)
            if now >= exp_datetime:
                raise jwt.ExpiredSignatureError("Token has expired")

        return decoded

    except jwt.ExpiredSignatureError:
        logger.warning("Token has expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidAudienceError as e:
        logger.error(f"Invalid audience: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token audience",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidIssuerError as e:
        logger.error(f"Invalid issuer: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token issuer",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidSignatureError:
        logger.error("Invalid token signature")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token signature",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.DecodeError as e:
        logger.error(f"Token decode error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token format",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        logger.exception("Unexpected error during token validation")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Token validation error: {str(e)}"
        )


def extract_user_info(token_data: Dict[str, Any]) -> Dict[str, str]:
    """
    Extract user information from validated token payload.
    
    Args:
        token_data: Decoded JWT token payload
        
    Returns:
        Dictionary with user information
    """
    return {
        "name": token_data.get("name", ""),
        "email": token_data.get("email", ""),
        "upn": token_data.get("upn", ""),
        "oid": token_data.get("oid", ""),
        "preferred_username": token_data.get("preferred_username", ""),
    }
