import json
from pathlib import Path
import pytest
from src.instagram import InstagramPublisher
from src.models import Product, STATUSES
from src.publishing import prepare_approved_site, validate_public_urls
from src.approval import freeze_manifest


class Response:
    def __init__(self, payload, status=200, content_type="application/json"):
        self.payload, self.status_code, self.headers = payload, status, {"content-type": content_type}
    def raise_for_status(self):
        if self.status_code >= 400: raise RuntimeError(self.status_code)
    def json(self): return self.payload


class Session:
    def __init__(self): self.calls = []
    def post(self, url, data, timeout): self.calls.append(("POST", url, data)); return Response({"id": "container-1"})
    def get(self, url, params, timeout):
        self.calls.append(("GET", url, params))
        if params.get("fields") == "status_code": return Response({"status_code": "FINISHED"})
        if url.endswith("/media"): return Response({"data": []})
        return Response({"id": "media-1", "permalink": "https://instagram.com/p/x"})


def test_instagram_child_payload():
    s = Session(); api = InstagramPublisher("token", "ig", "v99.0", s)
    api.create_child("https://pages/1.png")
    assert s.calls[0][2]["is_carousel_item"] == "true"


def test_instagram_carousel_payload():
    s = Session(); api = InstagramPublisher("token", "ig", "v99.0", s)
    api.create_carousel(["1", "2"], "caption")
    assert s.calls[0][2]["media_type"] == "CAROUSEL" and s.calls[0][2]["children"] == "1,2"


def test_instagram_rejects_invalid_carousel_count():
    with pytest.raises(ValueError): InstagramPublisher("t", "i", "v99.0", Session()).create_carousel(["1"], "c")


def test_instagram_version_is_configurable():
    with pytest.raises(ValueError): InstagramPublisher("t", "i", "99", Session())


def test_instagram_login_uses_instagram_graph_host():
    session = Session()
    api = InstagramPublisher("token", "media-1", "v23.0", session, "graph.instagram.com")
    assert api.base == "https://graph.instagram.com/v23.0"
    assert api.validate_account()["id"] == "media-1"
    assert session.calls[-1][1].endswith("/me")


def test_instagram_rejects_untrusted_graph_host():
    with pytest.raises(ValueError):
        InstagramPublisher("token", "ig", "v23.0", Session(), "example.com")


def test_pages_url_validation():
    class S:
        def head(self, url, timeout, allow_redirects): return Response({}, 200, "image/png")
    validate_public_urls(["https://pages/1.png"], S())


def test_pages_url_failure_safe():
    class S:
        def head(self, url, timeout, allow_redirects): return Response({}, 404, "text/html")
    with pytest.raises(RuntimeError): validate_public_urls(["https://pages/missing.png"], S())


def test_approved_site_hash_gate(tmp_path):
    pending, site = tmp_path / "pending", tmp_path / "site"; pending.mkdir()
    slides = []
    for i in range(6):
        p = pending / f"slide{i+1:02}.png"; p.write_bytes(str(i).encode()); slides.append(p)
    manifest = freeze_manifest(pending, slides, "cap", {"product": {"product_id": "abc"}})
    target = prepare_approved_site(pending, site, "key", manifest["content_hash"])
    assert len(list(target.glob("*.png"))) == 6


def test_approved_site_rejects_changed_asset(tmp_path):
    pending = tmp_path / "pending"; pending.mkdir(); slides=[]
    for i in range(6):
        p=pending/f"slide{i}.png"; p.write_bytes(b"x"); slides.append(p)
    manifest=freeze_manifest(pending,slides,"cap",{})
    slides[0].write_bytes(b"y")
    with pytest.raises(RuntimeError): prepare_approved_site(pending,tmp_path/"site","key",manifest["content_hash"])


def test_status_enum_complete():
    expected = {"DISCOVERED","RESEARCHING","REJECTED_DATA","REJECTED_EVIDENCE","DRAFTING","QC","PENDING_APPROVAL","EDIT_REQUESTED","REJECTED_USER","APPROVED","PUBLISHING","PUBLISHED","PUBLISH_FAILED_SAFE"}
    assert STATUSES == expected


def test_activepieces_routes_complete():
    spec = json.loads((Path(__file__).parents[1]/"activepieces/flow_configuration.json").read_text())
    blob = json.dumps(spec)
    assert all(action in blob for action in ("approve:", "edit:", "regenerate:", "reject:", "approve_all:"))


def test_schedule_timezone_and_time():
    text = (Path(__file__).parents[1]/".github/workflows/daily.yml").read_text()
    # GitHub evaluates cron in UTC. These are 12:00, 17:00 and 22:00 Dubai.
    assert all(f'cron: "0 {hour} * * *"' in text for hour in (8, 13, 18))
    assert "Asia/Dubai" in text
    assert all(category in text for category in ("korean_skincare", "vitamins_supplements", "personal_care"))


def test_zero_cost_guardrails_are_permanent():
    text = (Path(__file__).parents[1]/"config/settings.yaml").read_text()
    assert "allow_paid_services: false" in text and "require_manual_approval: true" in text and "free_ai_enabled: false" in text
