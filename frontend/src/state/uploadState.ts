import { UPLOAD_LIMITS } from "../config";
import type { ApiError, PlanUpload, SegRegion } from "../api/client";

// ── Client-side checks (rules U1–U3; the server re-validates) ─────────────────

export type RuleError = ApiError;

const IMAGE_EXT = /\.(png|jpe?g)$/i;
const PDF_EXT = /\.pdf$/i;

export function checkFileMeta(name: string, size: number): RuleError | null {
  const isPdf = PDF_EXT.test(name);
  if (!isPdf && !IMAGE_EXT.test(name)) return { rule: "U1", message: "unsupported-format" };
  const limit = isPdf ? UPLOAD_LIMITS.pdfBytes : UPLOAD_LIMITS.imageBytes;
  if (size > limit) return { rule: "U2", message: "too-large" };
  return null;
}

export function checkDims(w: number, h: number): RuleError | null {
  const long = Math.max(w, h);
  if (long < UPLOAD_LIMITS.minLongEdge) return { rule: "U3", message: "resolution-low" };
  if (long > UPLOAD_LIMITS.maxLongEdge) return { rule: "U3", message: "resolution-high" };
  return null;
}

// ── Upload modal state machine ────────────────────────────────────────────────

export type UpStep = "UP_IDLE" | "UP_UPLOADING" | "UP_SEGMENTING" | "UP_REVIEW" | "UP_DONE" | "UP_ERROR";

export interface EditableRegion { id: string; label: string; bbox: [number, number, number, number]; confidence: number }

export interface UploadState {
  step: UpStep;
  u4: boolean;
  u5: boolean;
  plan: PlanUpload | null;
  regions: EditableRegion[];
  error: RuleError | null;
}

export const UPLOAD_INITIAL: UploadState = { step: "UP_IDLE", u4: false, u5: false, plan: null, regions: [], error: null };

export type UploadEvent =
  | { type: "toggleConfirm"; which: "u4" | "u5"; value: boolean }
  | { type: "fileChosen"; clientError: RuleError | null }
  | { type: "uploaded"; plan: PlanUpload }
  | { type: "uploadFailed"; error: RuleError }
  | { type: "segmented"; regions: SegRegion[] }
  | { type: "regionRenamed"; id: string; label: string }
  | { type: "regionRemoved"; id: string }
  | { type: "regionResized"; id: string; bbox: [number, number, number, number] }
  | { type: "regionAdded"; sheetW: number; sheetH: number }
  | { type: "confirmSucceeded" }
  | { type: "confirmFailed"; error: RuleError }
  | { type: "cancelClicked" }
  | { type: "retry" };

export function canConfirm(regions: EditableRegion[]): boolean {
  return regions.length >= 1 && regions.every(r => r.label.trim().length > 0);
}

export function uploadReducer(s: UploadState, e: UploadEvent): UploadState {
  switch (e.type) {
    case "toggleConfirm":
      if (s.step !== "UP_IDLE") break;
      return { ...s, [e.which]: e.value };
    case "fileChosen":
      if (s.step !== "UP_IDLE") break;
      if (!s.u4 || !s.u5) break;
      return e.clientError ? { ...s, step: "UP_ERROR", error: e.clientError } : { ...s, step: "UP_UPLOADING", error: null };
    case "uploaded":
      if (s.step !== "UP_UPLOADING") break;
      return { ...s, step: "UP_SEGMENTING", plan: e.plan };
    case "uploadFailed":
      if (s.step !== "UP_UPLOADING" && s.step !== "UP_SEGMENTING") break;
      return { ...s, step: "UP_ERROR", error: e.error };
    case "segmented":
      if (s.step !== "UP_SEGMENTING") break;
      return { ...s, step: "UP_REVIEW", regions: e.regions.map(r => ({ id: r.id, label: r.label, bbox: r.bbox, confidence: r.confidence })) };
    case "regionRenamed":
      if (s.step !== "UP_REVIEW") break;
      return { ...s, regions: s.regions.map(r => (r.id === e.id ? { ...r, label: e.label } : r)), error: null };
    case "regionRemoved":
      if (s.step !== "UP_REVIEW") break;
      return { ...s, regions: s.regions.filter(r => r.id !== e.id), error: null };
    case "regionResized":
      if (s.step !== "UP_REVIEW") break;
      return { ...s, regions: s.regions.map(r => (r.id === e.id ? { ...r, bbox: e.bbox } : r)), error: null };
    case "regionAdded": {
      if (s.step !== "UP_REVIEW") break;
      const n = s.regions.length + 1;
      const w = Math.round(e.sheetW * 0.4), h = Math.round(e.sheetH * 0.4);
      const x0 = Math.round((e.sheetW - w) / 2), y0 = Math.round((e.sheetH - h) / 2);
      const id = `new_${Date.now().toString(36)}_${n}`;
      return { ...s, regions: [...s.regions, { id, label: `Deck ${n}`, bbox: [x0, y0, x0 + w, y0 + h], confidence: 1 }], error: null };
    }
    case "confirmSucceeded":
      if (s.step !== "UP_REVIEW") break;
      return { ...s, step: "UP_DONE" };
    case "confirmFailed":
      if (s.step !== "UP_REVIEW") break;
      return { ...s, error: e.error };
    case "cancelClicked":
      return { ...UPLOAD_INITIAL };
    case "retry":
      if (s.step !== "UP_ERROR") break;
      return { ...s, step: "UP_IDLE", plan: null, regions: [], error: null };
  }
  throw new Error(`Unrecognised (state=${s.step}, event=${e.type})`);
}

