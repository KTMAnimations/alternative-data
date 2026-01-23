"""Tests for WebSocket streaming SDK (US-012)."""

import asyncio
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.sdk.stream import (
    AltDataStreamClient,
    AsyncFactorStream,
    ConnectionState,
    FactorUpdate,
    StreamSubscription,
    VerbosityLevel,
)


class TestFactorUpdate:
    """Tests for FactorUpdate dataclass."""

    def test_from_message_full_data(self):
        """Test creating FactorUpdate from complete message."""
        message = {
            "type": "update",
            "factor_id": "tsa_throughput_momentum",
            "ticker": "DAL",
            "mean": 0.045,
            "variance": 0.001,
            "timestamp": "2025-01-15T10:30:00Z",
            "delta": 0.002,
            "delta_pct": 4.65,
            "metadata": {"source": "tsa"},
        }

        update = FactorUpdate.from_message(message)

        assert update.factor_id == "tsa_throughput_momentum"
        assert update.ticker == "DAL"
        assert update.value == 0.045
        assert update.variance == 0.001
        assert update.delta == 0.002
        assert update.delta_pct == 4.65
        assert update.metadata == {"source": "tsa"}
        assert isinstance(update.timestamp, datetime)

    def test_from_message_minimal_data(self):
        """Test creating FactorUpdate from minimal message."""
        message = {
            "factor_id": "test_factor",
            "ticker": "AAPL",
            "value": 0.05,
        }

        update = FactorUpdate.from_message(message)

        assert update.factor_id == "test_factor"
        assert update.ticker == "AAPL"
        assert update.value == 0.05
        assert update.variance is None
        assert update.delta is None
        assert update.delta_pct is None
        assert update.metadata == {}

    def test_from_message_with_mean_instead_of_value(self):
        """Test that mean field is used if value is not present."""
        message = {
            "factor_id": "test_factor",
            "ticker": "AAPL",
            "mean": 0.08,
        }

        update = FactorUpdate.from_message(message)

        assert update.value == 0.08

    def test_from_message_invalid_timestamp(self):
        """Test handling of invalid timestamp."""
        message = {
            "factor_id": "test_factor",
            "ticker": "AAPL",
            "value": 0.05,
            "timestamp": "invalid-timestamp",
        }

        update = FactorUpdate.from_message(message)

        # Should fall back to current time without raising
        assert isinstance(update.timestamp, datetime)


class TestStreamSubscription:
    """Tests for StreamSubscription dataclass."""

    def test_default_values(self):
        """Test default subscription values."""
        sub = StreamSubscription()

        assert sub.factors == []
        assert sub.tickers == []
        assert sub.verbosity == VerbosityLevel.SIMPLE
        assert sub.callback is None

    def test_custom_values(self):
        """Test subscription with custom values."""
        callback = AsyncMock()
        sub = StreamSubscription(
            factors=["factor_a", "factor_b"],
            tickers=["AAPL", "GOOGL"],
            verbosity=VerbosityLevel.FULL,
            callback=callback,
        )

        assert sub.factors == ["factor_a", "factor_b"]
        assert sub.tickers == ["AAPL", "GOOGL"]
        assert sub.verbosity == VerbosityLevel.FULL
        assert sub.callback == callback


class TestVerbosityLevel:
    """Tests for VerbosityLevel enum."""

    def test_verbosity_values(self):
        """Test verbosity level values."""
        assert VerbosityLevel.SIMPLE.value == "simple"
        assert VerbosityLevel.DELTA.value == "delta"
        assert VerbosityLevel.FULL.value == "full"

    def test_verbosity_from_string(self):
        """Test creating verbosity from string."""
        assert VerbosityLevel("simple") == VerbosityLevel.SIMPLE
        assert VerbosityLevel("delta") == VerbosityLevel.DELTA
        assert VerbosityLevel("full") == VerbosityLevel.FULL


class TestConnectionState:
    """Tests for ConnectionState enum."""

    def test_connection_states(self):
        """Test all connection states exist."""
        assert ConnectionState.DISCONNECTED.value == "disconnected"
        assert ConnectionState.CONNECTING.value == "connecting"
        assert ConnectionState.CONNECTED.value == "connected"
        assert ConnectionState.RECONNECTING.value == "reconnecting"
        assert ConnectionState.FAILED.value == "failed"


