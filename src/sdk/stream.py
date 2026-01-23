"""WebSocket streaming client for real-time factor updates (US-012).

This module provides an async WebSocket client for subscribing to
real-time factor updates from the Alternative Data Platform.

Example usage:
    ```python
    import asyncio
    from altdata.sdk import AltDataStreamClient, VerbosityLevel

    async def main():
        client = AltDataStreamClient(
            api_key="your-api-key",
            base_url="wss://api.altdata.example.com"
        )

        # Define callback for factor updates
        async def on_update(update):
            print(f"Factor: {update.factor_id}, Ticker: {update.ticker}, Value: {update.value}")

        # Subscribe to specific factors and tickers
        await client.connect()
        await client.subscribe(
            factors=["tsa_throughput_momentum", "seated_diners_momentum"],
            tickers=["DAL", "UAL", "DRI"],
            verbosity=VerbosityLevel.FULL,
            callback=on_update
        )

        # Keep connection alive
        try:
            await client.run_forever()
        finally:
            await client.disconnect()

    asyncio.run(main())
    ```
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Coroutine, Optional

import websockets
from websockets.exceptions import (
    ConnectionClosed,
    ConnectionClosedError,
    ConnectionClosedOK,
    InvalidStatusCode,
)

logger = logging.getLogger(__name__)


class VerbosityLevel(str, Enum):
    """Verbosity levels for streaming data.

    Attributes:
        SIMPLE: Returns only factor_id, ticker, value, and timestamp.
        DELTA: Includes value changes (delta and delta_pct).
        FULL: Returns complete data including mean, variance, and metadata.
    """

    SIMPLE = "simple"
    DELTA = "delta"
    FULL = "full"


class ConnectionState(str, Enum):
    """WebSocket connection states.

    Attributes:
        DISCONNECTED: Not connected to server.
        CONNECTING: Connection attempt in progress.
        CONNECTED: Successfully connected.
        RECONNECTING: Attempting to reconnect after disconnection.
        FAILED: Connection failed after max retries.
    """

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"


@dataclass
class FactorUpdate:
    """Represents a real-time factor value update.

    Attributes:
        factor_id: Unique identifier of the factor.
        ticker: Stock ticker symbol.
        value: Current factor value (mean).
        timestamp: When the update was generated.
        variance: Uncertainty measure of the value (optional).
        delta: Change from previous value (optional).
        delta_pct: Percentage change from previous value (optional).
        metadata: Additional data depending on verbosity level (optional).
    """

    factor_id: str
    ticker: str
    value: float
    timestamp: datetime
    variance: Optional[float] = None
    delta: Optional[float] = None
    delta_pct: Optional[float] = None
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_message(cls, data: dict) -> "FactorUpdate":
        """Create FactorUpdate from WebSocket message.

        Args:
            data: Raw message data from WebSocket.

        Returns:
            FactorUpdate instance.
        """
        timestamp_str = data.get("timestamp", "")
        if timestamp_str:
            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            except ValueError:
                timestamp = datetime.utcnow()
        else:
            timestamp = datetime.utcnow()

        return cls(
            factor_id=data.get("factor_id", ""),
            ticker=data.get("ticker", ""),
            value=data.get("value") or data.get("mean", 0.0),
            timestamp=timestamp,
            variance=data.get("variance"),
            delta=data.get("delta"),
            delta_pct=data.get("delta_pct"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class StreamSubscription:
    """Configuration for a WebSocket subscription.

    Attributes:
        factors: List of factor IDs to subscribe to (empty = all).
        tickers: List of ticker symbols to subscribe to (empty = all).
        verbosity: Level of detail in updates.
        callback: Async function called for each update.
    """

    factors: list[str] = field(default_factory=list)
    tickers: list[str] = field(default_factory=list)
    verbosity: VerbosityLevel = VerbosityLevel.SIMPLE
    callback: Optional[Callable[[FactorUpdate], Coroutine[Any, Any, None]]] = None


class AltDataStreamClient:
    """Async WebSocket client for real-time factor updates.

    This client handles connection management, automatic reconnection,
    and subscription management for the Alternative Data Platform's
    WebSocket streaming API.

    Attributes:
        api_key: API key for authentication.
        base_url: WebSocket server URL.
        max_retries: Maximum reconnection attempts.
        retry_delay: Initial delay between reconnection attempts (seconds).
        retry_backoff: Multiplier for exponential backoff.
        heartbeat_interval: Interval for ping messages (seconds).

    Example:
        ```python
        client = AltDataStreamClient(api_key="your-api-key")
        await client.connect()
        await client.subscribe(
            factors=["factor_a"],
            callback=my_handler
        )
        await client.run_forever()
        ```
    """

    DEFAULT_BASE_URL = "wss://api.altdata.example.com/api/v1/stream/factors"
    DEFAULT_MAX_RETRIES = 5
    DEFAULT_RETRY_DELAY = 1.0
    DEFAULT_RETRY_BACKOFF = 2.0
    DEFAULT_HEARTBEAT_INTERVAL = 30

    def __init__(
        self,
        api_key: str,
        base_url: Optional[str] = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_delay: float = DEFAULT_RETRY_DELAY,
        retry_backoff: float = DEFAULT_RETRY_BACKOFF,
        heartbeat_interval: int = DEFAULT_HEARTBEAT_INTERVAL,
    ):
        """Initialize the streaming client.

        Args:
            api_key: API key for authentication.
            base_url: WebSocket server URL (defaults to production URL).
            max_retries: Maximum number of reconnection attempts.
            retry_delay: Initial delay between retries in seconds.
            retry_backoff: Multiplier for exponential backoff.
            heartbeat_interval: Interval for heartbeat pings in seconds.
        """
        self.api_key = api_key
        self.base_url = base_url or self.DEFAULT_BASE_URL
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.retry_backoff = retry_backoff
        self.heartbeat_interval = heartbeat_interval

        self._websocket: Optional[websockets.WebSocketClientProtocol] = None
        self._state: ConnectionState = ConnectionState.DISCONNECTED
        self._subscriptions: list[StreamSubscription] = []
        self._callbacks: list[Callable[[FactorUpdate], Coroutine[Any, Any, None]]] = []
        self._client_id: Optional[str] = None
        self._retry_count = 0
        self._should_reconnect = True
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._receive_task: Optional[asyncio.Task] = None
        self._state_change_callbacks: list[Callable[[ConnectionState], None]] = []

    @property
    def state(self) -> ConnectionState:
        """Get current connection state."""
        return self._state

    @property
    def client_id(self) -> Optional[str]:
        """Get client ID assigned by server."""
        return self._client_id

    @property
    def is_connected(self) -> bool:
        """Check if client is currently connected."""
        return self._state == ConnectionState.CONNECTED and self._websocket is not None

    def on_state_change(self, callback: Callable[[ConnectionState], None]) -> None:
        """Register a callback for connection state changes.

        Args:
            callback: Function called when connection state changes.
        """
        self._state_change_callbacks.append(callback)

    def _set_state(self, state: ConnectionState) -> None:
        """Update connection state and notify callbacks."""
        old_state = self._state
        self._state = state
        if old_state != state:
            logger.info(f"Connection state changed: {old_state.value} -> {state.value}")
            for callback in self._state_change_callbacks:
                try:
                    callback(state)
                except Exception as e:
                    logger.error(f"State change callback error: {e}")

    async def connect(self) -> bool:
        """Establish WebSocket connection to the server.

        Returns:
            True if connection successful, False otherwise.

        Raises:
            Exception: If connection fails after all retries.
        """
        self._should_reconnect = True
        self._retry_count = 0
        return await self._connect_internal()

    async def _connect_internal(self) -> bool:
        """Internal connection logic with retry handling."""
        self._set_state(ConnectionState.CONNECTING)

        ws_url = f"{self.base_url}?api_key={self.api_key}"

        try:
            self._websocket = await websockets.connect(
                ws_url,
                ping_interval=None,  # We handle our own heartbeat
                ping_timeout=None,
                close_timeout=5,
            )

            # Wait for connection confirmation
            response = await asyncio.wait_for(self._websocket.recv(), timeout=10)
            data = json.loads(response)

            if data.get("type") == "connected":
                self._client_id = data.get("client_id")
                self._set_state(ConnectionState.CONNECTED)
                self._retry_count = 0
                logger.info(f"Connected with client_id: {self._client_id}")

                # Resubscribe to any existing subscriptions
                for subscription in self._subscriptions:
                    await self._send_subscribe(subscription)

                return True
            else:
                logger.error(f"Unexpected connection response: {data}")
                await self._handle_disconnect()
                return False

        except InvalidStatusCode as e:
            logger.error(f"Connection rejected with status {e.status_code}")
            self._set_state(ConnectionState.FAILED)
            return False

        except (ConnectionRefusedError, OSError) as e:
            logger.error(f"Connection failed: {e}")
            await self._handle_disconnect()
            return False

        except asyncio.TimeoutError:
            logger.error("Connection timed out waiting for server response")
            await self._handle_disconnect()
            return False

        except Exception as e:
            logger.exception(f"Unexpected connection error: {e}")
            await self._handle_disconnect()
            return False

    async def _handle_disconnect(self) -> None:
        """Handle disconnection and attempt reconnection if appropriate."""
        if self._websocket:
            try:
                await self._websocket.close()
            except Exception:
                pass
            self._websocket = None

        if self._should_reconnect and self._retry_count < self.max_retries:
            self._set_state(ConnectionState.RECONNECTING)
            delay = self.retry_delay * (self.retry_backoff ** self._retry_count)
            self._retry_count += 1
            logger.info(f"Reconnecting in {delay:.1f}s (attempt {self._retry_count}/{self.max_retries})")
            await asyncio.sleep(delay)
            await self._connect_internal()
        else:
            self._set_state(ConnectionState.FAILED if self._should_reconnect else ConnectionState.DISCONNECTED)

    async def disconnect(self) -> None:
        """Gracefully disconnect from the server."""
        self._should_reconnect = False

        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None

        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
            self._receive_task = None

        if self._websocket:
            try:
                await self._websocket.close()
            except Exception:
                pass
            self._websocket = None

        self._set_state(ConnectionState.DISCONNECTED)
        logger.info("Disconnected from server")

    async def subscribe(
        self,
        factors: Optional[list[str]] = None,
        tickers: Optional[list[str]] = None,
        verbosity: VerbosityLevel = VerbosityLevel.SIMPLE,
        callback: Optional[Callable[[FactorUpdate], Coroutine[Any, Any, None]]] = None,
    ) -> bool:
        """Subscribe to factor updates.

        Args:
            factors: List of factor IDs to subscribe to (empty/None = all).
            tickers: List of ticker symbols to subscribe to (empty/None = all).
            verbosity: Level of detail in updates.
            callback: Async function called for each update.

        Returns:
            True if subscription successful.

        Raises:
            RuntimeError: If not connected.
        """
        subscription = StreamSubscription(
            factors=factors or [],
            tickers=tickers or [],
            verbosity=verbosity,
            callback=callback,
        )

        self._subscriptions.append(subscription)
        if callback:
            self._callbacks.append(callback)

        if self.is_connected:
            return await self._send_subscribe(subscription)
        return True  # Will be sent on connect

    async def _send_subscribe(self, subscription: StreamSubscription) -> bool:
        """Send subscription message to server."""
        if not self._websocket:
            return False

        message = {
            "action": "subscribe",
            "factors": subscription.factors,
            "tickers": subscription.tickers,
            "verbosity": subscription.verbosity.value,
        }

        try:
            await self._websocket.send(json.dumps(message))
            response = await asyncio.wait_for(self._websocket.recv(), timeout=5)
            data = json.loads(response)

            if data.get("type") == "subscribed":
                logger.info(
                    f"Subscribed to factors={subscription.factors}, "
                    f"tickers={subscription.tickers}, verbosity={subscription.verbosity.value}"
                )
                return True
            else:
                logger.error(f"Subscription failed: {data}")
                return False

        except Exception as e:
            logger.error(f"Failed to send subscription: {e}")
            return False

    async def unsubscribe(
        self,
        factors: Optional[list[str]] = None,
        tickers: Optional[list[str]] = None,
    ) -> bool:
        """Unsubscribe from factor updates.

        Args:
            factors: List of factor IDs to unsubscribe from.
            tickers: List of ticker symbols to unsubscribe from.

        Returns:
            True if unsubscription successful.
        """
        if not self._websocket:
            return False

        message = {
            "action": "unsubscribe",
            "factors": factors or [],
            "tickers": tickers or [],
        }

        try:
            await self._websocket.send(json.dumps(message))
            response = await asyncio.wait_for(self._websocket.recv(), timeout=5)
            data = json.loads(response)

            if data.get("type") == "unsubscribed":
                logger.info(f"Unsubscribed from factors={factors}, tickers={tickers}")
                return True
            else:
                logger.error(f"Unsubscription failed: {data}")
                return False

        except Exception as e:
            logger.error(f"Failed to send unsubscription: {e}")
            return False

    async def ping(self) -> bool:
        """Send a ping message to the server.

        Returns:
            True if pong received.
        """
        if not self._websocket:
            return False

        try:
            await self._websocket.send(json.dumps({"action": "ping"}))
            response = await asyncio.wait_for(self._websocket.recv(), timeout=5)
            data = json.loads(response)
            return data.get("type") == "pong"
        except Exception as e:
            logger.error(f"Ping failed: {e}")
            return False

    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeat pings."""
        while self.is_connected:
            await asyncio.sleep(self.heartbeat_interval)
            if self.is_connected:
                success = await self.ping()
                if not success:
                    logger.warning("Heartbeat failed, connection may be stale")

    async def _receive_loop(self) -> None:
        """Receive and process messages from server."""
        while self.is_connected and self._websocket:
            try:
                message = await self._websocket.recv()
                data = json.loads(message)
                await self._handle_message(data)

            except ConnectionClosedOK:
                logger.info("Server closed connection gracefully")
                await self._handle_disconnect()
                break

            except ConnectionClosedError as e:
                logger.error(f"Connection closed with error: {e}")
                await self._handle_disconnect()
                break

            except ConnectionClosed:
                logger.warning("Connection closed")
                await self._handle_disconnect()
                break

            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON received: {e}")

            except Exception as e:
                logger.exception(f"Error processing message: {e}")

    async def _handle_message(self, data: dict) -> None:
        """Process received message and dispatch to callbacks."""
        msg_type = data.get("type")

        if msg_type == "update":
            update = FactorUpdate.from_message(data)
            for callback in self._callbacks:
                try:
                    await callback(update)
                except Exception as e:
                    logger.error(f"Callback error: {e}")

        elif msg_type == "heartbeat":
            logger.debug("Received heartbeat")

        elif msg_type == "error":
            logger.error(f"Server error: {data.get('message')}")

        elif msg_type in ("subscribed", "unsubscribed", "pong", "connected"):
            pass  # Already handled in respective methods

        else:
            logger.debug(f"Unknown message type: {msg_type}")

    async def run_forever(self) -> None:
        """Run the client, processing messages until disconnected.

        This method blocks until the client is disconnected or an error occurs.
        It handles automatic reconnection according to the configured parameters.
        """
        if not self.is_connected:
            await self.connect()

        if not self.is_connected:
            raise RuntimeError("Failed to connect to server")

        # Start heartbeat and receive loops
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self._receive_task = asyncio.create_task(self._receive_loop())

        try:
            # Wait for receive task to complete (disconnection)
            await self._receive_task
        except asyncio.CancelledError:
            pass
        finally:
            if self._heartbeat_task:
                self._heartbeat_task.cancel()
                try:
                    await self._heartbeat_task
                except asyncio.CancelledError:
                    pass

    async def __aenter__(self) -> "AltDataStreamClient":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.disconnect()


