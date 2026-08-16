import argparse
import json
import re
import sys
from pathlib import Path

DEFAULT_PROJECT = Path("/home/uwu/Documents/PEAK v2.1.a/ExportedProject")

ITEM_GUID = "c30496d6ae6d6f907456e10a94e01ec6"
LOOTDATA_GUID = "a44ff709bc91abce780008938281a0aa"
MODIFYSTATUS_GUID = "32b3edd72d0f40dae0a4f1cb5690ba53"
INFLICTPOISON_GUID = "fa6a8bbd2c612a25b5a6a592ce4e50c4"
GIVESTAMINA_GUID = "6154f562a95c1827e5a01810b2e5ba47"

# CharacterAfflictions.STATUSTYPE all on one normalized 0..1 bar (same unit stamina and carry weight use), so *100 gives the real bar-fill %.
STATUS_NAMES = ["Injury", "Hunger", "Cold", "Poison", "Crab", "Curse", "Drowsy",
                "Weight", "Hot", "Thorns", "Spores", "Web", "Arrow", "Petrify", "FlyTrap"]
WEIGHT_UNIT_FRACTION = 0.025  # 1 carryWeight point = 2.5% of the bar

STATUS_COLORS = {
    "Injury": "red", "Hunger": "gold", "Cold": "teal", "Poison": "green",
    "Crab": "purple", "Curse": "purple", "Drowsy": "purple", "Weight": "dim",
    "Hot": "orange", "Thorns": "red", "Spores": "green", "Web": "teal",
    "Arrow": "red", "Petrify": "dim", "FlyTrap": "green", "Stamina": "orange",
}

RARITY_NAMES = ["Common", "Uncommon", "Rare", "Epic", "Legendary", "Mythic", "Ridiculously Rare"]

NAME_OVERRIDES = {
    "AMULET_CLONE": "Scout's Generosity",
    "AMULET_DOUBLEJUMP": "Scout's Initiative",
    "AMULET_HEALING": "Scout's Tenacity",
    "AMULET_INFINITESTAM": "Scout's Ambition",
    "AUTOPARACHUTE": "Auto-Parachute",
    "EARLYWORM": "The Early Worm",
    "SCOUTMASTERSOUL": "Scoutmaster's Soul",
    "SNOWBALL": "Snowball",
    "THEBOOKOFBONES": "The Book of Bones",
    "VOIDLAUNCHER": "Anti-Zooka",
}

# SpawnPool.cs bit -> label
SPAWN_POOL_BITS = {
    1 << 2: "Mushroom cluster",
    1 << 3: "Berry bush (Shore)",
    1 << 4: "Berry bush (Tropics)",
    1 << 5: "Spiky vine",
    1 << 6: "Coconut tree",
    1 << 7: "Willow tree (Tropics)",
    1 << 8: "Jungle vine",
    1 << 9: "Winterberry tree",
    1 << 10: "Luggage (Shore)",
    1 << 11: "Luggage (Tropics)",
    1 << 12: "Luggage (Alpine)",
    1 << 13: "Luggage (Volcano)",
    1 << 14: "Luggage (Climber)",
    1 << 15: "Luggage (Ancient)",
    1 << 16: "Luggage (Cursed)",
    1 << 17: "Respawn coffin",
    1 << 18: "Nest",
    1 << 19: "Guidebook page (Shore)",
    1 << 20: "Guidebook page (Tropics)",
    1 << 21: "Guidebook page (Alpine)",
    1 << 22: "Cactus",
    1 << 23: "Redwood",
    1 << 24: "Luggage (Mesa)",
    1 << 25: "Campfire",
    1 << 26: "Luggage (Roots)",
    1 << 27: "All",
    1 << 28: "Luggage (Gloom)",
    1 << 29: "Luggage (Citadel)",
    1 << 30: "Luggage (Clown)",
}

# From Item.ItemTags [Flags] enum.
ITEM_TAG_BITS = {
    1 << 0: "Mystical",
    1 << 1: "Packaged food",
    1 << 2: "Berry",
    1 << 3: "Mushroom",
    1 << 4: "BingBong",
    1 << 5: "Gourmand requirement",
    1 << 6: "Golden idol",
    1 << 7: "Bird",
    1 << 8: "Book of Bones",
    1 << 9: "Scout amulet",
}

