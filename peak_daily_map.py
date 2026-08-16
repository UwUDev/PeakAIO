import argparse
import datetime as dt
import json
import urllib.error
import urllib.parse
import urllib.request

LIVE_ENDPOINT = "https://peaklogin3.azurewebsites.net/api/VersionCheck"
LIVE_ENDPOINT_BETA = "https://peaklogin-beta.azurewebsites.net/api/VersionCheck"

EPOCH = dt.datetime(2025, 6, 14, 17, 0, 0, tzinfo=dt.timezone.utc)
ROTATION_HOURS = 24

SCENE_PATHS = [f"Assets/8_SCENES/Generated/Level_{i}.unity" for i in range(12)]

BIOME_IDS = [
    "STAS", "SRMS", "STMS", "SRAS", "STMS", "STAS",
    "SRAS", "SRMS", "STMS", "SRAS", "SRMS", "STAS",
]

# biomeTypes per level: [Shore, Tropics(1)/Roots(7), Alpine(2)/Mesa(6), Swamp(8)]
SELECTED_BIOMES = [
    ["BlueBeach", "Thorny", "Default", "None"],
    ["RedBeach", "redwoods deep woods", "CacusHell", "None"],
    ["Default", "Default", "NoVariant", "None"],
    ["SnakeBeach", "Redwoods Default", "Default", "None"],
    ["RedBeach", "SkyJungle", "NoVariant", "None"],
    ["Default", "Default", "Default", "None"],
    ["RedBeach", "Redwoods Default", "Default", "None"],
    ["JellyHell", "Redwoods Default", "DynamiteHell", "None"],
    ["Default", "Default", "CacusHell", "None"],
    ["SnakeBeach", "redwoods deep woods", "Default", "None"],
    ["Default", "- Deep Water variant", "ScorpionsHell", "None"],
    ["Default", "Default", "Default", "None"],
]

DEEP_TIER = ["Deep Biome", "Peak"]

BIOME_SEQUENCES = [
    ["Shore", "Tropics", "Alpine", *DEEP_TIER],
    ["Shore", "Roots", "Mesa", *DEEP_TIER],
    ["Shore", "Tropics", "Mesa", *DEEP_TIER],
    ["Shore", "Roots", "Alpine", *DEEP_TIER],
    ["Shore", "Tropics", "Mesa", *DEEP_TIER],
    ["Shore", "Tropics", "Alpine", *DEEP_TIER],
    ["Shore", "Roots", "Alpine", *DEEP_TIER],
    ["Shore", "Roots", "Mesa", *DEEP_TIER],
    ["Shore", "Tropics", "Mesa", *DEEP_TIER],
    ["Shore", "Roots", "Alpine", *DEEP_TIER],
    ["Shore", "Roots", "Mesa", *DEEP_TIER],
    ["Shore", "Tropics", "Alpine", *DEEP_TIER],
]


def compute_level_index(now_utc: dt.datetime) -> int:
    hours_elapsed = int((now_utc - EPOCH).total_seconds() // 3600)
    day_index = hours_elapsed // ROTATION_HOURS
    return day_index


def next_rotation_time(now_utc: dt.datetime) -> dt.datetime:
    hours_elapsed = int((now_utc - EPOCH).total_seconds() // 3600)
    day_index = hours_elapsed // ROTATION_HOURS
    return EPOCH + dt.timedelta(hours=(day_index + 1) * ROTATION_HOURS)


def fetch_live_level_index(version: str, beta: bool = False, timeout: float = 5.0) -> dict:
    endpoint = LIVE_ENDPOINT_BETA if beta else LIVE_ENDPOINT
    url = f"{endpoint}?version={urllib.parse.quote(version)}"
    req = urllib.request.Request(url, headers={"User-Agent": "peak-daily-map-poc"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
    return json.loads(body)


def describe(day_index: int) -> dict:
    idx = day_index % len(SCENE_PATHS)
    biome_id = BIOME_IDS[idx]
    return {
        "raw_day_index": day_index,
        "level_index": idx,
        "scene": SCENE_PATHS[idx],
        "biome_id": biome_id,
        "biomes": BIOME_SEQUENCES[idx],
        "variants": SELECTED_BIOMES[idx],
    }


def main():
    ap = argparse.ArgumentParser(description="Predict PEAK's daily map rotation.")
    ap.add_argument("--offset-days", type=int, default=0,
                     help="Look N days into the future/past instead of today.")
    ap.add_argument("--live", action="store_true",
                     help="Also query the real CloudAPI VersionCheck endpoint "
                          "(peaklogin3.azurewebsites.net) and compare its "
                          "LevelIndex against the local prediction.")
    ap.add_argument("--version", default="2.1.a",
                     help="Version string sent to the live endpoint. Best-effort "
                          "guess -- see fetch_live_level_index() docstring.")
    ap.add_argument("--beta", action="store_true",
                     help="Use the beta CloudAPI endpoint instead of production.")
    args = ap.parse_args()

    now = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=args.offset_days)
    day_index = compute_level_index(now)
    info = describe(day_index)
    rotates_at = next_rotation_time(now)

    if args.live:
        print("--- Live CloudAPI query ---")
        try:
            live = fetch_live_level_index(args.version, beta=args.beta)
            live_index = live.get("LevelIndex")
            print(f"Server response       : {live}")
            print(f"Server LevelIndex      : {live_index}")
            local_index = info["level_index"] if len(SCENE_PATHS) else None
            if live_index is not None:
                match = "MATCH" if live_index == day_index or live_index == local_index else "DIFFERS"
                print(f"Local day_index={day_index}, level_index={local_index}  -> {match}")
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
            print(f"Live query failed ({exc}); falling back to local prediction only.")
        except json.JSONDecodeError as exc:
            print(f"Live query returned unparseable JSON ({exc}); falling back to local prediction only.")
        print()

    print(f"Current UTC time     : {now.isoformat()}")
    print(f"Epoch (rotation #0)  : {EPOCH.isoformat()}")
    print(f"Absolute day index   : {info['raw_day_index']}")
    print(f"Level index (mod 12) : {info['level_index']}")
    print(f"Scene                : {info['scene']}")
    print(f"Biome ID string      : {info['biome_id']}")
    print(f"Biome sequence       : {' -> '.join(info['biomes'])}")
    print(f"Variant skins        : {info['variants']}")
    print(f"Next rotation (UTC)  : {rotates_at.isoformat()}")

    print("\n--- Next 12 rotations (full cycle) ---")
    for i in range(12):
        d = day_index + i
        inf = describe(d)
        marker = "  <- today" if i == 0 else ""
        print(f"day_index={d:>6}  level={inf['level_index']:>2}  "
              f"biome={inf['biome_id']}  scene={inf['scene']}{marker}")


if __name__ == "__main__":
    main()
