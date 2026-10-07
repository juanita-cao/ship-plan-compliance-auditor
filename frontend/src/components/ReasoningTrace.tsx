import React from "react";
import { Tag } from "antd";

// ─── Parser ──────────────────────────────────────────────────────────────────

interface Section { name: string; raw: string }

function parseSections(raw: string): Section[] {
  const re = /^\[([A-Z_]+)\]\s*$/gm;
  const hits = [...raw.matchAll(re)];
  return hits.map((m, i) => ({
    name: m[1],
    raw: raw.slice((m.index ?? 0) + m[0].length, hits[i + 1]?.index ?? raw.length).trim(),
  }));
}

// Parse "- key: value\n  - subkey: subvalue" style blocks
function parseKeyBlocks(raw: string): Array<{ key: string; value: string; sub: Record<string, string> }> {
  const result: Array<{ key: string; value: string; sub: Record<string, string> }> = [];
  let current: { key: string; value: string; sub: Record<string, string> } | null = null;
  for (const line of raw.split("\n")) {
    const top = line.match(/^- ([^:]+):\s*(.*)/);
    const sub = line.match(/^\s{2,}- ([^:]+):\s*(.*)/);
    if (top && !line.startsWith("  ")) {
      if (current) result.push(current);
      current = { key: top[1].trim(), value: top[2].trim(), sub: {} };
    } else if (sub && current) {
      current.sub[sub[1].trim()] = sub[2].trim();
    }
  }
  if (current) result.push(current);
  return result;
}

// ─── Sub-renderers ────────────────────────────────────────────────────────────

