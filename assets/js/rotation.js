// reproduces NextLevelService.CreateFallbackData() + MapBaker.GetLevel/GetBiomeID()
const EPOCH_MS = Date.UTC(2025, 5, 14, 17, 0, 0); // 2025-06-14T17:00:00Z
const ROTATION_HOURS = 24;

const SCENE_PATHS = Array.from({ length: 12 }, (_, i) => `Assets/8_SCENES/Generated/Level_${i}.unity`);
const BIOME_IDS = ["STAS", "SRMS", "STMS", "SRAS", "STMS", "STAS", "SRAS", "SRMS", "STMS", "SRAS", "SRMS", "STAS"];
const DEEP_BIOME = "Deep Biome";

const BIOME_SEQUENCES = [
  ["Shore", "Tropics", "Alpine"],
  ["Shore", "Roots", "Mesa"],
  ["Shore", "Tropics", "Mesa"],
  ["Shore", "Roots", "Alpine"],
  ["Shore", "Tropics", "Mesa"],
  ["Shore", "Tropics", "Alpine"],
  ["Shore", "Roots", "Alpine"],
  ["Shore", "Roots", "Mesa"],
  ["Shore", "Tropics", "Mesa"],
  ["Shore", "Roots", "Alpine"],
  ["Shore", "Roots", "Mesa"],
  ["Shore", "Tropics", "Alpine"],
];

const SELECTED_BIOMES = [
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
];

function computeDayIndex(nowMs) {
  const hoursElapsed = Math.floor((nowMs - EPOCH_MS) / 3.6e6);
  return Math.floor(hoursElapsed / ROTATION_HOURS);
}

function describeDay(dayIndex) {
  const idx = ((dayIndex % 12) + 12) % 12;
  const biomeId = BIOME_IDS[idx];
  return {
    dayIndex,
    levelIndex: idx,
    scene: SCENE_PATHS[idx],
    biomeId,
    sequence: [...BIOME_SEQUENCES[idx], DEEP_BIOME, "Peak"].join(" -> "),
    variants: SELECTED_BIOMES[idx],
  };
}

function nextRotation(dayIndex) {
  return new Date(EPOCH_MS + (dayIndex + 1) * ROTATION_HOURS * 3.6e6);
}

function fmtUTC(date) {
  return date.toISOString().replace("T", " ").slice(0, 16) + " UTC";
}

function fmtLocal(date) {
  return date.toLocaleString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function fmtLocalTime(date) {
  return date.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}

function formatCountdown(targetMs) {
  const diff = targetMs - Date.now();
  if (diff <= 0) return "any moment now";
  const s = Math.floor(diff / 1000);
  const days = Math.floor(s / 86400);
  const hours = Math.floor((s % 86400) / 3600);
  const mins = Math.floor((s % 3600) / 60);
  const secs = s % 60;
  if (days > 0) return `${days}d ${hours}h`;
  if (hours > 0) return `${hours}h ${mins}m`;
  if (mins > 0) return `${mins}m ${secs}s`;
  return `${secs}s`;
}

function formatCountdownPrecise(targetMs) {
  const diff = targetMs - Date.now();
  if (diff <= 0) return "any moment now";
  const s = Math.floor(diff / 1000);
  const days = Math.floor(s / 86400);
  const hours = Math.floor((s % 86400) / 3600);
  const mins = Math.floor((s % 3600) / 60);
  const secs = s % 60;
  const parts = [];
  if (days > 0) parts.push(`${days}d`);
  if (days > 0 || hours > 0) parts.push(`${hours}h`);
  parts.push(`${mins}m`);
  parts.push(`${secs}s`);
  return parts.join(" ");
}

const PEAK = { computeDayIndex, describeDay, nextRotation, fmtUTC, fmtLocal, fmtLocalTime, formatCountdown, formatCountdownPrecise, EPOCH_MS };
