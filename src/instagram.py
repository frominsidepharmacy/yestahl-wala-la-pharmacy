from __future__ import annotations
import os
import time
from typing import Dict, List, Optional
import requests


class InstagramPublisher:
    ALLOWED_GRAPH_HOSTS = {"graph.instagram.com", "graph.facebook.com"}

    def __init__(self, access_token=None, user_id=None, api_version=None, session=None, graph_host=None):
        self.token = access_token or os.getenv("META_ACCESS_TOKEN")
        self.user_id = user_id or os.getenv("INSTAGRAM_USER_ID")
        self.version = api_version or os.getenv("META_API_VERSION")
        self.graph_host = graph_host or os.getenv("META_GRAPH_HOST", "graph.facebook.com")
        if not self.token or not self.user_id or not self.version:
            raise RuntimeError("META_ACCESS_TOKEN, INSTAGRAM_USER_ID and META_API_VERSION are required")
        if not self.version.startswith("v"):
            raise ValueError("META_API_VERSION must look like vNN.0")
        if self.graph_host not in self.ALLOWED_GRAPH_HOSTS:
            raise ValueError("META_GRAPH_HOST must be graph.instagram.com or graph.facebook.com")
        self.base = f"https://{self.graph_host}/{self.version}"
        self.session = session or requests.Session()

    def _post(self, path: str, data: Dict) -> Dict:
        response = self.session.post(f"{self.base}/{path}", data={**data, "access_token": self.token}, timeout=30)
        if response.status_code >= 400:
            raise RuntimeError(
                f"Instagram API POST {path} failed ({response.status_code}): "
                f"{getattr(response, 'text', '')[:1000]}"
            )
        return response.json()

    def _get(self, path: str, params: Dict) -> Dict:
        response = self.session.get(f"{self.base}/{path}", params={**params, "access_token": self.token}, timeout=30)
        if response.status_code >= 400:
            raise RuntimeError(
                f"Instagram API GET {path} failed ({response.status_code}): "
                f"{getattr(response, 'text', '')[:1000]}"
            )
        return response.json()

    def validate_account(self) -> Dict:
        if self.graph_host == "graph.instagram.com":
            account = self._get("me", {"fields": "id,username"})
            if str(account.get("id")) != str(self.user_id):
                received_id = account.get("id", "unknown")
                received_username = account.get("username", "unknown")
                raise RuntimeError(
                    "Instagram account mismatch: "
                    f"expected id {self.user_id}, received @{received_username} ({received_id})"
                )
            return account
        return self._get(self.user_id, {"fields": "id,username,account_type"})

    def find_by_caption_marker(self, marker: str) -> Optional[Dict]:
        page = self._get(f"{self.user_id}/media", {"fields": "id,caption,permalink,timestamp", "limit": 50})
        for item in page.get("data", []):
            if marker in (item.get("caption") or ""):
                return item
        return None

    def create_child(self, image_url: str) -> str:
        return self._post(f"{self.user_id}/media", {"image_url": image_url, "is_carousel_item": "true"})["id"]

    def wait_ready(self, container_id: str, timeout: int = 180) -> str:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            status = self._get(container_id, {"fields": "status_code"}).get("status_code")
            if status == "FINISHED":
                return status
            if status in {"ERROR", "EXPIRED"}:
                raise RuntimeError(f"Instagram container {container_id} ended with {status}")
            time.sleep(5)
        raise TimeoutError(f"Instagram container {container_id} not ready")

    def create_carousel(self, child_ids: List[str], caption: str) -> str:
        if not 2 <= len(child_ids) <= 10:
            raise ValueError("Instagram carousel requires 2-10 items")
        return self._post(f"{self.user_id}/media", {"media_type": "CAROUSEL", "children": ",".join(child_ids), "caption": caption})["id"]

    def publish(self, creation_id: str) -> str:
        return self._post(f"{self.user_id}/media_publish", {"creation_id": creation_id})["id"]

    def permalink(self, media_id: str) -> Optional[str]:
        return self._get(media_id, {"fields": "id,permalink"}).get("permalink")
