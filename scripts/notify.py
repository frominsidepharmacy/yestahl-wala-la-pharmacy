#!/usr/bin/env python3
import os

from src.telegram import TelegramClient


message = os.environ.get("NOTIFICATION_MESSAGE", "").strip()
if not message:
    raise SystemExit("NOTIFICATION_MESSAGE is required")
TelegramClient().call("sendMessage", chat_id=os.environ["TELEGRAM_CHAT_ID"], text=message)
