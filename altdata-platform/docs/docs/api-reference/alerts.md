# Alerts API

The Alerts API allows you to create and manage alert rules that trigger notifications when factor values meet specified conditions.

## Overview

Alert rules monitor factor values and trigger notifications via Slack, Email, or Webhooks when conditions are met. The system supports:

- **Simple thresholds**: Greater than, less than, equal to
- **Statistical alerts**: Z-score based anomaly detection
- **Percent change alerts**: Detect significant changes over time
- **Cooldown periods**: Prevent duplicate notifications

---

## Endpoints

### Create Alert Rule

Create a new alert rule.

```
POST /api/v1/alerts/rules
```

**Request Body:**

```json
{
  "name": "AAPL Insider Buying Alert",
  "description": "Alert when insider buying momentum exceeds threshold",
  "factor_name": "insider_transaction_momentum",
  "entity_id": "AAPL",
  "condition": "gt",
  "threshold": 1000.0,
  "lookback_days": 30,
  "notification_channel": "slack",
  "notification_config": "{\"webhook_url\": \"https://hooks.slack.com/services/...\"}",
  "cooldown_minutes": 60
}
```

**Parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Rule name (1-100 chars) |
| `description` | string | No | Rule description (max 500 chars) |
| `factor_name` | string | Yes | Factor to monitor |
| `entity_id` | string | No | Entity to monitor (null = all entities) |
| `condition` | string | Yes | Alert condition (see below) |
| `threshold` | float | Yes | Threshold value |
| `lookback_days` | int | No | Days for z-score/pct_change (default: 30) |
| `notification_channel` | string | No | Channel: `slack`, `email`, `webhook` |
| `notification_config` | string | No | JSON config for channel |
| `cooldown_minutes` | int | No | Minutes between alerts (default: 60) |

**Condition Types:**

| Condition | Description |
|-----------|-------------|
| `gt` | Factor value greater than threshold |
| `lt` | Factor value less than threshold |
| `eq` | Factor value equal to threshold |
| `zscore_gt` | Z-score greater than threshold |
| `zscore_lt` | Z-score less than threshold |
| `pct_change_gt` | Percent change greater than threshold |
| `pct_change_lt` | Percent change less than threshold |

**Response:** `201 Created`

```json
{
  "id": 1,
  "name": "AAPL Insider Buying Alert",
  "description": "Alert when insider buying momentum exceeds threshold",
  "factor_name": "insider_transaction_momentum",
  "entity_id": "AAPL",
  "condition": "gt",
  "threshold": 1000.0,
  "lookback_days": 30,
  "is_active": true,
  "notification_channel": "slack",
  "notification_config": "{\"webhook_url\": \"https://hooks.slack.com/services/...\"}",
  "cooldown_minutes": 60,
  "created_by": null,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

---

### List Alert Rules

List all alert rules with optional filtering.

```
GET /api/v1/alerts/rules
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `is_active` | boolean | Filter by active status |
| `factor_name` | string | Filter by factor name |

**Response:** `200 OK`

```json
{
  "rules": [
    {
      "id": 1,
      "name": "AAPL Insider Buying Alert",
      "factor_name": "insider_transaction_momentum",
      "entity_id": "AAPL",
      "condition": "gt",
      "threshold": 1000.0,
      "is_active": true,
      "created_at": "2024-01-15T10:30:00Z"
    }
  ],
  "total": 1
}
```

---

### Get Alert Rule

Get a specific alert rule by ID.

```
GET /api/v1/alerts/rules/{rule_id}
```

**Response:** `200 OK`

Returns the full alert rule object.

---

### Update Alert Rule

Update an existing alert rule.

```
PUT /api/v1/alerts/rules/{rule_id}
```

**Request Body:**

All fields are optional. Only provided fields will be updated.

```json
{
  "threshold": 1500.0,
  "is_active": false
}
```

**Response:** `200 OK`

Returns the updated alert rule object.

---

### Delete Alert Rule

