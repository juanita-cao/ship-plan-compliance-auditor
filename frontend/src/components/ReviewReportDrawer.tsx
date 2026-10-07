import { PrinterOutlined } from "@ant-design/icons";
import { useTranslation } from "react-i18next";
import { Button, Drawer } from "antd";
import { VESSEL_META } from "../config";
import { flagLabel, typeLabel, vesselName } from "../domain/vessels";
import { reportNo } from "../state/reviewStore";
import type { HistoryEntry } from "../state/reviewStore";

const BORDER = "#e5e8ed";
const SUB    = "#6b7280";
const TXT    = "#374151";

const VERDICT_COLOR: Record<string, string> = { GO: "#15803d", NO_GO: "#b91c1c", CONDITIONAL: "#b45309" };
const VERDICT_BG: Record<string, string> = {
  GO: "rgba(21,128,61,.10)", NO_GO: "rgba(185,28,28,.10)", CONDITIONAL: "rgba(180,83,9,.10)",
};
export const verdictText = (v: string) => (v === "NO_GO" ? "NO-GO" : v);

export function VerdictBadge({ verdict, size = 12 }: { verdict: string; size?: number }) {
  return (
    <span style={{
      color: VERDICT_COLOR[verdict] ?? TXT, background: VERDICT_BG[verdict] ?? "transparent",
      fontWeight: 700, fontSize: size, padding: "2px 9px", borderRadius: 4, whiteSpace: "nowrap", display: "inline-block",
    }}>
      {verdictText(verdict)}
    </span>
  );
}

const locale = (lang: string) => (lang.startsWith("zh") ? "zh-CN" : "en-GB");
export const fmtDate = (iso: string, lang = "en") =>
  new Date(iso).toLocaleDateString(locale(lang), { day: "2-digit", month: "short", year: "numeric" });
export const fmtDateTime = (iso: string, lang = "en") =>
  `${fmtDate(iso, lang)}  ${new Date(iso).toLocaleTimeString(locale(lang), { hour: "2-digit", minute: "2-digit" })}`;

const REGULATION_KEY: Record<string, string> = { GO: "report.regGO", NO_GO: "report.regNOGO", CONDITIONAL: "report.regCOND" };

const PRINT_CSS = `
@media print {
  body * { visibility: hidden !important; }
  #pvcb-report, #pvcb-report * { visibility: visible !important; }
  #pvcb-report { position: fixed; left: 0; top: 0; width: 100%; padding: 24px 32px; }
  .ant-drawer-content-wrapper { transform: none !important; box-shadow: none !important; }
  .pvcb-no-print { display: none !important; }
}`;

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div style={{ display: "flex", padding: "6px 0", borderBottom: `1px solid ${BORDER}`, fontSize: 12.5 }}>
      <div style={{ width: 130, flexShrink: 0, color: SUB }}>{label}</div>
      <div style={{ color: "#111827", fontWeight: 500 }}>{value}</div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginTop: 18 }}>
      <div style={{ fontSize: 11, fontWeight: 700, color: SUB, textTransform: "uppercase", letterSpacing: ".06em", marginBottom: 4 }}>
        {title}
      </div>
      {children}
    </div>
  );
}

