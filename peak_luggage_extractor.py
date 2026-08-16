import argparse
import json
import re
import sys
from pathlib import Path

BASE_TYPE_GUIDS = {
    "876661e355bbed0da4ebc56dba46e5af": "Luggage",
    "e95eea442aa5c7984ef338eaba2e24b9": "LuggageCursed",
    "d9e12f2866a09385ecc60a86898e1816": "RespawnChest",
}
BIOME_GUID = "14c297a9a939f3f47a217e7afa06118c"  # Biome.cs

BIOME_TYPE_NAMES = {
    0: "Shore", 1: "Tropics", 2: "Alpine", 3: "Volcano", 5: "Peak", 6: "Mesa",
    7: "Roots", 8: "Swamp", 9: "Temple", 10: "Grasslands", 11: "Ocean",
    12: "Skyblock", 13: "Hell", 14: "Heaven", 15: "Mars", 16: "Wisconsin", 17: "Void",
}

SPAWN_POOL_CLOWN_BIT = 1 << 30  # LuggageClown, see SpawnPool.cs

DOC_HEADER_RE = re.compile(r"^--- !u!(\d+) &(-?\d+)")
GUID_RE = re.compile(r"guid:\s*([0-9a-f]{32})")
GAMEOBJECT_RE = re.compile(r"m_GameObject:\s*\{fileID:\s*(-?\d+)")
FATHER_RE = re.compile(r"m_Father:\s*\{fileID:\s*(-?\d+)")
SPAWNPOOL_RE = re.compile(r"^\s*spawnPool:\s*(-?\d+)\s*$")
BIOMETYPE_RE = re.compile(r"^\s*biomeType:\s*(-?\d+)\s*$")
NAME_RE = re.compile(r"^\s*m_Name:\s*(.*?)\s*$")


def parse_scene(path: Path):
    transform_go = {}  # transform_id -> go_id
    transform_father = {}  # transform_id -> father_transform_id
    go_transform = {}  # go_id -> transform_id  (reverse of transform_go)
    biome_of_go = {}  # go_id -> biome_type_name  (GameObjects carrying a Biome component)
    luggage_go = {}  # go_id -> {"base_type": ..., "has_clown_pool": bool}
    name_of_go = {}  # go_id -> m_Name (from the GameObject doc itself, class 1)

    doc_class = None
    cur_id = None
    cur_go = None
    cur_father = None
    cur_script_type = None  # for class 114
    cur_has_clown_pool = False

    def flush():
        nonlocal cur_go, cur_father, cur_script_type, cur_has_clown_pool
        if doc_class == "4":
            if cur_id is not None:
                transform_go[cur_id] = cur_go
                transform_father[cur_id] = cur_father
                if cur_go is not None:
                    go_transform[cur_go] = cur_id
        elif doc_class == "114":
            if cur_script_type == "Biome" and cur_go is not None:
                pass
            elif cur_script_type in BASE_TYPE_GUIDS.values() and cur_go is not None:
                luggage_go[cur_go] = {
                    "base_type": cur_script_type,
                    "has_clown_pool": cur_has_clown_pool,
                }
        cur_go = None
        cur_father = None
        cur_script_type = None
        cur_has_clown_pool = False

    pending_biome_go = None
    pending_biome_type = None

    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.startswith("--- !u!"):
                flush()
                if pending_biome_go is not None:
                    biome_of_go[pending_biome_go] = pending_biome_type
                pending_biome_go = None
                pending_biome_type = None

                m = DOC_HEADER_RE.match(line)
                if m:
                    doc_class = m.group(1)
                    cur_id = m.group(2)
                else:
                    doc_class = None
                    cur_id = None
                continue

            if doc_class not in ("1", "4", "114"):
                continue

            if doc_class == "1":
                nm = NAME_RE.match(line)
                if nm and cur_id is not None:
                    name_of_go[cur_id] = nm.group(1)
                continue

            if doc_class == "4":
                gm = GAMEOBJECT_RE.search(line)
                if gm:
                    cur_go = gm.group(1)
                    continue
                fm = FATHER_RE.search(line)
                if fm:
                    cur_father = fm.group(1)
                continue

            # doc_class == "114"
            gm = GAMEOBJECT_RE.search(line)
            if gm:
                cur_go = gm.group(1)
                if pending_biome_go is None and cur_script_type == "Biome":
                    pending_biome_go = cur_go
                continue

            if cur_script_type is None:
                if "m_Script:" in line:
                    sm = GUID_RE.search(line)
                    if sm:
                        guid = sm.group(1)
                        if guid in BASE_TYPE_GUIDS:
                            cur_script_type = BASE_TYPE_GUIDS[guid]
                        elif guid == BIOME_GUID:
                            cur_script_type = "Biome"
                            if cur_go is not None:
                                pending_biome_go = cur_go
                continue

            if cur_script_type == "Biome":
                bm = BIOMETYPE_RE.match(line)
                if bm:
                    pending_biome_type = BIOME_TYPE_NAMES.get(int(bm.group(1)), f"Unknown({bm.group(1)})")
                    if cur_go is not None:
                        pending_biome_go = cur_go
                continue

            # luggage-family: only need spawnPool value(s) to detect the clown pool
            sm = SPAWNPOOL_RE.match(line)
            if sm:
                if int(sm.group(1)) & SPAWN_POOL_CLOWN_BIT:
                    cur_has_clown_pool = True

        flush()
        if pending_biome_go is not None:
            biome_of_go[pending_biome_go] = pending_biome_type

    def resolve_biome(go_id):
        depth = 0
        t_id = go_transform.get(go_id)
        while t_id is not None and t_id != "0" and depth < 200:
            g = transform_go.get(t_id)
            if g is not None and g in biome_of_go:
                return biome_of_go[g]
            t_id = transform_father.get(t_id)
            depth += 1
        return "Unknown"

    entries = []
    for go_id, info in luggage_go.items():
        base_type = info["base_type"]
        name = name_of_go.get(go_id, "")
        if name.startswith("LuggageEpic"):
            category = "epic"
        elif base_type == "Luggage" and info["has_clown_pool"]:
            category = "clown"
        else:
            category = {"Luggage": "normal", "LuggageCursed": "cursed", "RespawnChest": "respawn"}[base_type]
        entries.append({
            "game_object_id": go_id,
            "name": name,
            "category": category,
            "biome": resolve_biome(go_id),
        })
    return entries


