import { staticAdapter } from "./staticAdapter";
import axios from "axios";

export const IS_STATIC_DEMO = import.meta.env.VITE_STATIC_DEMO === "1";
export const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE ?? "/api",
  ...(IS_STATIC_DEMO ? { adapter: staticAdapter } : {}),
});

// ─── Types ────────────────────────────────────────────────────────────────────

export interface CategoryMeta { id: string; label: string; color: string }
export interface ImageInfo { stem: string; label: string; uploaded?: boolean }
export interface ProjectInfo { id: string; label: string; images: ImageInfo[]; categories: CategoryMeta[] }

export interface DetectedInstance {
  id: string;
  category: string;
  cx: number;
  cy: number;
  display_bbox: [number, number, number, number] | null;
  location_desc: string | null;
  nearby_text: string | null;
}

export interface ComplianceCheck {
  rule_id: string;
  article: string;
  description: string;
  required: string | null;
  found: string | null;
  status: string;
  verdict: string;
}

export interface ComplianceResult {
  verdict: string;
  is_mock: boolean;
  regulation_set: string;
  checks: ComplianceCheck[];
}

export interface DetectResult {
  session_id: string;
  project_id: string;
  image_stem: string;
  instances: DetectedInstance[];
  total_by_category: Record<string, number>;
  compliance_result: ComplianceResult | null;
  raw_response: string | null;
  is_sample?: boolean;
  sample_label?: string | null;
}

export interface ImageResponse { data: string }

// ─── Helpers ──────────────────────────────────────────────────────────────────

export const get = async <T>(url: string) => (await http.get<T>(url)).data;
export const post = async <T>(url: string, body: unknown) => (await http.post<T>(url, body)).data;

// ─── Plan upload (ADR-F30) ────────────────────────────────────────────────────

export interface PlanUpload {
  plan_id: string; project_id: string; filename: string; kind: string;
  width: number; height: number; size_bytes: number; pages: number;
}
export interface SegRegion { id: string; bbox: [number, number, number, number]; label: string; confidence: number }
export interface SegmentResult { plan_id: string; sheet_w: number; sheet_h: number; regions: SegRegion[]; method: string }
export interface ApiError { rule: string; message: string }

export const uploadPlan = async (projectId: string, file: File) => {
  const form = new FormData();
  form.append("file", file);
  return (await http.post<PlanUpload>(`/projects/${projectId}/plans`, form)).data;
};
export const segmentPlan = async (planId: string) => (await http.post<SegmentResult>(`/plans/${planId}/segment`)).data;
export const planSheet = async (planId: string) => (await http.get<ImageResponse>(`/plans/${planId}/sheet`)).data;
export const confirmPlan = async (planId: string, decks: { region_id: string; label: string; bbox?: [number, number, number, number] }[]) =>
  (await http.post<{ images: ImageInfo[] }>(`/plans/${planId}/confirm`, { decks })).data;
export const deletePlan = async (planId: string) => { await http.delete(`/plans/${planId}`); };

/** Pulls {rule, message} out of an axios error from the plan endpoints. */
export function apiError(e: unknown): ApiError {
  const d = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  if (d && typeof d === "object" && "message" in (d as object)) return d as ApiError;
  return { rule: "ERR", message: typeof d === "string" ? d : "Something went wrong. Please try again." };
}
