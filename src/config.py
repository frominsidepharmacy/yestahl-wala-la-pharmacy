from pathlib import Path
import os
import yaml

ROOT = Path(__file__).resolve().parents[1]


def load_yaml(name: str):
    with (ROOT / "config" / name).open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def assert_guardrails() -> None:
    settings = load_yaml("settings.yaml")["guardrails"]
    paid = os.getenv("ALLOW_PAID_SERVICES", str(settings["allow_paid_services"])).lower()
    approval = os.getenv("REQUIRE_MANUAL_APPROVAL", str(settings["require_manual_approval"])).lower()
    ai = os.getenv("FREE_AI_ENABLED", str(settings["free_ai_enabled"])).lower()
    if paid != "false" or approval != "true" or ai != "false":
        raise RuntimeError("Permanent safety settings violated: paid=false, manual approval=true, AI=false required")

