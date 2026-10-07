import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router-dom";
import { vesselName } from "../domain/vessels";
import { AppHeader } from "../components/AppHeader";
import { SidebarNav } from "../components/SidebarNav";
import { ReviewReportDrawer, VerdictBadge, fmtDate } from "../components/ReviewReportDrawer";
import { getHistory, useReviewStore } from "../state/reviewStore";
import type { HistoryEntry } from "../state/reviewStore";

const BORDER = "#e5e8ed";
const SUB    = "#6b7280";
const TXT    = "#374151";

// ── Filter chips ──────────────────────────────────────────────────────────────

function Chip({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button onClick={onClick} style={{
      border: `1px solid ${active ? "#93c5fd" : BORDER}`, background: active ? "#eff6ff" : "#fff",
      color: active ? "#2f54eb" : TXT, fontWeight: active ? 600 : 400,
      borderRadius: 14, padding: "3px 11px", fontSize: 12, cursor: "pointer",
    }}>{label}</button>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

const TH: React.CSSProperties = {
  padding: "8px 14px", textAlign: "left", fontSize: 11, fontWeight: 600, color: SUB,
  textTransform: "uppercase", letterSpacing: ".06em",
  borderBottom: `1px solid ${BORDER}`, whiteSpace: "nowrap", background: "#fff",
};
const TD: React.CSSProperties = {
  padding: "10px 14px", verticalAlign: "middle", borderBottom: `1px solid ${BORDER}`,
  fontSize: 12.5, color: TXT,
};

export function HistoryPage() {
  const { t, i18n } = useTranslation();
  useReviewStore();
  const allEntries = getHistory();
  const [verdictFilter, setVerdictFilter] = useState("all");
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const wantedVessel = params.get("vessel");
  const [vesselFilter, setVesselFilter] = useState(() => (wantedVessel && allEntries.some(e => e.projectId === wantedVessel) ? wantedVessel : "all"));
  const [selected, setSelected]           = useState<HistoryEntry | null>(null);

  const vessels = Array.from(new Map(allEntries.map(e => [e.projectId, e.projectLabel])).entries());
  const visible = allEntries
    .filter(e => (verdictFilter === "all" || e.verdict === verdictFilter) && (vesselFilter === "all" || e.projectId === vesselFilter))
    .sort((a, b) => b.submittedAt.localeCompare(a.submittedAt));

  return (
    <div style={{ display: "flex", flex: 1, minHeight: "100%" }}>
      <SidebarNav />

      <div style={{ flex: 1, minWidth: 0, background: "#f0f2f5", display: "flex", flexDirection: "column" }}>
        <AppHeader crumbs={[{ label: t("nav.history") }]} />

        <div style={{ padding: "24px 28px 12px" }}>
          <h1 style={{ fontSize: 20, fontWeight: 700, color: "#111827", margin: 0 }}>{t("history.title")}</h1>
        </div>

        <div style={{ padding: "0 28px 16px", display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
          <span style={{ fontSize: 11, fontWeight: 600, color: SUB, letterSpacing: ".06em", marginRight: 2 }}>{t("history.verdictFilter").toUpperCase()}</span>
          <Chip label={t("history.all")} active={verdictFilter === "all"} onClick={() => setVerdictFilter("all")} />
          <Chip label="GO" active={verdictFilter === "GO"} onClick={() => setVerdictFilter("GO")} />
          <Chip label="NO-GO" active={verdictFilter === "NO_GO"} onClick={() => setVerdictFilter("NO_GO")} />
          <Chip label={t("history.conditional")} active={verdictFilter === "CONDITIONAL"} onClick={() => setVerdictFilter("CONDITIONAL")} />
          <span style={{ width: 16 }} />
          <span style={{ fontSize: 11, fontWeight: 600, color: SUB, letterSpacing: ".06em", marginRight: 2 }}>{t("history.vesselFilter").toUpperCase()}</span>
          <Chip label={t("history.all")} active={vesselFilter === "all"} onClick={() => setVesselFilter("all")} />
          {vessels.map(([id, label]) => (
            <Chip key={id} label={vesselName(id, label)} active={vesselFilter === id} onClick={() => setVesselFilter(id)} />
          ))}
        </div>

        <div style={{ background: "#fff", borderTop: `1px solid ${BORDER}`, flex: 1 }}>
          <div style={{ padding: "13px 28px 11px", borderBottom: `1px solid ${BORDER}` }}>
            <div style={{ fontWeight: 600, fontSize: 13.5 }}>{t("history.section")}</div>
            <div style={{ fontSize: 11.5, color: SUB, marginTop: 2 }}>
              {t("history.hint")}
            </div>
          </div>

          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr>
                  <th style={{ ...TH, paddingLeft: 28 }}>{t("history.vessel")}</th>
                  <th style={TH}>{t("history.deck")}</th>
                  <th style={TH}>{t("history.verdict")}</th>
                  <th style={TH}>{t("history.confFlag")}</th>
                  <th style={TH}>{t("history.reviewer")}</th>
                  <th style={TH}>{t("history.submitted")}</th>
                  <th style={{ ...TH, paddingRight: 28 }}></th>
                </tr>
              </thead>
              <tbody>
                {visible.map(e => (
                  <tr key={e.id}
                    onMouseEnter={ev => { (ev.currentTarget as HTMLTableRowElement).style.background = "#f8faff"; }}
                    onMouseLeave={ev => { (ev.currentTarget as HTMLTableRowElement).style.background = ""; }}
                  >
                    <td style={{ ...TD, paddingLeft: 28 }}><span style={{ color: "#111827", fontWeight: 600, fontSize: 13 }}>{vesselName(e.projectId, e.projectLabel)}</span></td>
                    <td style={TD}>{e.imageLabel}</td>
                    <td style={TD}><VerdictBadge verdict={e.verdict} /></td>
                    <td style={TD}>{e.confirmedCount} / {e.flaggedCount}</td>
                    <td style={TD}>{e.reviewer}</td>
                    <td style={TD}>{fmtDate(e.submittedAt, i18n.language)}</td>
                    <td style={{ ...TD, paddingRight: 28, textAlign: "right" }}>
                      <button onClick={() => setSelected(e)} style={{
                        border: "1px solid #d1d5db", background: "#fff", borderRadius: 5,
                        padding: "3px 11px", fontSize: 12, color: TXT, cursor: "pointer",
                      }}>{t("history.viewReport")}</button>
                      <button onClick={() => navigate("/app/vessel", { state: { projectId: e.projectId, imageStem: e.imageStem } })} style={{
                        border: 0, background: "transparent", marginLeft: 6,
                        padding: "3px 6px", fontSize: 12, color: "#2f54eb", cursor: "pointer",
                      }}>{t("history.openVessel")}</button>
                    </td>
                  </tr>
                ))}
                {visible.length === 0 && (
                  <tr><td colSpan={7} style={{ ...TD, padding: "40px 28px", textAlign: "center", color: SUB }}>{t("history.noMatch")}</td></tr>
                )}
              </tbody>
            </table>
          </div>

          <div style={{ padding: "8px 28px", fontSize: 11, color: SUB, borderTop: `1px solid ${BORDER}`, background: "#fafbfc" }}>
            {t("history.footer", { shown: visible.length, total: allEntries.length })}
          </div>
        </div>
      </div>

      <ReviewReportDrawer entry={selected} onClose={() => setSelected(null)} />
    </div>
  );
}
