import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router-dom";
import type { TFunction } from "i18next";
import { vesselName } from "../domain/vessels";
import { AppHeader } from "../components/AppHeader";
import { SidebarNav } from "../components/SidebarNav";
import { getPendingQueue, useReviewStore } from "../state/reviewStore";
import type { AnalyzedEntry } from "../state/reviewStore";

const BORDER = "#e5e8ed";
const SUB    = "#6b7280";

const VERDICT_STYLE: Record<string, React.CSSProperties> = {
  GO:          { color: "#15803d", fontWeight: 700, fontSize: 12, background: "rgba(21,128,61,.10)",  padding: "2px 9px", borderRadius: 4 },
  NO_GO:       { color: "#b91c1c", fontWeight: 700, fontSize: 12, background: "rgba(185,28,28,.08)", padding: "2px 9px", borderRadius: 4 },
  CONDITIONAL: { color: "#b45309", fontWeight: 700, fontSize: 12, background: "rgba(180,83,9,.08)",  padding: "2px 9px", borderRadius: 4 },
};

function verdictLabel(v: string) {
  return v === "NO_GO" ? "NO-GO" : v === "NOT_APPLICABLE" ? "N/A" : v;
}

function relativeTime(iso: string, t: TFunction): string {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60_000);
  if (m < 1)  return t("queue.justNow");
  if (m < 60) return t("queue.minAgo", { n: m });
  const h = Math.floor(m / 60);
  if (h < 24) return t("queue.hrAgo", { n: h });
  return t("queue.daysAgo", { n: Math.floor(h / 24) });
}

const TH: React.CSSProperties = {
  padding: "8px 14px", textAlign: "left",
  fontSize: 11, fontWeight: 600, color: SUB,
  textTransform: "uppercase", letterSpacing: ".06em",
  borderBottom: `1px solid ${BORDER}`,
  whiteSpace: "nowrap", background: "#fff",
};
const TH_L: React.CSSProperties = { ...TH, paddingLeft: "var(--gutter)" };
const TH_R: React.CSSProperties = { ...TH, paddingRight: "var(--gutter)" };

function QueueRow({ entry }: { entry: AnalyzedEntry }) {
  const { t } = useTranslation();
  const navigate = useNavigate();

  const openReview = () => {
    navigate("/app/vessel", { state: { projectId: entry.projectId, imageStem: entry.imageStem, autoAnalyze: true } });
  };

  return (
    <tr
      style={{ cursor: "default" }}
      onMouseEnter={e => { (e.currentTarget as HTMLTableRowElement).style.background = "#f8faff"; }}
      onMouseLeave={e => { (e.currentTarget as HTMLTableRowElement).style.background = "transparent"; }}
    >
      <td style={{ padding: "10px 14px 10px var(--gutter)", borderBottom: `1px solid ${BORDER}` }}>
        <span style={{ color: "#1d4ed8", fontWeight: 600, fontSize: 13, cursor: "pointer" }}
          onClick={openReview}>
          {vesselName(entry.projectId, entry.projectLabel)}
        </span>
      </td>
      <td style={{ padding: "10px 14px", borderBottom: `1px solid ${BORDER}` }}>
        <div style={{ fontSize: 12.5, color: "#374151" }}>{entry.imageLabel}</div>
      </td>
      <td style={{ padding: "10px 14px", borderBottom: `1px solid ${BORDER}` }}>
        <span style={{ fontSize: 12.5, color: "#374151", fontVariantNumeric: "tabular-nums" }}>
          {relativeTime(entry.analyzedAt, t)}
        </span>
      </td>
      <td style={{ padding: "10px 14px", borderBottom: `1px solid ${BORDER}` }}>
        {entry.instanceCount != null
          ? <span style={{ fontSize: 12.5, color: "#374151" }}>{t("queue.items", { n: entry.instanceCount })}</span>
          : <span style={{ color: SUB, fontSize: 12 }}>—</span>}
      </td>
      <td style={{ padding: "10px 14px", borderBottom: `1px solid ${BORDER}` }}>
        {entry.aiVerdict
          ? <span style={VERDICT_STYLE[entry.aiVerdict] ?? { fontSize: 12 }}>{verdictLabel(entry.aiVerdict)}</span>
          : <span style={{ color: SUB, fontSize: 12 }}>—</span>}
      </td>
      <td style={{ padding: "10px 14px", borderBottom: `1px solid ${BORDER}`, textAlign: "center" }}>
        <span style={{
          color: "#ea580c", fontWeight: 600, fontSize: 12,
          background: "rgba(234,88,12,.1)", padding: "3px 10px", borderRadius: 4,
          display: "inline-flex", alignItems: "center", gap: 5,
        }}>
          <span style={{
            width: 5, height: 5, borderRadius: "50%", background: "#ea580c",
            animation: "pvcb-pulse 1.6s ease-in-out infinite", flexShrink: 0,
          }} />
          {t("queue.pendingReview")}
        </span>
      </td>
      <td style={{ padding: "10px var(--gutter) 10px 14px", borderBottom: `1px solid ${BORDER}` }}>
        <button
          onClick={openReview}
          style={{
            border: "1px solid #d1d5db", background: "#fff", borderRadius: 5,
            padding: "3px 11px", fontSize: 12, color: "#374151",
            cursor: "pointer", whiteSpace: "nowrap",
          }}
          onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.borderColor = "#93c5fd"; (e.currentTarget as HTMLButtonElement).style.color = "#2f54eb"; }}
          onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.borderColor = "#d1d5db"; (e.currentTarget as HTMLButtonElement).style.color = "#374151"; }}
        >
          {t("queue.openReview")}
        </button>
      </td>
    </tr>
  );
}

