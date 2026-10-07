import { useSyncExternalStore } from "react";

// localStorage-backed store for analyzed decks and review history.
// Pre-seeded so the demo looks live from first load.

export interface AnalyzedEntry {
  projectId: string;
  projectLabel: string;
  imageStem: string;
  imageLabel: string;
  analyzedAt: string;
  instanceCount?: number;
  aiVerdict?: string;
}

export interface HistoryEntry {
  id: string;
  projectId: string;
  projectLabel: string;
  imageStem: string;
  imageLabel: string;
  verdict: string;
  reviewer: string;
  submittedAt: string;
  instanceCount: number;
  confirmedCount: number;
  flaggedCount: number;
  note: string;
}

const ANALYZED_KEY = "pvcb_analyzed";
const HISTORY_KEY  = "pvcb_history_v2";

const makeSeedAnalyzed = (): AnalyzedEntry[] => [
  { projectId: "demo_ship_b", projectLabel: "Demo Ship B", imageStem: "below_main_deck_bow",  imageLabel: "Below Main Deck (Bow)",  analyzedAt: new Date(Date.now() - 3_600_000).toISOString() },
  { projectId: "demo_ship_a", projectLabel: "Demo Ship A", imageStem: "b_deck",               imageLabel: "B Deck",                analyzedAt: new Date(Date.now() - 7_200_000).toISOString() },
];
const SEED_ANALYZED: AnalyzedEntry[] = makeSeedAnalyzed();

const d = (days: number, h = 10) => new Date(Date.now() - days * 86_400_000 - (10 - h) * 3_600_000).toISOString();

const SEED_HISTORY: HistoryEntry[] = [
  { id: "seed-h1", projectId: "eastern_pioneer", projectLabel: "Eastern Pioneer", imageStem: "main_deck",    imageLabel: "Main Deck",            verdict: "GO",          reviewer: "J. Wong",  submittedAt: d(1),  instanceCount: 9, confirmedCount: 9, flaggedCount: 0, note: "" },
  { id: "seed-h2", projectId: "southern_cross",  projectLabel: "Southern Cross",  imageStem: "engine_room",  imageLabel: "Engine Room",          verdict: "NO_GO",       reviewer: "M. Tan",   submittedAt: d(8),  instanceCount: 7, confirmedCount: 5, flaggedCount: 2, note: "CO2 release point obstructed; one portable extinguisher expired (tag 2024)." },
  { id: "seed-h3", projectId: "northern_star",   projectLabel: "Northern Star",   imageStem: "accommodation", imageLabel: "Accommodation Deck",  verdict: "CONDITIONAL", reviewer: "A. Lim",   submittedAt: d(5),  instanceCount: 6, confirmedCount: 5, flaggedCount: 1, note: "Smoke detector spacing marginal in crew corridor; re-verify on next survey." },
  { id: "seed-h4", projectId: "asian_spirit",    projectLabel: "Asian Spirit",    imageStem: "pump_room",    imageLabel: "Cargo Pump Room",      verdict: "GO",          reviewer: "J. Wong",  submittedAt: d(19), instanceCount: 8, confirmedCount: 8, flaggedCount: 0, note: "" },
  { id: "seed-h5", projectId: "pacific_eagle",   projectLabel: "Pacific Eagle",   imageStem: "bridge_deck",  imageLabel: "Bridge Deck",          verdict: "GO",          reviewer: "A. Lim",   submittedAt: d(27), instanceCount: 5, confirmedCount: 5, flaggedCount: 0, note: "" },
  { id: "seed-h6", projectId: "pacific_trader",  projectLabel: "Pacific Trader",  imageStem: "cargo_hold_2", imageLabel: "Cargo Hold 2",         verdict: "NO_GO",       reviewer: "M. Tan",   submittedAt: d(47), instanceCount: 6, confirmedCount: 4, flaggedCount: 2, note: "Fixed fire-extinguishing system coverage incomplete at aft bulkhead." },
];

function safeGet<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return fallback;
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

function safeSet(key: string, value: unknown): boolean {
  try { localStorage.setItem(key, JSON.stringify(value)); return true; } catch { return false; }
}

// ── Change notification (components re-render on any write, also from other tabs) ──

const listeners = new Set<() => void>();
let version = 0;

function emit(): void {
  version += 1;
  listeners.forEach(l => l());
}

