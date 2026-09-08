#!/usr/bin/env python3
import json, os
from pathlib import Path

spec = json.loads(Path("activepieces/flow_configuration.json").read_text(encoding="utf-8"))
required = ["ACTIVEPIECES_API_KEY", "ACTIVEPIECES_PROJECT_ID", "GITHUB_REPOSITORY"]
missing = [name for name in required if not os.getenv(name)]
payload = {"projectId": os.getenv("ACTIVEPIECES_PROJECT_ID", "<PROJECT_ID>"), "displayName": spec["displayName"], "definition": spec}
print(json.dumps({"endpoint": f"{os.getenv('ACTIVEPIECES_API_URL', 'https://cloud.activepieces.com/api/v1')}/flows", "method": "POST", "authorization": "Bearer <ACTIVEPIECES_API_KEY>", "payload": payload, "missing": missing}, ensure_ascii=False, indent=2))
if missing:
    raise SystemExit("Needs Activepieces account authorization: " + ", ".join(missing))
