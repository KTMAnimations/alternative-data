# TradingView Integration SDK Documentation

This document provides comprehensive documentation for integrating the Alternative Data Platform with TradingView.

## Overview

The TradingView integration enables:
- **Pine Script Generation**: Automatically generate TradingView indicators from platform factors
- **Real-time Data Sync**: Push factor updates to TradingView via webhooks
- **Annotation Import**: Import chart annotations for analysis
- **OAuth Connection**: Connect your TradingView account for seamless sync

## Quick Start

### 1. Generate a Pine Script Indicator

```python
import requests

# Generate Pine Script for a factor
response = requests.post(
    "https://api.altdata.example.com/api/v1/tradingview/tsa_throughput_momentum/pinescript",
    headers={"Authorization": "Bearer YOUR_API_KEY"},
    json={
        "version": "v5",
        "include_webhook": True,
        "overlay": False,
        "show_alerts": True
    }
)

result = response.json()
pine_script = result["pine_script_code"]
instructions = result["setup_instructions"]
```

### 2. Add to TradingView

1. Open TradingView and navigate to any chart
2. Click "Pine Editor" at the bottom
3. Paste the generated code
4. Click "Save" and name your indicator
5. Click "Add to Chart"

## API Reference

### Generate Pine Script

**Endpoint:** `POST /api/v1/tradingview/{factor_id}/pinescript`

Generates Pine Script v5 code for a platform factor.

**Request Body:**
```json
{
    "version": "v5",
    "include_webhook": true,
    "webhook_url": "https://your-webhook.example.com/receive",
    "overlay": false,
    "show_alerts": true,
    "custom_colors": {
        "positive": "#26a69a",
        "negative": "#ef5350",
        "neutral": "#78909c"
    }
}
```

**Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| version | string | "v5" | Pine Script version (v5 or v4) |
| include_webhook | boolean | true | Include webhook integration code |
| webhook_url | string | null | Custom webhook URL for data |
| overlay | boolean | false | Display as chart overlay |
| show_alerts | boolean | true | Include alert conditions |
| custom_colors | object | null | Custom color scheme |

**Response:**
```json
{
    "factor_id": "tsa_throughput_momentum",
    "factor_name": "TSA Throughput Momentum",
    "pine_script_code": "// Pine Script v5...",
    "version": "v5",
    "setup_instructions": [
        "1. Open TradingView...",
        "..."
    ],
    "webhook_url": null,
    "generated_at": "2025-01-20T10:30:00Z"
}
```

### Push Factor Data via Webhook

**Endpoint:** `POST /api/v1/tradingview/webhook/push`

Push real-time factor updates to TradingView.

**Request Body:**
```json
{
    "factor_id": "tsa_throughput_momentum",
    "tickers": ["DAL", "UAL", "AAL"],
    "webhook_secret": "your-secure-webhook-secret"
}
```

**Response:**
```json
{
    "status": "queued",
    "factor_id": "tsa_throughput_momentum",
    "tickers_pushed": ["DAL", "UAL", "AAL"],
    "timestamp": "2025-01-20T10:30:00Z",
    "next_push_scheduled": null
}
```

### Import Annotations

**Endpoint:** `POST /api/v1/tradingview/annotations/import`

Import chart annotations from TradingView.

**Request Body:**
```json
{
    "chart_id": "AAPL-daily-123",
    "annotation_types": ["horizontal_line", "trend_line", "label"],
    "ticker": "AAPL",
    "start_date": "2025-01-01T00:00:00Z",
    "end_date": "2025-01-20T00:00:00Z"
}
```

**Annotation Types:**
- `horizontal_line`
- `vertical_line`
- `trend_line`
- `text`
- `shape`
- `label`

**Response:**
```json
{
    "chart_id": "AAPL-daily-123",
    "ticker": "AAPL",
    "annotations": [
        {
            "id": "ann_001",
            "type": "horizontal_line",
            "timestamp": "2025-01-15T00:00:00Z",
            "price_level": 185.50,
            "text": "Support Level",
            "color": "#26a69a",
            "metadata": {}
        }
    ],
    "total_count": 1,
    "imported_at": "2025-01-20T10:30:00Z"
}
```

### OAuth Connection

#### Initialize OAuth Flow

**Endpoint:** `POST /api/v1/tradingview/oauth/init`

Start OAuth 2.0 authorization flow.

**Request Body:**
```json
{
    "redirect_uri": "https://your-app.example.com/callback",
    "scopes": ["chart:read", "chart:write"]
}
```

**Available Scopes:**
- `chart:read` - Read chart data and annotations
- `chart:write` - Create and modify chart elements
- `alert:read` - Read user alerts
- `alert:write` - Create and modify alerts

**Response:**
```json
{
    "authorization_url": "https://www.tradingview.com/oauth/authorize?...",
    "state": "abc123xyz",
    "expires_at": "2025-01-20T11:30:00Z"
}
```

#### Handle OAuth Callback

**Endpoint:** `POST /api/v1/tradingview/oauth/callback`

Exchange authorization code for tokens.

**Request Body:**
```json
{
    "code": "authorization_code_from_tradingview",
    "state": "abc123xyz"
}
```

#### Check Connection Status

**Endpoint:** `GET /api/v1/tradingview/connection/status`

**Response:**
```json
{
    "status": "connected",
    "connected_at": "2025-01-15T08:00:00Z",
    "last_sync": "2025-01-20T10:00:00Z",
    "scopes": ["chart:read", "chart:write"],
    "username": "trader123"
}
```

#### Disconnect Account