DOC_SPLIT_RE = re.compile(r"(?=^--- !u!\d+ &-?\d+$)", re.MULTILINE)
ICON_RE = re.compile(r"icon:\s*\{fileID:\s*\d+,\s*guid:\s*([0-9a-f]{32})")
ITEMNAME_RE = re.compile(r"itemName:[ \t]*(.*?)[ \t]*$", re.MULTILINE)
PROMPT_RE = re.compile(r"mainInteractPrompt:[ \t]*(.*?)[ \t]*$", re.MULTILINE)


def find_component_block(text: str, guid: str) -> str | None:
    for doc in DOC_SPLIT_RE.split(text):
        if f"guid: {guid}, type: 3" in doc[:400] or (f"guid: {guid}" in doc and "m_Script:" in doc):
            return doc
    return None


def find_all_component_blocks(text: str, guid: str) -> list:
    return [doc for doc in DOC_SPLIT_RE.split(text)
            if f"guid: {guid}, type: 3" in doc[:400] or (f"guid: {guid}" in doc and "m_Script:" in doc)]


def block_field(block: str, name: str):
    m = re.search(rf"^[ \t]*{name}:[ \t]*(.*?)[ \t]*$", block, re.MULTILINE)
    return m.group(1) if m else None


def parse_effects(text: str) -> list:
    effects = []

    for block in find_all_component_blocks(text, MODIFYSTATUS_GUID):
        status_n = block_field(block, "statusType")
        amount = block_field(block, "changeAmount")
        if status_n is None or amount is None:
            continue
        try:
            status_idx, amount_f = int(status_n), float(amount)
        except ValueError:
            continue
        if not (0 <= status_idx < len(STATUS_NAMES)):
            continue
        name = STATUS_NAMES[status_idx]
        effects.append({
            "status": name,
            "percent": round(amount_f * 100, 1),
            "color": STATUS_COLORS.get(name, "dim"),
        })

    poison_block = find_component_block(text, INFLICTPOISON_GUID)
    if poison_block is not None:
        infliction_time = block_field(poison_block, "inflictionTime")
        per_second = block_field(poison_block, "poisonPerSecond")
        delay = block_field(poison_block, "delay")
        try:
            total = float(infliction_time) * float(per_second)
            effects.append({
                "status": "Poison",
                "percent": round(total * 100, 1),
                "color": STATUS_COLORS["Poison"],
                "overSeconds": float(infliction_time),
                "delaySeconds": float(delay) if delay is not None else 0.0,
            })
        except (TypeError, ValueError):
            pass

    stamina_block = find_component_block(text, GIVESTAMINA_GUID)
    if stamina_block is not None:
        amount = block_field(stamina_block, "amount")
        try:
            effects.append({
                "status": "Stamina",
                "percent": round(float(amount) * 100, 1),
                "color": STATUS_COLORS["Stamina"],
            })
        except (TypeError, ValueError):
            pass

    return effects