// ── Visible workflow step (ADR-F34) ───────────────────────────────────────────

export type PlanStep = 1 | 2 | 3 | 4;

/** Which stepper step is current. `workspace` = the upload workspace is open (null = closed). */
export function planStep(workspace: UploadState | null, hasDecks: boolean): PlanStep {
  if (!workspace) return hasDecks ? 4 : 1;
  switch (workspace.step) {
    case "UP_UPLOADING": case "UP_SEGMENTING": return 2;
    case "UP_REVIEW": return 3;
    case "UP_DONE": return 4;
    case "UP_ERROR": return workspace.plan ? 2 : 1;
    default: return 1;
  }
}

export const MIN_BOX_PX = 100;

/** Clamp a dragged box to the sheet and the minimum size. Pure so the drag maths is testable. */
export function clampBox(b: [number, number, number, number], sw: number, sh: number): [number, number, number, number] {
  let [x0, y0, x1, y1] = b.map(Math.round) as [number, number, number, number];
  x0 = Math.max(0, Math.min(x0, sw - MIN_BOX_PX)); y0 = Math.max(0, Math.min(y0, sh - MIN_BOX_PX));
  x1 = Math.min(sw, Math.max(x1, x0 + MIN_BOX_PX)); y1 = Math.min(sh, Math.max(y1, y0 + MIN_BOX_PX));
  return [x0, y0, x1, y1];
}

/** Move a box by (dx, dy) keeping its size inside the sheet. */
export function moveBox(b: [number, number, number, number], dx: number, dy: number, sw: number, sh: number): [number, number, number, number] {
  const w = b[2] - b[0], h = b[3] - b[1];
  const x0 = Math.max(0, Math.min(b[0] + dx, sw - w)), y0 = Math.max(0, Math.min(b[1] + dy, sh - h));
  return [Math.round(x0), Math.round(y0), Math.round(x0 + w), Math.round(y0 + h)];
}

export type Handle = "n" | "s" | "e" | "w" | "ne" | "nw" | "se" | "sw";

/** Drag one edge or corner by (dx, dy): the opposite edges stay put, min size and sheet bounds are kept. */
export function resizeBox(b: [number, number, number, number], h: Handle, dx: number, dy: number, sw: number, sh: number): [number, number, number, number] {
  let [x0, y0, x1, y1] = b;
  if (h.includes("w")) x0 = Math.max(0, Math.min(x0 + dx, x1 - MIN_BOX_PX));
  if (h.includes("e")) x1 = Math.min(sw, Math.max(x1 + dx, x0 + MIN_BOX_PX));
  if (h.includes("n")) y0 = Math.max(0, Math.min(y0 + dy, y1 - MIN_BOX_PX));
  if (h.includes("s")) y1 = Math.min(sh, Math.max(y1 + dy, y0 + MIN_BOX_PX));
  return [Math.round(x0), Math.round(y0), Math.round(x1), Math.round(y1)];
}