**Endpoint:** `DELETE /api/v1/tradingview/connection`

**Response:**
```json
{
    "status": "disconnected",
    "message": "TradingView account disconnected"
}
```

### Get Webhook Configuration

**Endpoint:** `GET /api/v1/tradingview/webhook/{factor_id}/config`

Get webhook setup details for a factor.

**Response:**
```json
{
    "factor_id": "tsa_throughput_momentum",
    "factor_name": "TSA Throughput Momentum",
    "webhook_url": "https://api.altdata.example.com/api/v1/tradingview/webhook/tsa_throughput_momentum",
    "json_template": {
        "factor_id": "tsa_throughput_momentum",
        "ticker": "{{ticker}}",
        "exchange": "{{exchange}}",
        "time": "{{timenow}}",
        "interval": "{{interval}}",
        "factor_value": "{{plot('Factor Value')}}",
        "alert_type": "{{strategy.order.action}}"
    },
    "instructions": [
        "1. Open your TradingView chart with the factor indicator",
        "2. Create a new Alert (Alt+A)",
        "..."
    ]
}
```

## Pine Script Features

### Generated Indicator Structure

The generated Pine Script includes:

1. **Configuration Section**
   - Factor ID and API endpoint
   - User-configurable display settings
   - Alert threshold settings
   - Custom colors

2. **Data Variables**
   - Factor mean and variance storage
   - Historical data arrays
   - Z-score calculations

3. **Visualization**
   - Factor value plot with dynamic coloring
   - Confidence bands (mean +/- 2 std dev)
   - Background highlighting for strong signals
   - Value labels

4. **Alert Conditions**
   - Strong positive signal (z-score crosses threshold)
   - Strong negative signal (z-score crosses -threshold)
   - Factor crosses zero

5. **Webhook Integration**
   - Endpoint URL
   - JSON template for alert messages
   - Setup instructions

### Customization Options

#### Colors

```json
{
    "custom_colors": {
        "positive": "#00ff00",
        "negative": "#ff0000",
        "neutral": "#808080"
    }
}
```

#### Overlay vs Separate Panel

```json
{
    "overlay": true  // Draws on price chart
}

{
    "overlay": false  // Draws in separate panel (default)
}
```

#### Alert Threshold

Configured within the Pine Script via input:
```pinescript
alertThreshold = input.float(2.0, "Alert Threshold (Std Dev)", minval=0.5, maxval=5.0)
```

## Webhook Integration

### Setting Up Real-time Updates

1. **Generate Pine Script with webhook enabled:**
   ```python
   response = requests.post(
       f"{API_BASE}/tradingview/{factor_id}/pinescript",
       json={"include_webhook": True}
   )
   ```

2. **Add indicator to TradingView**

3. **Configure webhook alert:**
   - Create alert in TradingView
   - Set your webhook URL
   - Use the JSON template from the generated script

4. **Receive updates:**
   Your webhook endpoint will receive POST requests with:
   ```json
   {
       "factor_id": "tsa_throughput_momentum",
       "ticker": "DAL",
       "exchange": "NYSE",
       "time": "2025-01-20T10:30:00Z",
       "factor_value": 0.045
   }
   ```

### Security

- Always validate webhook payloads
- Use HTTPS for webhook endpoints
- Store webhook secrets securely
- Implement rate limiting on your webhook receiver

## Error Codes

| Code | Description |
|------|-------------|
| 400 | Invalid request parameters |
| 401 | Authentication required |
| 403 | Insufficient permissions |
| 404 | Factor not found |
| 422 | Validation error |
| 429 | Rate limit exceeded |
| 500 | Internal server error |
| 501 | Feature not implemented |

## Rate Limits

| Endpoint | Limit |
|----------|-------|
| Pine Script generation | 100/hour |
| Webhook push | 1000/hour |
| Annotation import | 50/hour |
| OAuth operations | 10/hour |

## Examples

### Python SDK Example

```python
from altdata import Client

client = Client(api_key="YOUR_API_KEY")

# Generate Pine Script
pinescript = client.tradingview.generate_pinescript(
    factor_id="tsa_throughput_momentum",
    version="v5",
    include_webhook=True,
    overlay=False
)

print(pinescript.code)
for instruction in pinescript.setup_instructions:
    print(instruction)

# Check connection status
status = client.tradingview.connection_status()
print(f"Connected: {status.status}")
```

### cURL Examples

```bash
# Generate Pine Script
curl -X POST "https://api.altdata.example.com/api/v1/tradingview/tsa_throughput_momentum/pinescript" \
    -H "Authorization: Bearer YOUR_API_KEY" \
    -H "Content-Type: application/json" \
    -d '{"version": "v5", "include_webhook": true}'

# Get webhook configuration
curl "https://api.altdata.example.com/api/v1/tradingview/webhook/tsa_throughput_momentum/config" \
    -H "Authorization: Bearer YOUR_API_KEY"

# Push factor data
curl -X POST "https://api.altdata.example.com/api/v1/tradingview/webhook/push" \
    -H "Authorization: Bearer YOUR_API_KEY" \
    -H "Content-Type: application/json" \
    -d '{"factor_id": "tsa_throughput_momentum", "tickers": ["DAL"], "webhook_secret": "your-secret"}'
```

## Support

- **Documentation**: https://docs.altdata.example.com/tradingview
- **API Status**: https://status.altdata.example.com
- **Support Email**: support@altdata.example.com
- **GitHub Issues**: https://github.com/altdata/platform/issues

---

*Last Updated: January 2025*
