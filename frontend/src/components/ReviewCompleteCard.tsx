import { CheckCircleFilled } from "@ant-design/icons";
import { Button } from "antd";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { ReviewReportDrawer, VerdictBadge } from "./ReviewReportDrawer";
import { getPendingQueue, reportNo, useReviewStore, type HistoryEntry } from "../state/reviewStore";

const SUB = "#6b7280";

export function ReviewCompleteCard({ entry }: { entry: HistoryEntry }) {
  useReviewStore();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [report, setReport] = useState(false);
  const queue = getPendingQueue();
  const next = queue[0];

  const goNext = () => {
    if (next) navigate("/app/vessel", { state: { projectId: next.projectId, imageStem: next.imageStem, autoAnalyze: true } });
    else navigate("/app/queue");
  };

  return (
    <div id="human-review" style={{ background: "#fff", borderRadius: 8, boxShadow: "0 1px 4px rgba(0,0,0,.08)", marginTop: 16, padding: "20px 24px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <CheckCircleFilled style={{ color: "#15803d", fontSize: 20 }} />
        <span style={{ fontSize: 15, fontWeight: 700 }}>{t("complete.title")}</span>
        <span style={{ marginLeft: "auto", fontSize: 12, color: SUB }}>{reportNo(entry)}</span>
      </div>
      <div style={{ marginTop: 12, display: "flex", alignItems: "center", gap: 10, fontSize: 13, color: "#374151" }}>
        {t("complete.final")} <VerdictBadge verdict={entry.verdict} />
        <span>{t("complete.counts", { c: entry.confirmedCount, f: entry.flaggedCount })}</span>
      </div>
      <div style={{ marginTop: 6, fontSize: 12, color: SUB }}>
        {queue.length === 0 ? t("complete.clear") : queue.length === 1 ? t("complete.leftOne") : t("complete.leftMany", { n: queue.length })}
      </div>
      <div style={{ marginTop: 16, display: "flex", gap: 8 }}>
        <Button onClick={() => setReport(true)}>{t("complete.viewReport")}</Button>
        <Button type="primary" onClick={goNext}>
          {next ? t("complete.next") : t("complete.back")}
        </Button>
        <Button onClick={() => navigate("/app/history")}>{t("complete.history")}</Button>
      </div>
      <ReviewReportDrawer entry={report ? entry : null} onClose={() => setReport(false)} />
    </div>
  );
}
