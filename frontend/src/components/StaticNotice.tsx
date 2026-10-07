import { PlayCircleOutlined } from "@ant-design/icons";
import { Button } from "antd";
import { useTranslation } from "react-i18next";
import { PlanStepper } from "./PlanStepper";
import type { PlanStep } from "../state/uploadState";

/** Optional link to a recorded walkthrough (hosted elsewhere; large videos are not bundled with the static site). */
const WALKTHROUGH_URL = (import.meta.env.VITE_WALKTHROUGH_URL as string | undefined) ?? "";

/** Shown instead of the upload workflow in the static demo build (ADR-F36). Nothing is faked. */
export function StaticNotice({ step, onBack }: { step: PlanStep; onBack?: () => void }) {
  const { t } = useTranslation();
  return (
    <div style={{ background: "#fff", border: "1px solid #e5e8ed", borderRadius: 10, padding: "20px 22px", marginTop: 8 }}>
      <PlanStepper current={step} />
      <div style={{ maxWidth: 640, margin: "28px auto 12px", textAlign: "center" }}>
        <div style={{ fontSize: 16, fontWeight: 600, color: "#111827" }}>{t("staticDemo.title")}</div>
        <div style={{ fontSize: 13, color: "#6b7280", margin: "8px 0 18px", lineHeight: 1.6 }}>{t("staticDemo.body")}</div>
        <div style={{ display: "flex", gap: 8, justifyContent: "center" }}>
          {WALKTHROUGH_URL && <Button type="primary" icon={<PlayCircleOutlined />} href={WALKTHROUGH_URL} target="_blank" rel="noopener noreferrer">{t("staticDemo.watch")}</Button>}
          {onBack && <Button onClick={onBack}>{t("staticDemo.back")}</Button>}
        </div>
      </div>
    </div>
  );
}
