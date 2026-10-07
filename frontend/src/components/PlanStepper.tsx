import { Steps } from "antd";
import { useTranslation } from "react-i18next";
import type { PlanStep } from "../state/uploadState";

/** ① Upload → ② Segment → ③ Review decks → ④ Analyze (ADR-F34). Steps before `current` show as done. */
export function PlanStepper({ current }: { current: PlanStep }) {
  const { t } = useTranslation();
  return (
    <Steps
      size="small" current={current - 1} className="plan-stepper"
      items={[{ title: t("upload.s1") }, { title: t("upload.s2") }, { title: t("upload.s3") }, { title: t("upload.s4") }]}
    />
  );
}