export function ReviewReportDrawer({ entry, onClose }: { entry: HistoryEntry | null; onClose: () => void }) {
  const { t, i18n } = useTranslation();
  const lang = i18n.language;
  const meta = entry ? VESSEL_META[entry.projectId] : undefined;
  const refNo = entry ? reportNo(entry) : "";

  return (
    <Drawer open={!!entry} onClose={onClose} width={560} title={t("report.drawerTitle")} styles={{ body: { padding: 0 } }}
      extra={<Button size="small" icon={<PrinterOutlined />} onClick={() => window.print()}>{t("report.print")}</Button>}
    >
      <style>{PRINT_CSS}</style>
      {entry && (
        <div id="pvcb-report" style={{ padding: "22px 28px 28px", color: "#111827" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", borderBottom: "2px solid #0a1e3d", paddingBottom: 12 }}>
            <div>
              <div style={{ fontSize: 11, fontWeight: 700, color: "#0a1e3d", letterSpacing: ".08em" }}>{t("report.society")}</div>
              <div style={{ fontSize: 16, fontWeight: 700, marginTop: 4 }}>{t("report.docTitle")}</div>
            </div>
            <div style={{ textAlign: "right", fontSize: 11.5, color: SUB, lineHeight: 1.6 }}>
              <div>{t("report.reportNo")}</div>
              <div style={{ color: "#111827", fontWeight: 600 }}>{refNo}</div>
              <div>{fmtDate(entry.submittedAt, lang)}</div>
            </div>
          </div>

          <Section title={t("report.s1")}>
            <Field label={t("report.vesselName")} value={vesselName(entry.projectId, entry.projectLabel)} />
            <Field label={t("report.imoNumber")} value={meta?.imo ?? "—"} />
            <Field label={t("report.shipType")} value={meta ? typeLabel(meta.type, lang) : "—"} />
            <Field label={t("report.flagState")} value={meta ? flagLabel(meta.flag, lang) : "—"} />
            <Field label={t("report.yearBuild")} value={meta?.yearBuilt ?? "—"} />
          </Section>

          <Section title={t("report.s2")}>
            <Field label={t("report.planReviewed")} value={entry.imageLabel} />
            <Field label={t("report.surveyType")} value={t("report.surveyTypeValue")} />
            <Field label={t("report.regSet")} value="SOLAS II-2 · FSS Code" />
            <Field label={t("report.surveyor")} value={entry.reviewer} />
            <Field label={t("report.dateSigned")} value={fmtDateTime(entry.submittedAt, lang)} />
          </Section>

          <Section title={t("report.s3")}>
            <div style={{ display: "flex", gap: 32, padding: "8px 0" }}>
              {[
                [t("report.detected"), entry.instanceCount, "#111827"],
                [t("report.confirmed"), entry.confirmedCount, "#15803d"],
                [t("report.flagged"), entry.flaggedCount, entry.flaggedCount ? "#b91c1c" : "#111827"],
              ].map(([l, n, c]) => (
                <div key={l as string}>
                  <div style={{ fontSize: 11, color: SUB }}>{l}</div>
                  <div style={{ fontSize: 20, fontWeight: 700, color: c as string }}>{n}</div>
                </div>
              ))}
            </div>
          </Section>

          <Section title={t("report.s4")}>
            <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "8px 0" }}>
              <VerdictBadge verdict={entry.verdict} size={14} />
              <span style={{ fontSize: 12.5, color: TXT }}>{t(REGULATION_KEY[entry.verdict] ?? "report.regGO")}</span>
            </div>
          </Section>

          <Section title={t("report.s5")}>
            <div style={{ fontSize: 12.5, color: TXT, lineHeight: 1.6, padding: "6px 0" }}>
              {entry.note || t("report.noDeficiencies")}
            </div>
          </Section>

          <div style={{ marginTop: 36, display: "flex", justifyContent: "space-between", fontSize: 11.5, color: SUB }}>
            <div style={{ borderTop: "1px solid #9ca3af", paddingTop: 6, width: 200 }}>
              {t("report.sigSurveyor")}<br /><span style={{ color: "#111827" }}>{entry.reviewer}</span>
            </div>
            <div style={{ borderTop: "1px solid #9ca3af", paddingTop: 6, width: 160 }}>{t("report.sigDate")}<br /><span style={{ color: "#111827" }}>{fmtDate(entry.submittedAt, lang)}</span></div>
          </div>
          <div style={{ marginTop: 22, fontSize: 10.5, color: SUB }}>
            {t("report.disclaimer")}
          </div>
        </div>
      )}
    </Drawer>
  );
}

