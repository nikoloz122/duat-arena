"""Pre-demo verification for June 21 live presentations.

Checks that the LLM response cache exists (so demo runs are fast and
deterministic) and optionally that the backend is reachable. Exit code 1
if the cache is missing; prints warnings for backend connectivity.

Usage:
    python scripts/verify_demo.py
"""

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE_PATH = ROOT / "logs" / "llm_cache.json"
BACKEND_HEALTH = "http://localhost:8000/api/health"


def main() -> int:
    ok = True

    if not CACHE_PATH.exists():
        print("FAIL: logs/llm_cache.json not found.")
        print("  Fix: python scripts/record_llm_demo.py --scenario liquidation-cascade --ticks 30")
        ok = False
    else:
        try:
            data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
            count = len(data) if isinstance(data, dict) else 0
            if count == 0:
                print("WARN: llm_cache.json exists but is empty.")
                print("  Fix: python scripts/record_llm_demo.py --scenario liquidation-cascade --ticks 30")
                ok = False
            else:
                print(f"OK: llm_cache.json ({count} cached LLM responses)")
        except (OSError, json.JSONDecodeError) as exc:
            print(f"FAIL: llm_cache.json unreadable ({exc})")
            ok = False

    try:
        with urllib.request.urlopen(BACKEND_HEALTH, timeout=3) as response:
            if response.status == 200:
                print("OK: backend reachable at http://localhost:8000")
            else:
                print(f"WARN: backend returned status {response.status}")
    except (urllib.error.URLError, TimeoutError, OSError):
        print("WARN: backend not reachable at http://localhost:8000")
        print("  Fix: uvicorn backend.main:app --reload --port 8000")

    if ok:
        print("\nDemo cache check passed.")
        return 0
    print("\nDemo cache check failed — record the LLM cache before presenting.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
