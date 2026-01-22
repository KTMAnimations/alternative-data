"""Notification channels for alerts."""

import json
import logging
from abc import ABC, abstractmethod
from typing import Optional

import httpx

from .models import NotificationChannel

logger = logging.getLogger(__name__)


class BaseNotifier(ABC):
    """Base class for notification channels."""

    @abstractmethod
    def send(self, message: dict) -> bool:
        """Send a notification.

        Args:
            message: Message dictionary with alert details.

        Returns:
            True if sent successfully, False otherwise.
        """
        pass


class SlackNotifier(BaseNotifier):
    """Slack webhook notifier."""

    def __init__(self, webhook_url: str):
        """Initialize Slack notifier.

        Args:
            webhook_url: Slack webhook URL.
        """
        self.webhook_url = webhook_url

    def send(self, message: dict) -> bool:
        """Send notification to Slack."""
        try:
            # Format Slack message
            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f":bell: {message['title']}",
                    },
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*Factor:*\n{message['factor_name']}",
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Entity:*\n{message['entity_id']}",
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Current Value:*\n{message['current_value']:.4f}",
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Threshold ({message['condition']}):*\n{message['threshold']}",
                        },
                    ],
                },
            ]

            if message.get("computed_value") is not None:
                blocks.append(
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*Computed Value:* {message['computed_value']:.4f}",
                        },
                    }
                )

            if message.get("description"):
                blocks.append(
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": message["description"],
                            }
                        ],
                    }
                )

            payload = {"blocks": blocks}

            response = httpx.post(
                self.webhook_url,
                json=payload,
                timeout=10.0,
            )
            response.raise_for_status()

            logger.info(f"Slack notification sent for {message['rule_name']}")
            return True

        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")
            return False


class EmailNotifier(BaseNotifier):
    """Email notifier using SMTP or SES."""

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        smtp_user: str,
        smtp_password: str,
        from_address: str,
        to_addresses: list,
    ):
        """Initialize email notifier.

        Args:
            smtp_host: SMTP server hostname.
            smtp_port: SMTP server port.
            smtp_user: SMTP username.
            smtp_password: SMTP password.
            from_address: Sender email address.
            to_addresses: List of recipient email addresses.
        """
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.from_address = from_address
        self.to_addresses = to_addresses

    def send(self, message: dict) -> bool:
        """Send notification via email."""
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"AltData Alert: {message['title']}"
            msg["From"] = self.from_address
            msg["To"] = ", ".join(self.to_addresses)

            # Plain text version
            text = f"""
Alert: {message['title']}

Factor: {message['factor_name']}
Entity: {message['entity_id']}
Condition: {message['condition']}
Threshold: {message['threshold']}
Current Value: {message['current_value']}
Triggered At: {message['triggered_at']}

{message.get('description', '')}
"""

            # HTML version
            html = f"""
<html>
<body>
<h2>{message['title']}</h2>
<table>
<tr><td><strong>Factor:</strong></td><td>{message['factor_name']}</td></tr>
<tr><td><strong>Entity:</strong></td><td>{message['entity_id']}</td></tr>
<tr><td><strong>Condition:</strong></td><td>{message['condition']}</td></tr>
<tr><td><strong>Threshold:</strong></td><td>{message['threshold']}</td></tr>
<tr><td><strong>Current Value:</strong></td><td>{message['current_value']:.4f}</td></tr>
<tr><td><strong>Triggered At:</strong></td><td>{message['triggered_at']}</td></tr>
</table>
<p>{message.get('description', '')}</p>
</body>
</html>
"""

            msg.attach(MIMEText(text, "plain"))
            msg.attach(MIMEText(html, "html"))

            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.sendmail(
                    self.from_address, self.to_addresses, msg.as_string()
                )

            logger.info(f"Email notification sent for {message['rule_name']}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")
            return False


class WebhookNotifier(BaseNotifier):
    """Generic webhook notifier."""

    def __init__(self, url: str, headers: Optional[dict] = None):
        """Initialize webhook notifier.

        Args:
            url: Webhook URL.
            headers: Optional headers to include in request.
        """
        self.url = url
        self.headers = headers or {}

    def send(self, message: dict) -> bool:
        """Send notification via webhook."""
        try:
            headers = {
                "Content-Type": "application/json",
                **self.headers,
            }

            response = httpx.post(
                self.url,
                json=message,
                headers=headers,
                timeout=10.0,
            )
            response.raise_for_status()

            logger.info(f"Webhook notification sent for {message['rule_name']}")
            return True

        except Exception as e:
            logger.error(f"Failed to send webhook notification: {e}")
            return False


def get_notifier(channel: NotificationChannel, config: Optional[str]) -> BaseNotifier:
    """Get a notifier instance for the specified channel.

    Args:
        channel: Notification channel type.
        config: JSON configuration string for the notifier.

    Returns:
        Configured notifier instance.

    Raises:
        ValueError: If channel is not supported or config is invalid.
    """
    config_dict = json.loads(config) if config else {}

    if channel == NotificationChannel.SLACK:
        if "webhook_url" not in config_dict:
            raise ValueError("Slack notifier requires webhook_url in config")
        return SlackNotifier(config_dict["webhook_url"])

    elif channel == NotificationChannel.EMAIL:
        required = ["smtp_host", "smtp_port", "smtp_user", "smtp_password", "from_address", "to_addresses"]
        if not all(k in config_dict for k in required):
            raise ValueError(f"Email notifier requires: {required}")
        return EmailNotifier(**config_dict)

    elif channel == NotificationChannel.WEBHOOK:
        if "url" not in config_dict:
            raise ValueError("Webhook notifier requires url in config")
        return WebhookNotifier(
            config_dict["url"],
            config_dict.get("headers"),
        )

    else:
        raise ValueError(f"Unsupported notification channel: {channel}")