class TestAltDataStreamClient:
    """Tests for AltDataStreamClient."""

    def test_initialization_defaults(self):
        """Test client initialization with defaults."""
        client = AltDataStreamClient(api_key="test-api-key")

        assert client.api_key == "test-api-key"
        assert client.base_url == AltDataStreamClient.DEFAULT_BASE_URL
        assert client.max_retries == AltDataStreamClient.DEFAULT_MAX_RETRIES
        assert client.retry_delay == AltDataStreamClient.DEFAULT_RETRY_DELAY
        assert client.retry_backoff == AltDataStreamClient.DEFAULT_RETRY_BACKOFF
        assert client.heartbeat_interval == AltDataStreamClient.DEFAULT_HEARTBEAT_INTERVAL
        assert client.state == ConnectionState.DISCONNECTED
        assert not client.is_connected

    def test_initialization_custom(self):
        """Test client initialization with custom values."""
        client = AltDataStreamClient(
            api_key="test-api-key",
            base_url="wss://custom.example.com",
            max_retries=10,
            retry_delay=2.0,
            retry_backoff=3.0,
            heartbeat_interval=60,
        )

        assert client.base_url == "wss://custom.example.com"
        assert client.max_retries == 10
        assert client.retry_delay == 2.0
        assert client.retry_backoff == 3.0
        assert client.heartbeat_interval == 60

    def test_state_change_callback(self):
        """Test state change callbacks are invoked."""
        client = AltDataStreamClient(api_key="test-api-key")
        states_received = []

        def on_state_change(state):
            states_received.append(state)

        client.on_state_change(on_state_change)
        client._set_state(ConnectionState.CONNECTING)
        client._set_state(ConnectionState.CONNECTED)

        assert states_received == [ConnectionState.CONNECTING, ConnectionState.CONNECTED]

    def test_state_change_callback_no_duplicate(self):
        """Test that same state doesn't trigger callback."""
        client = AltDataStreamClient(api_key="test-api-key")
        states_received = []

        def on_state_change(state):
            states_received.append(state)

        client.on_state_change(on_state_change)
        client._set_state(ConnectionState.CONNECTING)
        client._set_state(ConnectionState.CONNECTING)  # Same state

        assert len(states_received) == 1

    @pytest.mark.asyncio
    async def test_subscribe_adds_to_list(self):
        """Test that subscribe adds subscription to list."""
        client = AltDataStreamClient(api_key="test-api-key")
        callback = AsyncMock()

        # Subscribe without connection (queued for later)
        await client.subscribe(
            factors=["factor_a"],
            tickers=["AAPL"],
            verbosity=VerbosityLevel.FULL,
            callback=callback,
        )

        assert len(client._subscriptions) == 1
        assert client._subscriptions[0].factors == ["factor_a"]
        assert client._subscriptions[0].tickers == ["AAPL"]
        assert callback in client._callbacks

    @pytest.mark.asyncio
    async def test_handle_message_update(self):
        """Test handling update message."""
        client = AltDataStreamClient(api_key="test-api-key")
        received_updates = []

        async def callback(update):
            received_updates.append(update)

        client._callbacks.append(callback)

        await client._handle_message({
            "type": "update",
            "factor_id": "test_factor",
            "ticker": "AAPL",
            "mean": 0.05,
            "timestamp": "2025-01-15T10:00:00Z",
        })

        assert len(received_updates) == 1
        assert received_updates[0].factor_id == "test_factor"
        assert received_updates[0].ticker == "AAPL"
        assert received_updates[0].value == 0.05

    @pytest.mark.asyncio
    async def test_handle_message_heartbeat(self):
        """Test handling heartbeat message (no action)."""
        client = AltDataStreamClient(api_key="test-api-key")

        # Should not raise
        await client._handle_message({"type": "heartbeat"})

    @pytest.mark.asyncio
    async def test_handle_message_error(self):
        """Test handling error message."""
        client = AltDataStreamClient(api_key="test-api-key")

        # Should not raise, just log
        await client._handle_message({
            "type": "error",
            "message": "Test error message",
        })

    @pytest.mark.asyncio
    async def test_disconnect_changes_state(self):
        """Test that disconnect changes state."""
        client = AltDataStreamClient(api_key="test-api-key")
        client._set_state(ConnectionState.CONNECTED)

        await client.disconnect()

        assert client.state == ConnectionState.DISCONNECTED

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager."""
        with patch.object(AltDataStreamClient, 'connect', new_callable=AsyncMock) as mock_connect:
            with patch.object(AltDataStreamClient, 'disconnect', new_callable=AsyncMock) as mock_disconnect:
                mock_connect.return_value = True

                async with AltDataStreamClient(api_key="test") as client:
                    pass

                mock_connect.assert_called_once()
                mock_disconnect.assert_called_once()


class TestAsyncFactorStream:
    """Tests for AsyncFactorStream iterator."""

    def test_initialization(self):
        """Test stream initialization."""
        stream = AsyncFactorStream(
            api_key="test-api-key",
            factors=["factor_a"],
            tickers=["AAPL"],
            verbosity=VerbosityLevel.FULL,
            base_url="wss://test.example.com",
        )

        assert stream.api_key == "test-api-key"
        assert stream.factors == ["factor_a"]
        assert stream.tickers == ["AAPL"]
        assert stream.verbosity == VerbosityLevel.FULL
        assert stream.base_url == "wss://test.example.com"

    @pytest.mark.asyncio
    async def test_on_update_adds_to_queue(self):
        """Test that updates are added to internal queue."""
        stream = AsyncFactorStream(api_key="test")

        update = FactorUpdate(
            factor_id="test",
            ticker="AAPL",
            value=0.05,
            timestamp=datetime.utcnow(),
        )

        await stream._on_update(update)

        # Queue should have the update
        assert not stream._queue.empty()
        queued = await stream._queue.get()
        assert queued.factor_id == "test"


class TestReconnectionLogic:
    """Tests for reconnection behavior."""

    def test_retry_delay_exponential_backoff(self):
        """Test that retry delay increases exponentially."""
        client = AltDataStreamClient(
            api_key="test",
            retry_delay=1.0,
            retry_backoff=2.0,
        )

        # Simulate retry calculations
        delays = []
        for i in range(5):
            delay = client.retry_delay * (client.retry_backoff ** i)
            delays.append(delay)

        assert delays == [1.0, 2.0, 4.0, 8.0, 16.0]

    def test_max_retries_respected(self):
        """Test that max_retries limit is respected."""
        client = AltDataStreamClient(api_key="test", max_retries=3)

        assert client.max_retries == 3

        # After 3 retries, should stop
        client._retry_count = 3
        client._should_reconnect = True

        # Logic check: should not reconnect when retry_count >= max_retries
        should_reconnect = client._should_reconnect and client._retry_count < client.max_retries
        assert not should_reconnect


class TestClientIntegration:
    """Integration-style tests for client behavior."""

    @pytest.mark.asyncio
    async def test_multiple_subscriptions(self):
        """Test handling multiple subscriptions."""
        client = AltDataStreamClient(api_key="test")

        await client.subscribe(factors=["factor_a"], callback=AsyncMock())
        await client.subscribe(factors=["factor_b"], callback=AsyncMock())
        await client.subscribe(tickers=["AAPL"], callback=AsyncMock())

        assert len(client._subscriptions) == 3
        assert len(client._callbacks) == 3

    @pytest.mark.asyncio
    async def test_callback_error_handling(self):
        """Test that callback errors don't break message handling."""
        client = AltDataStreamClient(api_key="test")

        async def bad_callback(update):
            raise ValueError("Callback error")

        good_results = []

        async def good_callback(update):
            good_results.append(update)

        client._callbacks = [bad_callback, good_callback]

        # Should not raise, and good callback should still be called
        await client._handle_message({
            "type": "update",
            "factor_id": "test",
            "ticker": "AAPL",
            "value": 0.05,
            "timestamp": "2025-01-15T10:00:00Z",
        })

        assert len(good_results) == 1
