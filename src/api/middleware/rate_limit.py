"""Rate limiting middleware for API endpoints (US-023).

This module provides rate limiting functionality with configurable
limits per user tier and proper rate limit headers.
"""

import time
from datetime import datetime
from typing import Optional
from collections import defaultdict

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from src.core.config import settings


class RateLimitState:
    """Track rate limit state for a client.

    Attributes:
        limit: Maximum requests allowed in the window.
        remaining: Remaining requests in current window.
        reset_time: Unix timestamp when the window resets.
        window_start: Unix timestamp when current window started.
    """

    def __init__(self, limit: int, window_seconds: int = 60):
        """Initialize rate limit state.

        Args:
            limit: Maximum requests per window.
            window_seconds: Window duration in seconds.
        """
        self.limit = limit
        self.window_seconds = window_seconds
        self.remaining = limit
        self.window_start = time.time()
        self.reset_time = self.window_start + window_seconds

    def check_and_update(self) -> tuple[bool, int, int, int]:
        """Check if request is allowed and update state.

        Returns:
            Tuple of (allowed, limit, remaining, reset_time).
        """
        current_time = time.time()

        # Reset window if expired
        if current_time >= self.reset_time:
            self.window_start = current_time
            self.reset_time = current_time + self.window_seconds
            self.remaining = self.limit

        if self.remaining > 0:
            self.remaining -= 1
            return True, self.limit, self.remaining, int(self.reset_time)
        else:
            return False, self.limit, 0, int(self.reset_time)


class RateLimitStore:
    """In-memory store for rate limit tracking.

    For production, this should be replaced with Redis for
    distributed rate limiting across multiple instances.
    """

    def __init__(self):
        """Initialize the rate limit store."""
        self._states: dict[str, RateLimitState] = {}
        self._tier_limits = {
            "free": 100,        # 100 requests per minute
            "pro": 10000,       # 10,000 requests per minute
            "enterprise": -1,   # Unlimited (-1)
        }

    def get_limit_for_tier(self, tier: str) -> int:
        """Get rate limit for a tier.

        Args:
            tier: User tier name.

        Returns:
            Rate limit per minute, or -1 for unlimited.
        """
        return self._tier_limits.get(tier, self._tier_limits["free"])

    def check_rate_limit(
        self,
        client_key: str,
        tier: str = "free",
    ) -> tuple[bool, int, int, int]:
        """Check and update rate limit for a client.

        Args:
            client_key: Unique identifier for the client (e.g., API key or IP).
            tier: User tier for determining limit.

        Returns:
            Tuple of (allowed, limit, remaining, reset_time).
        """
        limit = self.get_limit_for_tier(tier)

        # Unlimited for enterprise
        if limit == -1:
            return True, -1, -1, 0

        # Create or get state for this client
        if client_key not in self._states:
            self._states[client_key] = RateLimitState(limit=limit)
        else:
            # Update limit if tier changed
            if self._states[client_key].limit != limit:
                self._states[client_key].limit = limit
                self._states[client_key].remaining = min(
                    self._states[client_key].remaining, limit
                )

        return self._states[client_key].check_and_update()


# Global rate limit store (replace with Redis in production)
rate_limit_store = RateLimitStore()


def add_rate_limit_headers(
    response: Response,
    limit: int,
    remaining: int,
    reset_time: int,
) -> Response:
    """Add rate limit headers to response.

    Args:
        response: FastAPI response object.
        limit: Maximum requests per window.
        remaining: Remaining requests in current window.
        reset_time: Unix timestamp when window resets.

    Returns:
        Response with rate limit headers added.
    """
    if limit == -1:
        # Unlimited tier
        response.headers["X-RateLimit-Limit"] = "unlimited"
        response.headers["X-RateLimit-Remaining"] = "unlimited"
    else:
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_time)

    return response


def get_client_key(request: Request) -> str:
    """Extract client identifier from request.

    Uses API key if present, otherwise falls back to IP address.

    Args:
        request: FastAPI request object.

    Returns:
        Unique client identifier string.
    """
    # Check for API key in header
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        api_key = auth_header[7:]
        if api_key:
            return f"api_key:{api_key[:16]}"

    # Check for API key in query parameter
    api_key = request.query_params.get("api_key")
    if api_key:
        return f"api_key:{api_key[:16]}"

    # Fall back to IP address
    client_host = request.client.host if request.client else "unknown"
    return f"ip:{client_host}"


def get_client_tier(request: Request) -> str:
    """Get client tier from request.

    In production, this should look up the tier from the database
    based on the authenticated user or API key.

    Args:
        request: FastAPI request object.

    Returns:
        Tier name string.
    """
    # TODO: Look up actual tier from database based on API key
    # For now, default to free tier
    # Check if there's a tier hint in request state (set by auth middleware)
    return getattr(request.state, "user_tier", "free")


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware that applies rate limiting to all API requests.

    This middleware checks rate limits before processing requests
    and adds rate limit headers to all responses.
    """

    def __init__(self, app, excluded_paths: Optional[list[str]] = None):
        """Initialize the middleware.

        Args:
            app: FastAPI application instance.
            excluded_paths: Paths to exclude from rate limiting.
        """
        super().__init__(app)
        self.excluded_paths = excluded_paths or [
            "/health",
            "/docs",
            "/redoc",
            "/openapi.json",
        ]

    async def dispatch(self, request: Request, call_next):
        """Process request with rate limiting.

        Args:
            request: Incoming request.
            call_next: Next middleware/handler.

        Returns:
            Response with rate limit headers.
        """
        # Skip rate limiting for excluded paths
        if any(request.url.path.startswith(path) for path in self.excluded_paths):
            return await call_next(request)

        client_key = get_client_key(request)
        tier = get_client_tier(request)

        allowed, limit, remaining, reset_time = rate_limit_store.check_rate_limit(
            client_key, tier
        )

        if not allowed:
            from fastapi.responses import JSONResponse
            response = JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded",
                    "retry_after": reset_time - int(time.time()),
                },
            )
            return add_rate_limit_headers(response, limit, remaining, reset_time)

        response = await call_next(request)
        return add_rate_limit_headers(response, limit, remaining, reset_time)


__all__ = [
    "RateLimitMiddleware",
    "rate_limit_store",
    "add_rate_limit_headers",
    "get_client_key",
    "get_client_tier",
    "RateLimitState",
    "RateLimitStore",
]
