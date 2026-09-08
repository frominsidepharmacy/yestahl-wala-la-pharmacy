from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Dict, List, Optional
import requests


def authorized_user(update: Dict, allowed_user_id: str) -> bool:
    actor = (update.get("callback_query") or {}).get("from") or (update.get("message") or {}).get("from") or {}
    return str(actor.get("id", "")) == str(allowed_user_id)


def callback_data(action: str, publication_key: str, version: int, content_hash: str, artifact_run_id: str = "0") -> str:
    value = f"{action}:{publication_key}:v{version}:{content_hash[:12]}:{artifact_run_id}"
    if len(value.encode()) > 64:
        raise ValueError("Telegram callback_data exceeds 64 bytes")
    return value


def parse_callback(value: str) -> Dict:
    action, key, version, digest, run_id = value.split(":", 4)
    if action not in {"approve", "edit", "regenerate", "reject", "approve_all"}:
        raise ValueError("unknown callback action")
    return {"action": action, "publication_key": key, "version": int(version.removeprefix("v")), "hash_prefix": digest, "artifact_run_id": run_id}


class TelegramClient:
    def __init__(self, token: Optional[str] = None, chat_id: Optional[str] = None):
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
        if not self.token or not self.chat_id:
            raise RuntimeError("Telegram credentials required")
        self.api = f"https://api.telegram.org/bot{self.token}"

    def call(self, method: str, **data):
        response = requests.post(f"{self.api}/{method}", json=data, timeout=30)
        response.raise_for_status()
        payload = response.json()
        if not payload.get("ok"):
            raise RuntimeError(f"Telegram API error: {payload.get('description')}")
        return payload["result"]

    def send_preview(self, slide_urls: List[str], control_text: str, caption: str, keyboard: Dict):
        media = [{"type": "photo", "media": url} for url in slide_urls]
        self.call("sendMediaGroup", chat_id=self.chat_id, media=media)
        return self.call("sendMessage", chat_id=self.chat_id, text=f"{control_text}\n\n{caption}", reply_markup=keyboard, disable_web_page_preview=True)

    def send_preview_files(self, slide_paths: List[Path], control_text: str, caption: str, keyboard: Dict):
        media, files = [], {}
        for index, path in enumerate(slide_paths):
            key = f"slide{index}"
            media.append({"type": "photo", "media": f"attach://{key}"})
            files[key] = (path.name, path.read_bytes(), "image/png")
        response = requests.post(f"{self.api}/sendMediaGroup", data={"chat_id": self.chat_id, "media": json.dumps(media)}, files=files, timeout=60)
        response.raise_for_status()
        if not response.json().get("ok"):
            raise RuntimeError(response.json().get("description"))
        return self.call("sendMessage", chat_id=self.chat_id, text=f"{control_text}\n\n{caption}", reply_markup=keyboard, disable_web_page_preview=True)


def inline_keyboard(key: str, version: int, digest: str, artifact_run_id: str = "0") -> Dict:
    return {"inline_keyboard": [
        [{"text": "✅ APPROVE & PUBLISH", "callback_data": callback_data("approve", key, version, digest, artifact_run_id)}],
        [{"text": "✏️ EDIT", "callback_data": callback_data("edit", key, version, digest, artifact_run_id)},
         {"text": "🔄 REGENERATE", "callback_data": callback_data("regenerate", key, version, digest, artifact_run_id)}],
        [{"text": "❌ REJECT", "callback_data": callback_data("reject", key, version, digest, artifact_run_id)}],
    ]}
