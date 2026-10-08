import { Statistic } from "antd";
import { useTranslation } from "react-i18next";

interface Props {
  totalByCategory: Record<string, number>;
}

export function MetricsRow({ totalByCategory }: Props) {
  const { t } = useTranslation();
  const typeCount = Object.values(totalByCategory).filter((n) => n > 0).length;
  const instanceCount = Object.values(totalByCategory).reduce((a, b) => a + b, 0);
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 24, padding: "12px 16px", background: "#fff", borderRadius: 8, boxShadow: "0 1px 4px rgba(0,0,0,.08)", marginBottom: 16 }}>
      <Statistic title={t("metrics.types")} value={typeCount} />
      <Statistic title={t("metrics.located")} value={instanceCount} />
    </div>
  );
}
