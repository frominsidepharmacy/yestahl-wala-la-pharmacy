#!/usr/bin/env python3
import json
from src.instagram import InstagramPublisher
print(json.dumps(InstagramPublisher().validate_account(), indent=2))

