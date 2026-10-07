import { Alert, Badge, Tag } from "antd";
import { useTranslation } from "react-i18next";
import type { ComplianceResult } from "../api/client";

interface Props {
  result: ComplianceResult;
}

const STATUS_COLOR: Record<string, string> = {
  pass: "green",
  fail: "red",
  warning: "orange",
  not_applicable: "gray",
};

const STATUS_KEY: Record<string, string> = {
  pass: "compliance.pass",
  fail: "compliance.fail",
  warning: "compliance.warn",
  not_applicable: "compliance.na",
};

const VERDICT_COLOR: Record<string, string> = {
  GO: "#00b42a",
  NO_GO: "#f53f3f",
  CONDITIONAL: "#ff7d00",
};

export function CompliancePanel({ result }: Props) {
  const { t } = useTranslation();
  return (
    <div style={{ marginTop: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
        <span style={{ fontWeight: 700, fontSize: 15, color: "#1d2129" }}>{t("compliance.title")}</span>
        <Tag color={VERDICT_COLOR[result.verdict] ?? "#86909c"} style={{ fontWeight: 700 }}>
          {result.verdict}
        </Tag>
        {result.is_mock && <Tag color="orange">{t("compliance.mock")}</Tag>}
      </div>

      {result.is_mock && (
        <Alert
          type="warning"
          message={t("compliance.notice")}
          style={{ marginBottom: 12 }}
        />
      )}

      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
        <thead>
          <tr style={{ background: "#f7f8fa", color: "#86909c" }}>
            <th style={th}>{t("compliance.article")}</th>
            <th style={th}>{t("compliance.rule")}</th>
            <th style={th}>{t("compliance.required")}</th>
            <th style={th}>{t("compliance.found")}</th>
            <th style={th}>{t("compliance.status")}</th>
          </tr>
        </thead>
        <tbody>
          {result.checks.map((c) => (
            <tr key={c.rule_id} style={{ borderBottom: "1px solid #f0f0f0" }}>
              <td style={td}>{c.article}</td>
              <td style={td}>{c.description}</td>
              <td style={{ ...td, textAlign: "center" }}>{c.required ?? "—"}</td>
              <td style={{ ...td, textAlign: "center" }}>{c.found ?? "—"}</td>
              <td style={{ ...td, textAlign: "center" }}>
                <Badge
                  color={STATUS_COLOR[c.status] ?? "gray"}
                  text={STATUS_KEY[c.status] ? t(STATUS_KEY[c.status]) : c.status.toUpperCase()}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const th: React.CSSProperties = { padding: "6px 10px", textAlign: "left", fontWeight: 600, fontSize: 12 };
const td: React.CSSProperties = { padding: "8px 10px", verticalAlign: "top" };