function fmtKey(k: string) {
  return k.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function fmtCategory(cat: string) {
  return cat
    .replace(/^extinguisher_/, "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function StatusBadge({ value }: { value: string }) {
  const v = value.toUpperCase();
  const map: Record<string, [string, string]> = {
    NO:   ["#E6F7E6", "#237804"],
    YES:  ["#FFF1F0", "#CF1322"],
    PASS: ["#E6F7E6", "#237804"],
    FAIL: ["#FFF1F0", "#CF1322"],
    WARN: ["#FFF7E6", "#D46B08"],
    CLEAR: ["#F0F5FF", "#2F54EB"],
  };
  const [bg, fg] = map[v] ?? ["#F5F5F5", "#595959"];
  return (
    <span style={{
      display: "inline-block", padding: "1px 8px", borderRadius: 4,
      fontSize: 11, fontWeight: 700, letterSpacing: "0.04em",
      background: bg, color: fg, fontFamily: "inherit",
    }}>{v}</span>
  );
}

function SectionHeader({ step, title, icon }: { step: number; title: string; icon: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
      <span style={{
        width: 22, height: 22, borderRadius: "50%",
        background: "#EBF0FF", color: "#2F54EB",
        display: "inline-flex", alignItems: "center", justifyContent: "center",
        fontSize: 11, fontWeight: 700, flexShrink: 0,
      }}>{step}</span>
      <span style={{ fontSize: 13, marginRight: 4 }}>{icon}</span>
      <span style={{ fontWeight: 600, fontSize: 14, color: "#1a1a2e" }}>{title}</span>
    </div>
  );
}

// ─── Section: Detection List ──────────────────────────────────────────────────

function DetectionList({ raw }: { raw: string }) {
  const items = parseKeyBlocks(raw);
  return (
    <div>
      <SectionHeader step={1} icon="🔍" title="Visual Detections" />
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {items.map((inst) => (
          <div key={inst.key} style={{
            background: "#FAFAFA", border: "1px solid #F0F0F0",
            borderRadius: 8, padding: "10px 14px",
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
              <span style={{
                background: "#E6F0FF", color: "#2F54EB",
                borderRadius: 4, padding: "1px 8px", fontSize: 11, fontWeight: 700,
              }}>{inst.key.replace("_", " ").toUpperCase()}</span>
              {inst.sub.nearby_text && (
                <Tag color="orange" style={{ margin: 0, fontSize: 11 }}>
                  label: {inst.sub.nearby_text.replace(/"/g, "")}
                </Tag>
              )}
              {inst.sub.boundary_status && (
                <StatusBadge value={inst.sub.boundary_status} />
              )}
            </div>
            {inst.sub.location && (
              <div style={{ fontSize: 13, color: "#262626", fontWeight: 500, marginBottom: 3 }}>
                📍 {inst.sub.location}
              </div>
            )}
            {inst.sub.visual_features && (
              <div style={{ fontSize: 12, color: "#595959" }}>{inst.sub.visual_features}</div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Section: Matching ────────────────────────────────────────────────────────

function Matching({ raw }: { raw: string }) {
  const rows = parseKeyBlocks(raw).filter((r) => r.key !== "unknown" && r.key !== "excluded_boundary");
  return (
    <div>
      <SectionHeader step={2} icon="🏷️" title="Category Assignment" />
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {rows.map((row) => {
          const ids = row.value.replace(/[\[\]]/g, "").split(",").map((s) => s.trim()).filter(Boolean);
          return (
            <div key={row.key} style={{
              display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap",
              padding: "6px 12px", background: "#FAFAFA",
              borderRadius: 6, border: "1px solid #F0F0F0",
            }}>
              <span style={{ fontSize: 13, color: "#262626", minWidth: 200 }}>{fmtCategory(row.key)}</span>
              {ids.length > 0 ? ids.map((id) => (
                <Tag key={id} color="blue" style={{ margin: 0, fontSize: 11 }}>{id.replace("_", " ")}</Tag>
              )) : (
                <span style={{ fontSize: 12, color: "#BFBFBF" }}>—</span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Section: Validation ─────────────────────────────────────────────────────

function Validation({ raw }: { raw: string }) {
  const items = parseKeyBlocks(raw);
  const LABELS: Record<string, string> = {
    missing_detection: "No missed detections",
    misclassification: "No misclassifications",
    count_consistency: "Count consistency",
  };
  return (
    <div>
      <SectionHeader step={3} icon="✅" title="Quality Checks" />
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {items.map((item) => {
          const isGood = item.value === "NO" || item.value === "PASS";
          return (
            <div key={item.key} style={{
              display: "flex", gap: 12, alignItems: "flex-start",
              padding: "10px 14px", borderRadius: 8,
              background: isGood ? "#F6FFED" : "#FFF1F0",
              border: `1px solid ${isGood ? "#B7EB8F" : "#FFA39E"}`,
            }}>
              <span style={{ fontSize: 16, flexShrink: 0, marginTop: 1 }}>
                {isGood ? "✓" : "✗"}
              </span>
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                  <span style={{ fontWeight: 600, fontSize: 13, color: "#1a1a2e" }}>
                    {LABELS[item.key] ?? fmtKey(item.key)}
                  </span>
                  <StatusBadge value={item.value} />
                </div>
                {item.sub.explanation && (
                  <div style={{ fontSize: 12, color: "#595959", lineHeight: 1.5 }}>
                    {item.sub.explanation}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Section: Checklist ───────────────────────────────────────────────────────

function Checklist({ raw }: { raw: string }) {
  const items = parseKeyBlocks(raw);
  return (
    <div>
      <SectionHeader step={4} icon="📋" title="Count Summary" />
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 8 }}>
        {items.map((item) => {
          const count = parseInt(item.value, 10);
          const locations = item.sub.locations;
          return (
            <div key={item.key} style={{
              padding: "10px 14px", borderRadius: 8,
              background: count > 0 ? "#F0F5FF" : "#FAFAFA",
              border: `1px solid ${count > 0 ? "#ADC6FF" : "#F0F0F0"}`,
            }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
                <span style={{ fontSize: 13, fontWeight: 500, color: "#262626" }}>{fmtCategory(item.key)}</span>
                <span style={{
                  fontWeight: 700, fontSize: 18, color: count > 0 ? "#2F54EB" : "#BFBFBF",
                }}>{count}</span>
              </div>
              {locations && count > 0 && (
                <div style={{ fontSize: 11, color: "#8C8C8C", lineHeight: 1.4 }}>{locations}</div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

const SECTION_RENDERERS: Record<string, React.ComponentType<{ raw: string }>> = {
  DETECTION_LIST: DetectionList,
  MATCHING:       Matching,
  CHECKLIST:      Checklist,
  VALIDATION:     Validation,
};

export function ReasoningTrace({ raw }: { raw: string }) {
  const sections = parseSections(raw).filter((s) => s.name in SECTION_RENDERERS);
  return (
    <div style={{
      fontFamily: '-apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", sans-serif',
      display: "flex", flexDirection: "column", gap: 24,
    }}>
      {sections.map((s) => {
        const Renderer = SECTION_RENDERERS[s.name];
        return <Renderer key={s.name} raw={s.raw} />;
      })}
    </div>
  );
}
