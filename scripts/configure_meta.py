#!/usr/bin/env python3
import json
import requests
from src.instagram import InstagramPublisher

try:
    print(json.dumps(InstagramPublisher().validate_account(), indent=2))
except requests.HTTPError as exc:
    response = exc.response
    try:
        details = response.json()
    except ValueError:
        details = {"error": {"message": "Meta returned a non-JSON error", "status": response.status_code}}
    print(json.dumps(details, indent=2))
    raise SystemExit(1)
