import { Modal } from "antd";
import { useTranslation } from "react-i18next";
import { VerdictBadge } from "./ReviewReportDrawer";

export interface SignOffSummary {
  projectLabel: string;
  imageLabel: string;
  aiVerdict: string | null;
  finalVerdict: string;
  confirmed: number;
  flagged: number;
  added: number;
  note: string;
  signer: string;
}

const SUB = "#6b7280";

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ display: "flex", padding: "7px 0", borderBottom: "1px solid #e5e8ed", fontSize: 13 }}>
      <div style={{ width: 120, flexShrink: 0, color: SUB }}>{label}</div>
      <div style={{ color: "#111827" }}>{children}</div>
    </div>
  );
}

export function SignOffModal({ open, summary, onCancel, onSign }: {
  open: boolean; summary: SignOffSummary; onCancel: () => void; onSign: () => void;
}) {
  const { t } = useTranslation();
  const overridden = summary.aiVerdict !== null && summary.aiVerdict !== summary.finalVerdict;
  return (
    <Modal
      open={open} title={t("signoff.title")} onCancel={onCancel} onOk={onSign}
      okText={t("signoff.ok")} cancelText={t("common.cancel")} width={480} destroyOnClose
    >
      <div style={{ marginTop: 8 }}>
        <Row label={t("signoff.vesselDeck")}><b>{summary.projectLabel}</b> · {summary.imageLabel}</Row>
        <Row label={t("signoff.ai")}>{summary.aiVerdict ? <VerdictBadge verdict={summary.aiVerdict} /> : "—"}</Row>
        <Row label={t("signoff.final")}>
          <VerdictBadge verdict={summary.finalVerdict} />
          {overridden && <span style={{ marginLeft: 8, fontSize: 12, color: "#b45309" }}>{t("signoff.overridden")}</span>}
        </Row>
        <Row label={t("signoff.detections")}>{t("signoff.counts", { c: summary.confirmed, f: summary.flagged, a: summary.added })}</Row>
        {summary.note && <Row label={t("signoff.note")}>{summary.note}</Row>}
      </div>
      <div style={{ marginTop: 14, fontSize: 12, color: SUB }}>
        {t("signoff.signingAs", { name: summary.signer })}
      </div>
    </Modal>
  );
}