def parse_item_prefab(path: Path) -> dict | None:
    text = path.read_text(encoding="utf-8", errors="replace")

    item_block = find_component_block(text, ITEM_GUID)
    if item_block is None:
        return None

    def field(name, block=item_block):
        return block_field(block, name)

    item_id = field("itemID")
    carry_weight = field("carryWeight")
    item_tags = field("itemTags")

    ui_match = re.search(r"^\s*UIData:\n((?:^\s{4,}.*\n?)+)", item_block, re.MULTILINE)
    ui_block = ui_match.group(1) if ui_match else ""
    name_m = ITEMNAME_RE.search(ui_block)
    icon_m = ICON_RE.search(ui_block)
    prompt_m = PROMPT_RE.search(ui_block)

    display_name = (name_m.group(1) if name_m else "").strip() or path.stem
    display_name = NAME_OVERRIDES.get(display_name, display_name)
    icon_guid = icon_m.group(1) if icon_m else None
    prompt = (prompt_m.group(1) if prompt_m else "").strip()

    rarity = None
    spawn_pools = []
    loot_block = find_component_block(text, LOOTDATA_GUID)
    if loot_block is not None:
        rarity_m = re.search(r"^\s*Rarity:\s*(\d+)\s*$", loot_block, re.MULTILINE)
        pool_m = re.search(r"^\s*spawnLocations:\s*(-?\d+)\s*$", loot_block, re.MULTILINE)
        if rarity_m:
            rarity = int(rarity_m.group(1))
        if pool_m:
            mask = int(pool_m.group(1)) & 0xFFFFFFFF
            spawn_pools = [label for bit, label in SPAWN_POOL_BITS.items() if mask & bit]

    tags = []
    if item_tags:
        try:
            mask = int(item_tags)
            tags = [label for bit, label in ITEM_TAG_BITS.items() if mask & bit]
        except ValueError:
            pass

    weight = int(carry_weight) if carry_weight and carry_weight.lstrip("-").isdigit() else None

    return {
        "file": path.stem,
        "name": display_name,
        "itemID": int(item_id) if item_id and item_id.lstrip("-").isdigit() else None,
        "weight": weight,
        "weightPercent": round(weight * WEIGHT_UNIT_FRACTION * 100, 1) if weight is not None else None,
        "prompt": prompt,
        "tags": tags,
        "rarity": RARITY_NAMES[rarity] if rarity is not None and 0 <= rarity < len(RARITY_NAMES) else None,
        "spawnPools": sorted(spawn_pools),
        "effects": parse_effects(text),
        "iconGuid": icon_guid,
    }


def build_texture_guid_index(project: Path) -> dict:
    print("Indexing Texture2D GUIDs...", file=sys.stderr)
    tex_dir = project / "Assets" / "Texture2D"
    index = {}
    for meta_path in tex_dir.glob("*.png.meta"):
        content = meta_path.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"guid:\s*([0-9a-f]{32})", content)
        if m:
            index[m.group(1)] = meta_path.with_suffix("")  # strip .meta -> the .png
    print(f"  -> {len(index)} textures indexed", file=sys.stderr)
    return index


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", default=str(DEFAULT_PROJECT), help="ExportedProject root.")
    ap.add_argument("--icons-out", default=str(Path(__file__).parent / "assets" / "img" / "items"),
                    help="Where to copy resolved icon images.")
    ap.add_argument("-o", "--output", default=str(Path(__file__).parent / "items.json"))
    args = ap.parse_args()

    project = Path(args.project)
    items_dir = project / "Assets" / "Resources" / "0_items"
    if not items_dir.is_dir():
        print(f"Not found: {items_dir}", file=sys.stderr)
        sys.exit(1)

    prefabs = sorted(items_dir.glob("*.prefab"))
    print(f"Found {len(prefabs)} prefabs, parsing...", file=sys.stderr)

    items = []
    for p in prefabs:
        data = parse_item_prefab(p)
        if data is not None:
            items.append(data)
    print(f"  -> {len(items)} are actual items (have an Item component)", file=sys.stderr)

    tex_index = build_texture_guid_index(project)
    icons_out = Path(args.icons_out)
    icons_out.mkdir(parents=True, exist_ok=True)

    from PIL import Image
    resolved_icons = 0
    for item in items:
        guid = item.pop("iconGuid")
        item["icon"] = None
        if guid and guid in tex_index:
            src = tex_index[guid]
            safe = re.sub(r"[^a-zA-Z0-9_-]+", "_", item["file"]).strip("_")
            dst = icons_out / f"{safe}.webp"
            try:
                im = Image.open(src).convert("RGBA")
                im.thumbnail((128, 128), Image.LANCZOS)
                im.save(dst, "WEBP", quality=85, method=6)
                item["icon"] = f"assets/img/items/{safe}.webp"
                resolved_icons += 1
            except Exception as exc:
                print(f"  icon export failed for {item['file']}: {exc}", file=sys.stderr)
    print(f"  -> {resolved_icons}/{len(items)} icons exported", file=sys.stderr)

    items.sort(key=lambda i: i["name"].lower())
    Path(args.output).write_text(json.dumps({"items": items}, indent=2))
    print(f"Wrote {args.output} ({len(items)} items)", file=sys.stderr)


if __name__ == "__main__":
    main()
