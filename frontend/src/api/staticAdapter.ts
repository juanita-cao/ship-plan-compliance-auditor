import { AxiosError, type AxiosAdapter, type AxiosResponse, type InternalAxiosRequestConfig } from "axios";

// Static demo build (ADR-F36): answers the API calls from pre-exported JSON in /demo-data/.

/** Same rule as `safe()` in scripts/export_static_demo.py. */
export const safeName = (s: string) => s.replace(/[^A-Za-z0-9_.-]/g, "_");

/** Maps an API request to its exported file (relative to demo-data/), or null if nothing was exported for it. */
export function staticPath(method: string, url: string, body?: unknown): string | null {
  const u = new URL(url, "http://static.local");
  const parts = u.pathname.replace(/^\/api/, "").split("/").filter(Boolean);
  const m = method.toLowerCase();
  if (m === "get" && parts.length === 1 && parts[0] === "projects") return "projects.json";
  if (m === "get" && parts.length === 3 && parts[0] === "image") return `image/${parts[1]}/${safeName(parts[2])}.json`;
  if (m === "post" && parts.length === 1 && parts[0] === "detect") {
    const b = (typeof body === "string" ? safeJson(body) : body) as { project_id?: string; image_stem?: string } | null;
    return b?.project_id && b.image_stem ? `detect/${b.project_id}/${safeName(b.image_stem)}.json` : null;
  }
  if (m === "get" && parts.length === 3 && parts[0] === "spotlight") {
    const base = `spotlight/${parts[1]}/${safeName(parts[2])}`;
    const inst = u.searchParams.get("instance_id");
    const cat = u.searchParams.get("category");
    // a selected instance overrides the category (same as the live renderer)
    if (inst) return `${base}/inst-${safeName(inst)}.json`;
    if (cat) return `${base}/cat-${safeName(cat)}.json`;
    return `${base}/all.json`;
  }
  return null;
}

function safeJson(s: string): unknown { try { return JSON.parse(s); } catch { return null; } }

const respond = (config: InternalAxiosRequestConfig, status: number, data: unknown): AxiosResponse =>
  ({ data, status, statusText: String(status), headers: {}, config, request: {} });

const fail = (config: InternalAxiosRequestConfig, status: number, detail: unknown) => {
  const response = respond(config, status, { detail });
  return new AxiosError(`Request failed with status code ${status}`, String(status), config, {}, response);
};

/** Axios adapter that serves exported JSON; uploads are not available in the static build. */
export const staticAdapter: AxiosAdapter = async config => {
  const method = config.method ?? "get";
  const url = config.url ?? "";
  if (/\/(plans|projects\/[^/]+\/plans)/.test(url)) throw fail(config, 501, { rule: "ST", message: "static-demo" });
  const rel = staticPath(method, url, config.data);
  if (!rel) throw fail(config, 404, "Not part of the static demo");
  const res = await fetch(`${import.meta.env.BASE_URL}demo-data/${rel}`);
  const type = res.headers.get("content-type") ?? "";
  // a dev/preview server answers unknown paths with index.html (200): treat that as missing
  if (!res.ok || !type.includes("json")) throw fail(config, 404, "Not part of the static demo");
  return respond(config, 200, await res.json());
};
