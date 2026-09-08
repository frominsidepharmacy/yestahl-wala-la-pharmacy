#!/usr/bin/env python3
import json, os
from src.config import assert_guardrails, load_yaml

assert_guardrails()
checks = {
    "guardrails": "ok",
    "telegram": "configured" if os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_ALLOWED_USER_ID") else "needs auth",
    "activepieces": "configured" if os.getenv("ACTIVEPIECES_API_KEY") else "needs auth",
    "instagram": "configured" if all(os.getenv(k) for k in ("META_ACCESS_TOKEN", "INSTAGRAM_USER_ID", "META_API_VERSION")) else "needs auth",
    "branding": load_yaml("settings.yaml")["brand"],
}
print(json.dumps(checks, ensure_ascii=False, indent=2))

