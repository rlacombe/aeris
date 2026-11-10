"""Shared recovery categories for autonomous tool execution."""

from __future__ import annotations

from enum import Enum


class RecoveryCategory(str, Enum):
    AUTHORIZATION = "authorization"
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    TRANSIENT_UPSTREAM = "transient_upstream"
    MISSING_CREDENTIAL = "missing_credential"
    DATA_UNAVAILABLE = "data_unavailable"
    INVALID_INPUT = "invalid_input"
    INTERNAL = "internal"


def classify_error(error: BaseException | str) -> RecoveryCategory:
    """Map provider-specific messages to stable recovery behavior."""
    message = str(error).lower()
    if "429" in message or "rate limit" in message:
        return RecoveryCategory.RATE_LIMIT
    if "timeout" in message or "timed out" in message:
        return RecoveryCategory.TIMEOUT
    if any(token in message for token in ("502", "503", "504", "temporar", "connection")):
        return RecoveryCategory.TRANSIENT_UPSTREAM
    if any(token in message for token in ("api key", "credential", "unauthorized", "401")):
        return RecoveryCategory.MISSING_CREDENTIAL
    if any(token in message for token in ("not found", "no data", "no rows", "404")):
        return RecoveryCategory.DATA_UNAVAILABLE
    if any(token in message for token in ("invalid", "requires", "must ")):
        return RecoveryCategory.INVALID_INPUT
    return RecoveryCategory.INTERNAL
