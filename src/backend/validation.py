"""Input validation utilities."""
import re
from fastapi import HTTPException, status

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
EMAIL_MIN_LENGTH = 5
EMAIL_MAX_LENGTH = 254


def validate_email(email: str, field_name: str = "email") -> str:
    if not email or not email.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{field_name} is required",
        )
    email = email.strip()
    if len(email) < EMAIL_MIN_LENGTH or len(email) > EMAIL_MAX_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{field_name} must be between {EMAIL_MIN_LENGTH} and {EMAIL_MAX_LENGTH} characters",
        )
    if not EMAIL_REGEX.match(email):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{field_name} has an invalid email format",
        )
    return email


def get_validated_email(user_info: dict) -> str:
    email = (
        user_info.get("email")
        or user_info.get("upn")
        or user_info.get("preferred_username", "")
    )
    return validate_email(email, field_name="email")
