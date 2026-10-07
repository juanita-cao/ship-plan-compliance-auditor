import { VESSEL_FLEET, type VesselFleetEntry } from "../config";

/** Look a fleet vessel up by its project id / history key (they are the same for every vessel). */
export function fleetEntry(key: string): VesselFleetEntry | undefined {
  return VESSEL_FLEET.find(v => v.historyKey === key || v.projectId === key);
}

/** The one display name used everywhere for a vessel. */
export function vesselName(key: string, fallback?: string): string {
  return fleetEntry(key)?.name ?? fallback ?? key;
}

const TYPE_ZH: Record<string, string> = {
  "General Cargo": "杂货船", "Bulk Carrier": "散货船", "Tanker": "油轮", "Container Ship": "集装箱船",
};
const FLAG_ZH: Record<string, string> = {
  "Panama": "巴拿马", "Singapore": "新加坡", "Hong Kong": "香港",
  "Marshall Is.": "马绍尔群岛", "Marshall Islands": "马绍尔群岛", "Bahamas": "巴哈马",
};

const isZh = (lang: string) => lang.startsWith("zh");
export const typeLabel = (type: string, lang: string) => (isZh(lang) ? TYPE_ZH[type] ?? type : type);
export const flagLabel = (flag: string, lang: string) => (isZh(lang) ? FLAG_ZH[flag] ?? flag : flag);
