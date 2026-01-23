"""Alternative Data Platform Python SDK.

This SDK provides programmatic access to the Alternative Data Platform,
including REST API clients and WebSocket streaming.
"""

from src.sdk.stream import (
    AltDataStreamClient,
    AsyncFactorStream,
    StreamSubscription,
    VerbosityLevel,
    FactorUpdate,
    ConnectionState,
    stream_factors,
)

__all__ = [
    "AltDataStreamClient",
    "AsyncFactorStream",
    "StreamSubscription",
    "VerbosityLevel",
    "FactorUpdate",
    "ConnectionState",
    "stream_factors",
]

__version__ = "0.1.0"
