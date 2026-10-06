"""PII redaction utilities for safe logging."""
import os
import re


def mask_email(email: str) -> str:
    if not email or "@" not in email:
        return "***"
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        masked_local = local[0] + "***"
    else:
        masked_local = local[0] + "***" + local[-1]
    domain_parts = domain.split(".")
    masked_domain = "***." + domain_parts[-1] if len(domain_parts) >= 2 else "***"
    return f"{masked_local}@{masked_domain}"


def mask_query(text: str, max_preview: int = 30) -> str:
    if not text:
        return ""
    stripped = text.strip()
    if len(stripped) <= max_preview:
        return stripped
    return stripped[:max_preview] + f"... ({len(stripped)} chars)"


def mask_filepath(path: str) -> str:
    return os.path.basename(path) if path else ""
