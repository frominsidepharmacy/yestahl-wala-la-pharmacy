#!/usr/bin/env python3
import json, os, requests
token = os.environ["TELEGRAM_BOT_TOKEN"]
response = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=20)
response.raise_for_status()
print(json.dumps(response.json()["result"], ensure_ascii=False, indent=2))