Delete an alert rule.

```
DELETE /api/v1/alerts/rules/{rule_id}
```

**Response:** `204 No Content`

---

### List Notifications

List triggered alert notifications.

```
GET /api/v1/alerts/notifications
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `rule_id` | int | Filter by rule ID |
| `entity_id` | string | Filter by entity |
| `status` | string | Filter by status: `pending`, `sent`, `failed` |
| `start_date` | datetime | Filter by trigger date (from) |
| `end_date` | datetime | Filter by trigger date (to) |
| `page` | int | Page number (default: 1) |
| `page_size` | int | Items per page (default: 50, max: 100) |

**Response:** `200 OK`

```json
{
  "notifications": [
    {
      "id": 1,
      "rule_id": 1,
      "entity_id": "AAPL",
      "factor_value": 1523.45,
      "threshold": 1000.0,
      "computed_value": null,
      "triggered_at": "2024-01-15T14:30:00Z",
      "notified_at": "2024-01-15T14:30:05Z",
      "notification_channel": "slack",
      "notification_status": "sent",
      "error_message": null
    }
  ],
  "total": 1
}
```

---

### Trigger Alert Check

Manually trigger a check of all active alert rules.

```
POST /api/v1/alerts/check
```

**Response:** `202 Accepted`

```json
{
  "status": "completed",
  "alerts_triggered": 2,
  "details": [
    {
      "rule_id": 1,
      "entity_id": "AAPL",
      "factor_value": 1523.45
    },
    {
      "rule_id": 3,
      "entity_id": "MSFT",
      "factor_value": 2.34
    }
  ]
}
```

---

## Notification Channels

### Slack

Send notifications to a Slack channel via webhook.

**Configuration:**

```json
{
  "webhook_url": "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXX"
}
```

### Email

Send notifications via SMTP email.

**Configuration:**

```json
{
  "smtp_host": "smtp.gmail.com",
  "smtp_port": 587,
  "smtp_user": "alerts@example.com",
  "smtp_password": "app-password",
  "from_address": "alerts@example.com",
  "to_addresses": ["user1@example.com", "user2@example.com"]
}
```

### Webhook

Send notifications to a custom webhook endpoint.

**Configuration:**

```json
{
  "url": "https://api.example.com/alerts",
  "headers": {
    "Authorization": "Bearer your-token"
  }
}
```

---

## Examples

### Create a Z-Score Alert

Alert when a factor's z-score exceeds 2 standard deviations:

```bash
curl -X POST "https://api.altdata.example.com/api/v1/alerts/rules" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Unusual Insider Activity",
    "factor_name": "insider_transaction_momentum",
    "condition": "zscore_gt",
    "threshold": 2.0,
    "lookback_days": 60,
    "notification_channel": "slack",
    "notification_config": "{\"webhook_url\": \"https://hooks.slack.com/...\"}"
  }'
```

### Monitor All Entities

Create a rule without `entity_id` to monitor all entities:

```bash
curl -X POST "https://api.altdata.example.com/api/v1/alerts/rules" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Market-Wide Sentiment Drop",
    "factor_name": "ticker_sentiment",
    "condition": "lt",
    "threshold": -0.5,
    "notification_channel": "email",
    "notification_config": "{\"smtp_host\": \"smtp.gmail.com\", ...}"
  }'
```

### Python SDK Example

```python
from altdata import AltDataClient

client = AltDataClient(api_key="your-api-key")

# Create an alert rule
rule = client.create_alert_rule(
    name="AAPL Insider Alert",
    factor_name="insider_transaction_momentum",
    entity_id="AAPL",
    condition="gt",
    threshold=1000.0,
    notification_channel="slack",
    notification_config={"webhook_url": "https://hooks.slack.com/..."}
)

# List notifications
notifications = client.list_alert_notifications(rule_id=rule.id)
for n in notifications:
    print(f"Alert triggered: {n.entity_id} = {n.factor_value}")
```