export function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}

if (typeof window !== "undefined") {
  window.addEventListener("storage", e => {
    if (e.key === ANALYZED_KEY || e.key === HISTORY_KEY) emit();
  });
}

/** Re-renders the calling component whenever analyzed/history data changes. */
export function useReviewStore(): number {
  return useSyncExternalStore(subscribe, () => version);
}

function initSeeds(): void {
  // Only seed once per browser (check by looking for the key)
  try {
    if (!localStorage.getItem(ANALYZED_KEY)) safeSet(ANALYZED_KEY, SEED_ANALYZED);
    if (!localStorage.getItem(HISTORY_KEY))  safeSet(HISTORY_KEY, SEED_HISTORY);
  } catch {}
}

initSeeds();

export function getAnalyzed(): AnalyzedEntry[] {
  return safeGet<AnalyzedEntry[]>(ANALYZED_KEY, SEED_ANALYZED);
}

export function addAnalyzed(entry: Omit<AnalyzedEntry, "analyzedAt">): void {
  const existing = getAnalyzed();
  const key = `${entry.projectId}/${entry.imageStem}`;
  const filtered = existing.filter(e => `${e.projectId}/${e.imageStem}` !== key);
  safeSet(ANALYZED_KEY, [{ ...entry, analyzedAt: new Date().toISOString() }, ...filtered]);
  emit();
}

export function getHistory(): HistoryEntry[] {
  return safeGet<HistoryEntry[]>(HISTORY_KEY, SEED_HISTORY);
}

export function addHistoryEntry(entry: HistoryEntry): void {
  const existing = getHistory();
  if (!safeSet(HISTORY_KEY, [entry, ...existing].slice(0, 50))) {
    throw new Error("Could not save the review (browser storage unavailable)");
  }
  emit();
}

const keyOf = (e: { projectId: string; imageStem: string }) => `${e.projectId}/${e.imageStem}`;

export function getReviewedKeys(): Set<string> {
  return new Set(getHistory().map(keyOf));
}

function latestSubmittedAt(key: string): string | null {
  let best: string | null = null;
  for (const h of getHistory()) {
    if (keyOf(h) === key && (best === null || h.submittedAt > best)) best = h.submittedAt;
  }
  return best;
}

/** An analysis is pending when it is newer than the latest signed review of the same deck. */
function isPending(e: AnalyzedEntry): boolean {
  const last = latestSubmittedAt(keyOf(e));
  return last === null || e.analyzedAt > last;
}

export function getDeckStatus(projectId: string, imageStem: string): "new" | "done" | "reviewed" {
  const key = `${projectId}/${imageStem}`;
  const analyzed = getAnalyzed().find(e => keyOf(e) === key);
  if (analyzed && isPending(analyzed)) return "done";
  if (latestSubmittedAt(key) !== null) return "reviewed";
  return "new";
}

export function getPendingQueue(): AnalyzedEntry[] {
  return getAnalyzed().filter(isPending);
}

export function getLatestHistory(projectId: string, imageStem: string): HistoryEntry | null {
  const key = `${projectId}/${imageStem}`;
  let best: HistoryEntry | null = null;
  for (const h of getHistory()) {
    if (keyOf(h) === key && (best === null || h.submittedAt > best.submittedAt)) best = h;
  }
  return best;
}

/** Presenter helper: back to the seeded demo state. Login and language are untouched. */
export function resetDemoData(): void {
  try {
    localStorage.removeItem("pvcb_last_project");
    localStorage.removeItem(ANALYZED_KEY);
    localStorage.removeItem(HISTORY_KEY);
  } catch {}
  safeSet(ANALYZED_KEY, makeSeedAnalyzed());
  safeSet(HISTORY_KEY, SEED_HISTORY);
  emit();
}

/** Stable report number, e.g. PVCB-FS-2026-0042. */
export function reportNo(e: Pick<HistoryEntry, "id" | "submittedAt">): string {
  const seed = /^seed-h(\d+)$/.exec(e.id);
  let n: number;
  if (seed) n = Number(seed[1]);
  else {
    let h = 0;
    for (const ch of e.id) h = (h * 31 + ch.charCodeAt(0)) % 9000;
    n = h + 1000;
  }
  return `PVCB-FS-${new Date(e.submittedAt).getFullYear()}-${String(n).padStart(4, "0")}`;
}
