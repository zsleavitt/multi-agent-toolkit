"""Map provider-specific exceptions to ``ProviderError``."""

from __future__ import annotations

import re
from typing import Any

from mat_runtime.providers.model import ProviderError

_CONTEXT_LENGTH_RE = re.compile(
    r"context|token.?limit|maximum.?context|too.?long|max.?tokens",
    re.IGNORECASE,
)


def _is_context_length_message(message: str) -> bool:
    return bool(_CONTEXT_LENGTH_RE.search(message))


def _retry_after_ms_from_headers(headers: Any) -> int | None:
    if headers is None:
        return None
    raw = None
    if isinstance(headers, dict):
        raw = headers.get("retry-after") or headers.get("Retry-After")
    else:
        getter = getattr(headers, "get", None)
        if callable(getter):
            raw = getter("retry-after") or getter("Retry-After")
    if raw is None:
        return None
    try:
        return int(float(raw)) * 1000
    except (TypeError, ValueError):
        return None


def map_anthropic_error(exc: BaseException) -> ProviderError:
    from anthropic import (
        APIConnectionError,
        APITimeoutError,
        AuthenticationError,
        BadRequestError,
        RateLimitError,
    )

    if isinstance(exc, AuthenticationError):
        return ProviderError(code="auth_error", message=str(exc))
    if isinstance(exc, RateLimitError):
        response = getattr(exc, "response", None)
        headers = getattr(response, "headers", None) if response is not None else None
        retry_after_ms = _retry_after_ms_from_headers(headers)
        return ProviderError(
            code="rate_limit",
            message=str(exc),
            retryable=True,
            retry_after_ms=retry_after_ms,
        )
    if isinstance(exc, APITimeoutError):
        return ProviderError(code="timeout", message=str(exc), retryable=True)
    if isinstance(exc, APIConnectionError):
        return ProviderError(code="timeout", message=str(exc), retryable=True)
    if isinstance(exc, BadRequestError):
        message = str(exc)
        if _is_context_length_message(message):
            return ProviderError(code="context_length", message=message)
    return ProviderError(code="unknown", message=str(exc))


def map_openai_error(exc: BaseException) -> ProviderError:
    from openai import (
        APIConnectionError,
        APITimeoutError,
        AuthenticationError,
        BadRequestError,
        RateLimitError,
    )

    if isinstance(exc, AuthenticationError):
        return ProviderError(code="auth_error", message=str(exc))
    if isinstance(exc, RateLimitError):
        response = getattr(exc, "response", None)
        headers = getattr(response, "headers", None) if response is not None else None
        retry_after_ms = _retry_after_ms_from_headers(headers)
        return ProviderError(
            code="rate_limit",
            message=str(exc),
            retryable=True,
            retry_after_ms=retry_after_ms,
        )
    if isinstance(exc, APITimeoutError):
        return ProviderError(code="timeout", message=str(exc), retryable=True)
    if isinstance(exc, APIConnectionError):
        return ProviderError(code="timeout", message=str(exc), retryable=True)
    if isinstance(exc, BadRequestError):
        message = str(exc)
        if _is_context_length_message(message):
            return ProviderError(code="context_length", message=message)
    return ProviderError(code="unknown", message=str(exc))


def map_gemini_error(exc: BaseException) -> ProviderError:
    try:
        from google.api_core import exceptions as google_exceptions
    except ImportError:
        google_exceptions = None  # type: ignore[assignment]

    message = str(exc)
    if google_exceptions is not None:
        if isinstance(exc, google_exceptions.Unauthenticated):
            return ProviderError(code="auth_error", message=message)
        if isinstance(exc, google_exceptions.PermissionDenied):
            return ProviderError(code="auth_error", message=message)
        if isinstance(exc, google_exceptions.ResourceExhausted):
            return ProviderError(
                code="rate_limit",
                message=message,
                retryable=True,
            )
        if isinstance(exc, google_exceptions.DeadlineExceeded):
            return ProviderError(code="timeout", message=message, retryable=True)
        if isinstance(exc, google_exceptions.InvalidArgument):
            if _is_context_length_message(message):
                return ProviderError(code="context_length", message=message)

    lowered = message.lower()
    if "api key" in lowered or "unauthenticated" in lowered or "permission" in lowered:
        return ProviderError(code="auth_error", message=message)
    if "quota" in lowered or "rate" in lowered or "resource exhausted" in lowered:
        return ProviderError(code="rate_limit", message=message, retryable=True)
    if "deadline" in lowered or "timeout" in lowered:
        return ProviderError(code="timeout", message=message, retryable=True)
    if _is_context_length_message(message):
        return ProviderError(code="context_length", message=message)
    return ProviderError(code="unknown", message=message)
