#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from urllib.parse import urlparse

import requests


def main() -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    response = requests.get(
        f"https://api.telegram.org/bot{token}/getWebhookInfo",
        timeout=20,
    )
    response.raise_for_status()
    result = response.json()["result"]
    webhook_url = result.get("url", "")
    print(json.dumps({
        "webhook_configured": bool(webhook_url),
        "webhook_host": urlparse(webhook_url).hostname if webhook_url else None,
        "pending_update_count": result.get("pending_update_count", 0),
        "last_error_date": result.get("last_error_date"),
        "last_error_message": result.get("last_error_message"),
        "allowed_updates": result.get("allowed_updates"),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
