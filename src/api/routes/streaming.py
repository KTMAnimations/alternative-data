"""WebSocket streaming API for real-time factor updates (US-012)."""

import asyncio
import json
from datetime import datetime
from typing import Optional
from enum import Enum

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException, status
from pydantic import BaseModel


router = APIRouter()


class VerbosityLevel(str, Enum):
    """Verbosity levels for streaming data."""
    SIMPLE = "simple"
    DELTA = "delta"
    FULL = "full"


class StreamSubscription(BaseModel):
    """Subscription configuration."""
    factors: list[str] = []
    tickers: list[str] = []
    verbosity: VerbosityLevel = VerbosityLevel.SIMPLE


class ConnectionManager:
    """Manages WebSocket connections and subscriptions."""

    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
        self.subscriptions: dict[str, StreamSubscription] = {}

    async def connect(self, websocket: WebSocket, client_id: str) -> bool:
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        self.subscriptions[client_id] = StreamSubscription()
        return True

    def disconnect(self, client_id: str):
        """Remove a disconnected client."""
        self.active_connections.pop(client_id, None)
        self.subscriptions.pop(client_id, None)

    def update_subscription(self, client_id: str, subscription: StreamSubscription):
        """Update client's subscription."""
        if client_id in self.subscriptions:
            self.subscriptions[client_id] = subscription

    async def send_to_client(self, client_id: str, data: dict):
        """Send data to a specific client."""
        if client_id in self.active_connections:
            websocket = self.active_connections[client_id]
            await websocket.send_json(data)

    async def broadcast(self, data: dict, factor_id: str = None, ticker: str = None):
        """Broadcast data to subscribed clients."""
        for client_id, subscription in self.subscriptions.items():
            # Check if client is subscribed to this factor/ticker
            if factor_id and subscription.factors and factor_id not in subscription.factors:
                continue
            if ticker and subscription.tickers and ticker not in subscription.tickers:
                continue

            # Format based on verbosity
            formatted_data = self._format_data(data, subscription.verbosity)
            await self.send_to_client(client_id, formatted_data)

    def _format_data(self, data: dict, verbosity: VerbosityLevel) -> dict:
        """Format data based on verbosity level."""
        if verbosity == VerbosityLevel.SIMPLE:
            return {
                "factor_id": data.get("factor_id"),
                "ticker": data.get("ticker"),
                "value": data.get("mean"),
                "timestamp": data.get("timestamp"),
            }
        elif verbosity == VerbosityLevel.DELTA:
            return {
                "factor_id": data.get("factor_id"),
                "ticker": data.get("ticker"),
                "value": data.get("mean"),
                "delta": data.get("delta"),
                "delta_pct": data.get("delta_pct"),
                "timestamp": data.get("timestamp"),
            }
        else:  # FULL
            return data


# Global connection manager
manager = ConnectionManager()


@router.websocket("/factors")
async def websocket_factors(
    websocket: WebSocket,
    api_key: str = Query(..., description="API key for authentication"),
):
    """
    WebSocket endpoint for real-time factor updates.

    Connect with an API key and subscribe to specific factors and tickers.

    Messages from client:
    - {"action": "subscribe", "factors": ["factor_id"], "tickers": ["AAPL"], "verbosity": "full"}
    - {"action": "unsubscribe", "factors": ["factor_id"]}
    - {"action": "ping"}

    Messages from server:
    - {"type": "update", "factor_id": "...", "ticker": "...", "mean": 0.05, "variance": 0.001, ...}
    - {"type": "pong"}
    - {"type": "error", "message": "..."}
    """
    # TODO: Validate API key against database
    if not api_key or len(api_key) < 10:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    client_id = f"{api_key[:8]}_{id(websocket)}"

    try:
        await manager.connect(websocket, client_id)

        # Send initial connection confirmation
        await websocket.send_json({
            "type": "connected",
            "client_id": client_id,
            "timestamp": datetime.utcnow().isoformat(),
        })

        # Start heartbeat task
        heartbeat_task = asyncio.create_task(send_heartbeat(websocket))

        try:
            while True:
                # Receive message from client
                data = await websocket.receive_json()

                action = data.get("action")

                if action == "subscribe":
                    subscription = StreamSubscription(
                        factors=data.get("factors", []),
                        tickers=data.get("tickers", []),
                        verbosity=VerbosityLevel(data.get("verbosity", "simple")),
                    )
                    manager.update_subscription(client_id, subscription)
                    await websocket.send_json({
                        "type": "subscribed",
                        "factors": subscription.factors,
                        "tickers": subscription.tickers,
                        "verbosity": subscription.verbosity.value,
                    })

                elif action == "unsubscribe":
                    current = manager.subscriptions.get(client_id, StreamSubscription())
                    # Remove specified factors/tickers
                    factors_to_remove = set(data.get("factors", []))
                    tickers_to_remove = set(data.get("tickers", []))
                    new_subscription = StreamSubscription(
                        factors=[f for f in current.factors if f not in factors_to_remove],
                        tickers=[t for t in current.tickers if t not in tickers_to_remove],
                        verbosity=current.verbosity,
                    )
                    manager.update_subscription(client_id, new_subscription)
                    await websocket.send_json({
                        "type": "unsubscribed",
                        "factors": list(factors_to_remove),
                        "tickers": list(tickers_to_remove),
                    })

                elif action == "ping":
                    await websocket.send_json({"type": "pong"})

                else:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Unknown action: {action}",
                    })

        finally:
            heartbeat_task.cancel()

    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        manager.disconnect(client_id)
        # Log error but don't raise since connection is already closed


async def send_heartbeat(websocket: WebSocket, interval: int = 30):
    """Send periodic heartbeat to keep connection alive."""
    while True:
        await asyncio.sleep(interval)
        try:
            await websocket.send_json({
                "type": "heartbeat",
                "timestamp": datetime.utcnow().isoformat(),
            })
        except Exception:
            break


# HTTP endpoint to check stream status
@router.get("/status")
async def stream_status():
    """Get streaming service status."""
    return {
        "active_connections": len(manager.active_connections),
        "timestamp": datetime.utcnow().isoformat(),
    }


# Function to publish factor updates (called by factor computation service)
async def publish_factor_update(
    factor_id: str,
    ticker: str,
    mean: float,
    variance: float,
    timestamp: datetime,
    delta: Optional[float] = None,
    delta_pct: Optional[float] = None,
    metadata: Optional[dict] = None,
):
    """Publish a factor update to all subscribed clients."""
    data = {
        "type": "update",
        "factor_id": factor_id,
        "ticker": ticker,
        "mean": mean,
        "variance": variance,
        "timestamp": timestamp.isoformat(),
        "delta": delta,
        "delta_pct": delta_pct,
        "metadata": metadata or {},
    }
    await manager.broadcast(data, factor_id=factor_id, ticker=ticker)
