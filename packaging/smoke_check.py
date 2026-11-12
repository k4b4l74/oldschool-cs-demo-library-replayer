"""Run by `tasks.py package` with Windows Python: waits until the built app
(started separately) serves the page and has imported the dropped demo.
WSL cannot reach a Windows server on 127.0.0.1, hence this script."""

import json
import sys
import time
import urllib.request

base = sys.argv[1]
deadline = time.monotonic() + float(sys.argv[2] if len(sys.argv) > 2 else 50)
last = None
while time.monotonic() < deadline:
    try:
        stats = json.load(urllib.request.urlopen(f"{base}/api/stats", timeout=3))
        page = urllib.request.urlopen(f"{base}/import", timeout=3).read()
        last = stats["matches"]
        if stats["matches"] == 1 and b'<div id="root">' in page:
            print("smoke: page served, dropped demo imported")
            sys.exit(0)
    except OSError as exc:
        last = exc
    time.sleep(1)
print(f"smoke: not ready ({last})")
sys.exit(1)
