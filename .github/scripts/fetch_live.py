#!/usr/bin/env python3

import datetime as dt
import json
import pathlib
import urllib.error
import urllib.parse
import urllib.request

LIVE_ENDPOINT = "https://peaklogin3.azurewebsites.net/api/VersionCheck"
VERSION = "2.1.a"
OUT_PATH = pathlib.Path(__file__).resolve().parent.parent.parent / "data" / "live.json"


def fetch():
    url = f"{LIVE_ENDPOINT}?version={urllib.parse.quote(VERSION)}"
    req = urllib.request.Request(url, headers={"User-Agent": "peak-rotation-tracker"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    try:
        live = fetch()
        out = {
            "dayIndex": live.get("LevelIndex"),
            "raw": live,
            "fetchedAt": now,
            "ok": True,
        }
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        out = {"ok": False, "error": str(exc), "fetchedAt": now}

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, indent=2) + "\n")
    print(out)


if __name__ == "__main__":
    main()
