#!/usr/bin/env python3
import json
from src.pipeline import live_dry_run

if __name__ == "__main__":
    print(json.dumps(live_dry_run(), ensure_ascii=False, indent=2))