# Convenience function for quick subscriptions
async def stream_factors(
    api_key: str,
    factors: Optional[list[str]] = None,
    tickers: Optional[list[str]] = None,
    verbosity: VerbosityLevel = VerbosityLevel.SIMPLE,
    base_url: Optional[str] = None,
) -> "AsyncFactorStream":
    """Create a simple async iterator for factor updates.

    Args:
        api_key: API key for authentication.
        factors: List of factor IDs to subscribe to.
        tickers: List of ticker symbols to subscribe to.
        verbosity: Level of detail in updates.
        base_url: WebSocket server URL.

    Yields:
        FactorUpdate objects as they arrive.

    Example:
        ```python
        async for update in stream_factors(api_key, factors=["factor_a"]):
            print(f"{update.ticker}: {update.value}")
        ```
    """
    return AsyncFactorStream(
        api_key=api_key,
        factors=factors,
        tickers=tickers,
        verbosity=verbosity,
        base_url=base_url,
    )


class AsyncFactorStream:
    """Async iterator for factor updates.

    This class provides a simpler interface for consuming factor updates
    using async for loops.
    """

    def __init__(
        self,
        api_key: str,
        factors: Optional[list[str]] = None,
        tickers: Optional[list[str]] = None,
        verbosity: VerbosityLevel = VerbosityLevel.SIMPLE,
        base_url: Optional[str] = None,
    ):
        """Initialize the async stream."""
        self.api_key = api_key
        self.factors = factors
        self.tickers = tickers
        self.verbosity = verbosity
        self.base_url = base_url
        self._client: Optional[AltDataStreamClient] = None
        self._queue: asyncio.Queue[FactorUpdate] = asyncio.Queue()
        self._running = False

    async def _on_update(self, update: FactorUpdate) -> None:
        """Handle incoming updates by adding to queue."""
        await self._queue.put(update)

    async def __aenter__(self) -> "AsyncFactorStream":
        """Start the stream."""
        self._client = AltDataStreamClient(
            api_key=self.api_key,
            base_url=self.base_url,
        )
        await self._client.connect()
        await self._client.subscribe(
            factors=self.factors,
            tickers=self.tickers,
            verbosity=self.verbosity,
            callback=self._on_update,
        )
        self._running = True

        # Start receive loop in background
        asyncio.create_task(self._client.run_forever())

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Stop the stream."""
        self._running = False
        if self._client:
            await self._client.disconnect()

    def __aiter__(self) -> "AsyncFactorStream":
        """Return async iterator."""
        return self

    async def __anext__(self) -> FactorUpdate:
        """Get next update from stream."""
        if not self._running:
            raise StopAsyncIteration
        try:
            return await self._queue.get()
        except asyncio.CancelledError:
            raise StopAsyncIteration
