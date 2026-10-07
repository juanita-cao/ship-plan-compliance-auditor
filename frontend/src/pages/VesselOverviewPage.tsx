import { useNavigate } from "react-router-dom";
import { VESSEL_FLEET, type VesselFleetEntry, type VesselStatus } from "../config";
import { typeLabel, flagLabel } from "../domain/vessels";
import { SidebarNav } from "../components/SidebarNav";
import { AppHeader } from "../components/AppHeader";
import { getHistory, getPendingQueue, useReviewStore } from "../state/reviewStore";
import { latestVerdict, pendingCount, vesselStatus } from "../domain/vesselStatus";
import { useTranslation } from "react-i18next";

const BORDER = "#e5e8ed";
const SUB    = "#6b7280";

// ── Derive live compliance/pending from reviewStore ───────────────────────────

function latestReviewDate(projectId: string): string | null {
  const entries = getHistory()
    .filter(h => h.projectId === projectId)
    .sort((a, b) => b.submittedAt.localeCompare(a.submittedAt));
  const iso = entries[0]?.submittedAt;
  return iso ? iso.slice(0, 10) : null;
}

// ── Compliance + status badges ────────────────────────────────────────────────

const VERDICT_STYLE: Record<string, React.CSSProperties> = {
  GO:          { color: "#15803d", fontWeight: 600, fontSize: 12 },
  NO_GO:       { color: "#b91c1c", fontWeight: 600, fontSize: 12 },
  CONDITIONAL: { color: "#b45309", fontWeight: 600, fontSize: 12 },
};

const STATUS_STYLE: Record<VesselStatus, { color: string; bg: string }> = {
  to_review:       { color: "#c2410c", bg: "rgba(234,88,12,.10)" },
  pending_confirm: { color: "#1d4ed8", bg: "rgba(47,84,235,.10)" },
  action_required: { color: "#b91c1c", bg: "rgba(185,28,28,.10)" },
  up_to_date:      { color: "#15803d", bg: "rgba(21,128,61,.10)" },
  scheduled:       { color: "#0e7490", bg: "rgba(8,145,178,.10)" },
};

function StatusBadge({ status, count, onClick }: { status: VesselStatus; count: number; onClick: () => void }) {
  const { t } = useTranslation();
  const st = STATUS_STYLE[status];
  return (
    <button
      type="button"
      onClick={e => { e.stopPropagation(); onClick(); }}
      style={{ color: st.color, background: st.bg, fontWeight: 600, fontSize: 12, padding: "2px 9px", borderRadius: 4, whiteSpace: "nowrap", border: 0, cursor: "pointer" }}
      onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.textDecoration = "underline"; }}
      onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.textDecoration = "none"; }}
    >
      {t(`status.${status}`)}{count > 1 ? ` · ${count}` : ""}
    </button>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

const TH: React.CSSProperties = {
  padding: "8px 14px", textAlign: "left",
  fontSize: 11, fontWeight: 600, color: SUB,
  textTransform: "uppercase", letterSpacing: ".06em",
  borderBottom: `1px solid ${BORDER}`, whiteSpace: "nowrap",
  background: "#fff",
};
const TH_NUM: React.CSSProperties = { ...TH, textAlign: "center" };
const TXT = "#374151";

