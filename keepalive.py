"""
Keep every Hugging Face Space owned by a user awake.

For each Space it:
  1. Reads the Space's runtime stage from the Hugging Face API.
  2. If the Space is SLEEPING (or PAUSED), restarts it via the API (needs HF_TOKEN with write access).
  3. Sends an HTTP request to the Space's *.hf.space URL so it registers activity.

Spaces are discovered automatically, so new Spaces are covered without editing this file.

Environment variables:
  HF_USERNAME     Hugging Face user/org whose Spaces to keep alive (default: Faruna01)
  HF_TOKEN        Hugging Face token with WRITE access (needed to wake sleeping Spaces
                  and to see private Spaces). Optional, but strongly recommended.
  EXTRA_SPACES    Optional comma-separated extra Space ids, e.g. "someorg/some-space"
  SKIP_SPACES     Optional comma-separated Space ids to ignore
  WAKE_PAUSED     "true" to also restart Spaces you paused manually (default: true)
  KEEP_SPACES     Optional comma-separated Space ids. If set, ONLY these are woken up
                  (checked first); other Spaces are just pinged and never fail the run.
                  Useful because free accounts can only run a few CPU Spaces at once.
"""

import os
import re
import sys
import time
from datetime import datetime, timezone

import requests
from huggingface_hub import HfApi

USERNAME = os.environ.get("HF_USERNAME", "Faruna01").strip()
TOKEN = os.environ.get("HF_TOKEN", "").strip() or None
EXTRA = [s.strip() for s in os.environ.get("EXTRA_SPACES", "").split(",") if s.strip()]
SKIP = {s.strip().lower() for s in os.environ.get("SKIP_SPACES", "").split(",") if s.strip()}
KEEP = [s.strip() for s in os.environ.get("KEEP_SPACES", "").split(",") if s.strip()]
KEEP_LOWER = {s.lower() for s in KEEP}
WAKE_PAUSED = os.environ.get("WAKE_PAUSED", "true").lower() == "true"

WAKE_STAGES = {"SLEEPING"} | ({"PAUSED"} if WAKE_PAUSED else set())
OK_STAGES = {"RUNNING", "RUNNING_BUILDING", "RUNNING_APP_STARTING", "BUILDING", "APP_STARTING"}
ERROR_STAGES = {"BUILD_ERROR", "RUNTIME_ERROR", "CONFIG_ERROR", "NO_APP_FILE"}

api = HfApi(token=TOKEN)


def space_url(space_id: str, runtime) -> str:
    """Return the direct *.hf.space URL for a Space."""
    raw = getattr(runtime, "raw", None) or {}
    for d in raw.get("domains") or []:
        if d.get("domain"):
            return f"https://{d['domain']}"
    sub = re.sub(r"[^a-z0-9]+", "-", space_id.lower()).strip("-")
    return f"https://{sub}.hf.space"


def ping(url: str) -> str:
    headers = {"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}
    try:
        r = requests.get(url, timeout=60, headers=headers)
        return f"HTTP {r.status_code}"
    except Exception as e:  # noqa: BLE001
        return f"ping failed: {e.__class__.__name__}"


def discover() -> list[str]:
    ids = [s.id for s in api.list_spaces(author=USERNAME)]
    for extra in EXTRA:
        if extra not in ids:
            ids.append(extra)
    for k in KEEP:
        if k.lower() not in {i.lower() for i in ids}:
            ids.append(k)
    ids = [i for i in ids if i.lower() not in SKIP]
    # Priority Spaces first, so they get the free CPU slots
    return sorted(ids, key=lambda i: i.lower() not in KEEP_LOWER)


def is_priority(sid: str) -> bool:
    return not KEEP or sid.lower() in KEEP_LOWER


def main() -> int:
    print("HF Spaces keepalive")
    print(f"Time:  {datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S} UTC")
    print(f"User:  {USERNAME}")
    if not TOKEN:
        print("WARNING: HF_TOKEN is not set. Sleeping Spaces cannot be woken up and private "
              "Spaces are invisible. Add an HF_TOKEN repository secret (write access).")

    spaces = discover()
    print(f"Found {len(spaces)} Space(s)\n")

    problems = []
    for sid in spaces:
        try:
            runtime = api.get_space_runtime(sid)
            stage = runtime.stage
        except Exception as e:  # noqa: BLE001
            print(f"[??]   {sid}: could not read runtime ({e.__class__.__name__}: {e})")
            problems.append(sid)
            continue

        action = ""
        priority = is_priority(sid)
        if stage in WAKE_STAGES and not priority:
            action = " -> not in KEEP_SPACES, left asleep"
        elif stage in WAKE_STAGES:
            if TOKEN:
                try:
                    api.restart_space(sid)
                    action = " -> restart requested"
                except Exception as e:  # noqa: BLE001
                    action = f" -> restart FAILED ({e.__class__.__name__}: {e})"
                    problems.append(sid)
            else:
                action = " -> cannot wake (no HF_TOKEN)"
                problems.append(sid)
        elif stage in ERROR_STAGES:
            action = " -> needs a code/config fix on Hugging Face"
            if priority:
                problems.append(sid)

        url = space_url(sid, runtime)
        result = ping(url)
        tag = "OK" if stage in OK_STAGES else stage
        print(f"[{tag}] {sid} ({url}) {result}{action}")
        time.sleep(2)

    print(f"\nDone. {len(spaces) - len(problems)}/{len(spaces)} Space(s) OK.")
    if problems:
        print("Needs attention: " + ", ".join(problems))
        return 1  # makes the run fail so GitHub emails you
    return 0


if __name__ == "__main__":
    sys.exit(main())