def summarize(entries: list) -> dict:
    total = len(entries)
    by_biome_category = {}
    for e in entries:
        biome = e["biome"]
        cat = e["category"]
        by_biome_category.setdefault(biome, {}).setdefault(cat, 0)
        by_biome_category[biome][cat] += 1
    return {"total": total, "by_biome": by_biome_category}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    default_dir = Path(__file__).parent / "levels"
    ap.add_argument("levels_folder", nargs="?", default=str(default_dir),
                    help="Folder containing Level_N.unity files.")
    ap.add_argument("-o", "--output", default=None, help="Output JSON path (default: print to stdout).")
    ap.add_argument("--only", default=None, help="Comma-separated level numbers to process, e.g. 0,1,2.")
    args = ap.parse_args()

    folder = Path(args.levels_folder)
    if not folder.is_dir():
        print(f"Not a directory: {folder}", file=sys.stderr)
        sys.exit(1)

    level_files = sorted(folder.glob("Level_*.unity"),
                         key=lambda p: int(re.search(r"Level_(\d+)", p.name).group(1)))
    if args.only:
        wanted = {int(x) for x in args.only.split(",")}
        level_files = [p for p in level_files
                       if int(re.search(r"Level_(\d+)", p.name).group(1)) in wanted]
    if not level_files:
        print(f"No Level_N.unity files found in {folder}", file=sys.stderr)
        sys.exit(1)

    result = {"levels": {}}
    for path in level_files:
        level_name = path.stem
        print(f"Parsing {level_name} ({path.stat().st_size / 1e6:.0f} MB)...", file=sys.stderr)
        entries = parse_scene(path)
        result["levels"][level_name] = summarize(entries)
        print(f"  -> {len(entries)} luggage/chest objects found", file=sys.stderr)

    out_text = json.dumps(result, indent=2)
    if args.output:
        Path(args.output).write_text(out_text)
        print(f"Wrote {args.output}", file=sys.stderr)
    else:
        print(out_text)


if __name__ == "__main__":
    main()