function Row({ entry }: { entry: VesselFleetEntry }) {
  const { i18n } = useTranslation();
  const navigate = useNavigate();
  const pending = pendingCount(entry.historyKey);
  const lastDate = latestReviewDate(entry.historyKey) ?? entry.lastReviewMock;
  const verdict  = latestVerdict(entry.historyKey) ?? entry.complianceMock;
  const status: VesselStatus = vesselStatus(entry);

  const TD: React.CSSProperties = {
    padding: "10px 14px",
    verticalAlign: "middle",
    borderBottom: `1px solid ${BORDER}`,
    fontSize: 12.5, color: TXT,
  };

  const handleClick = () => {
    try { localStorage.setItem("pvcb_last_project", entry.historyKey); } catch {}
    navigate("/app/vessel", { state: { projectId: entry.historyKey } });
  };

  const openStatus = () => {
    if (status === "to_review") navigate(`/app/queue?vessel=${entry.historyKey}`);
    else if (status === "scheduled") handleClick();
    else navigate(`/app/history?vessel=${entry.historyKey}`);
  };

  return (
    <tr
      onClick={handleClick}
      style={{ cursor: "pointer", transition: "background .1s" }}
      onMouseEnter={e => { (e.currentTarget as HTMLTableRowElement).style.background = "#f8faff"; }}
      onMouseLeave={e => { (e.currentTarget as HTMLTableRowElement).style.background = ""; }}
    >
      <td style={{ ...TD, paddingLeft: 28 }}>
        <span style={{ color: "#1d4ed8", fontWeight: 600, fontSize: 13 }}>{entry.name}</span>
      </td>
      <td style={TD}>{typeLabel(entry.type, i18n.language)}</td>
      <td style={TD}>{entry.imo}</td>
      <td style={TD}>{entry.flagEmoji} {flagLabel(entry.flag, i18n.language)}</td>
      <td style={TD}>{entry.yearBuilt}</td>
      <td style={TD}>{lastDate}</td>
      <td style={{ ...TD, textAlign: "center" }}><StatusBadge status={status} count={status === "to_review" ? pending : 0} onClick={openStatus} /></td>
      <td style={{ ...TD, textAlign: "center", paddingRight: 28 }}>
        <span style={VERDICT_STYLE[verdict] ?? {}}>{verdict.replace("_", "-")}</span>
      </td>
    </tr>
  );
}

export function VesselOverviewPage() {
  useReviewStore();
  const { t } = useTranslation();

  return (
    <div style={{ display: "flex", flex: 1, minHeight: "100%" }}>
      <SidebarNav />

      {/* Main */}
      <div style={{ flex: 1, minWidth: 0, background: "#f0f2f5", display: "flex", flexDirection: "column" }}>
        {/* Top controls bar — aligns with sidebar brand height */}
        <AppHeader crumbs={[{ label: t("nav.overview") }]} />
        {/* Title row */}
        <div style={{ padding: "24px 28px 20px" }}>
          <h1 style={{ fontSize: 20, fontWeight: 700, color: "#111827", margin: 0 }}>{t("overview.title")}</h1>
        </div>

        {/* Table — flat, no card border, white fills edge-to-edge */}
        <div style={{ background: "#fff", borderTop: `1px solid ${BORDER}`, flex: 1 }}>
          {/* Section heading */}
          <div style={{ padding: "13px 28px 11px", borderBottom: `1px solid ${BORDER}` }}>
            <div style={{ fontWeight: 600, fontSize: 13.5 }}>{t("overview.section")}</div>
            <div style={{ fontSize: 11.5, color: SUB, marginTop: 2 }}>
              {t("overview.hint")}
            </div>
          </div>

          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr>
                  <th style={{ ...TH, paddingLeft: 28 }}>{t("overview.vessel")}</th>
                  <th style={TH}>{t("overview.type")}</th>
                  <th style={TH}>{t("overview.imo")}</th>
                  <th style={TH}>{t("overview.flag")}</th>
                  <th style={TH}>{t("overview.built")}</th>
                  <th style={TH}>{t("overview.latestReview")}</th>
                  <th style={TH_NUM}>{t("overview.statusCol")}</th>
                  <th style={{ ...TH_NUM, paddingRight: 28 }}>{t("overview.compliance")}</th>
                </tr>
              </thead>
              <tbody>
                {VESSEL_FLEET.map((v, i) => <Row key={i} entry={v} />)}
              </tbody>
            </table>
          </div>

        </div>
      </div>
    </div>
  );
}