export function ReviewQueuePage() {
  const { t } = useTranslation();
  useReviewStore();
  const [params, setParams] = useSearchParams();
  const all = getPendingQueue();
  const vessels = Array.from(new Map(all.map(e => [e.projectId, e.projectLabel])).keys());
  const wanted = params.get("vessel");
  const vesselFilter = wanted && vessels.includes(wanted) ? wanted : "all";
  const queue = vesselFilter === "all" ? all : all.filter(e => e.projectId === vesselFilter);
  const setVessel = (v: string) => setParams(v === "all" ? {} : { vessel: v }, { replace: true });

  return (
    <>
      <style>{`
        @keyframes pvcb-pulse { 0%,100%{opacity:1} 50%{opacity:.3} }
      `}</style>

      <div style={{ display: "flex", flex: 1, minHeight: "100%" }}>
        <SidebarNav />

        <div style={{ flex: 1, minWidth: 0, background: "#f0f2f5", display: "flex", flexDirection: "column" }}>
          <AppHeader crumbs={[{ label: t("nav.queue") }]} />

          <div style={{ padding: "24px var(--gutter) 20px" }}>
            <h1 style={{ fontSize: 20, fontWeight: 700, color: "#111827", margin: 0 }}>
              {t("queue.title")}
            </h1>
          </div>

          {vessels.length > 1 && (
            <div style={{ padding: "0 var(--gutter) 16px", display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
              <span style={{ fontSize: 11, fontWeight: 600, color: SUB, letterSpacing: ".06em", marginRight: 2 }}>{t("queue.filterVessel").toUpperCase()}</span>
              {["all", ...vessels].map(v => {
                const active = vesselFilter === v;
                return (
                  <button key={v} onClick={() => setVessel(v)} style={{
                    border: `1px solid ${active ? "#93c5fd" : BORDER}`, background: active ? "#eff6ff" : "#fff",
                    color: active ? "#2f54eb" : "#374151", fontWeight: active ? 600 : 400,
                    borderRadius: 14, padding: "3px 11px", fontSize: 12, cursor: "pointer",
                  }}>{v === "all" ? t("queue.all") : vesselName(v)}</button>
                );
              })}
            </div>
          )}

          {/* Table */}
          <div style={{ background: "#fff", borderTop: `1px solid ${BORDER}`, flex: 1 }}>
            {/* Section header */}
            <div style={{ padding: "13px var(--gutter) 11px", borderBottom: `1px solid ${BORDER}` }}>
              <div>
                <div style={{ fontSize: 13.5, fontWeight: 600 }}>{t("queue.section")}</div>
                <div style={{ fontSize: 11.5, color: SUB, marginTop: 2 }}>
                  {t("queue.hint")}
                </div>
              </div>
            </div>

            {queue.length === 0 ? (
              <div style={{ padding: "64px var(--gutter)", textAlign: "center" }}>
                <div style={{ fontSize: 28, marginBottom: 10, opacity: .35 }}>✓</div>
                <div style={{ fontSize: 15, color: "#374151", fontWeight: 600 }}>{t("queue.emptyTitle")}</div>
                <div style={{ fontSize: 13, color: SUB, marginTop: 4 }}>
                  {t("queue.emptyBody")}
                </div>
              </div>
            ) : (
              <>
                <div style={{ overflowX: "auto" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse" }}>
                    <thead>
                      <tr style={{ background: "#fff" }}>
                        <th style={TH_L}>{t("queue.vessel")}</th>
                        <th style={TH}>{t("queue.deck")}</th>
                        <th style={TH}>{t("queue.analyzed")}</th>
                        <th style={TH}>{t("queue.detections")}</th>
                        <th style={TH}>{t("queue.aiVerdict")}</th>
                        <th style={{ ...TH, textAlign: "center" }}>{t("queue.statusCol")}</th>
                        <th style={TH_R}></th>
                      </tr>
                    </thead>
                    <tbody>
                      {queue.map(entry => (
                        <QueueRow key={`${entry.projectId}/${entry.imageStem}`} entry={entry} />
                      ))}
                    </tbody>
                  </table>
                </div>
                <div style={{ padding: "8px var(--gutter)", fontSize: 11, color: SUB, borderTop: `1px solid ${BORDER}`, background: "#fafbfc", display: "flex", justifyContent: "space-between" }}>
                  <span>{queue.length === 1 ? t("queue.footerOne") : t("queue.footerMany", { n: queue.length })}</span>
                  <span>{t("queue.footerNote")}</span>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
