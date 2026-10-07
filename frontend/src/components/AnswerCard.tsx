import { CopyOutlined, DislikeOutlined, LikeOutlined } from "@ant-design/icons";
import { Button, message } from "antd";
import { Fragment, useState } from "react";
import { useTranslation } from "react-i18next";
import type { AskAnswer, AskSource } from "../content/askDemo";

const BORDER = "#e5e8ed";
const SUB = "#6b7280";
const BLUE = "#1d4ed8";

/** `**bold**` and `[n]` citations are the only markup; a citation opens its source. */
function Rich({ text, onCite }: { text: string; onCite?: (n: number) => void }) {
  const parts = text.split(/(\*\*[^*]+\*\*|\[\d+\])/g).filter(Boolean);
  return (
    <>
      {parts.map((p, i) => {
        if (p.startsWith("**")) return <b key={i}>{p.slice(2, -2)}</b>;
        const m = /^\[(\d+)\]$/.exec(p);
        if (m && onCite) return <a key={i} role="button" onClick={() => onCite(Number(m[1]))} style={{ color: BLUE, cursor: "pointer" }}>{p}</a>;
        return <Fragment key={i}>{p}</Fragment>;
      })}
    </>
  );
}

export function AnswerCard({ answer, asOf, onOpenSource, onAction }: {
  answer: AskAnswer; asOf: string; onOpenSource: (s: AskSource) => void; onAction: (to: string, state?: unknown) => void;
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [vote, setVote] = useState<"up" | "down" | null>(null);
  const [tag, setTag] = useState<string | null>(null);
  const cite = (n: number) => { const s = answer.sources[n - 1]; if (s) onOpenSource(s); };

  const copy = async () => {
    try { await navigator.clipboard.writeText(answer.draft ?? ""); message.success(t("ask.copied")); }
    catch { message.warning(t("ask.copyFailed")); }
  };

  return (
    <div style={{ background: "#fff", border: `1px solid ${BORDER}`, borderRadius: 10, padding: "14px 18px", fontSize: 13.5, lineHeight: 1.6, color: "#1f2937" }}>
      <div><Rich text={answer.short} />{answer.proposal && <span style={{ color: SUB }}> ({t("ask.proposal")})</span>}</div>

      {answer.draft && (
        <div style={{ marginTop: 10, background: "#f8fafc", border: `1px solid ${BORDER}`, borderRadius: 8, padding: "12px 14px" }}>
          <div style={{ whiteSpace: "pre-wrap", fontSize: 13 }}>{answer.draft}</div>
          <div style={{ marginTop: 10, display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
            <Button size="small" icon={<CopyOutlined />} onClick={copy}>{t("ask.copy")}</Button>
            <span style={{ fontSize: 12, color: SUB }}>{t("ask.draftOnly")}</span>
          </div>
        </div>
      )}

      {answer.action && (
        <div style={{ marginTop: 10 }}>
          <Button size="small" type="primary" ghost onClick={() => onAction(answer.action!.to, answer.action!.state)}>{answer.action.label}</Button>
        </div>
      )}

      {answer.basis.length > 0 && (
        <div style={{ marginTop: 8 }}>
          <a role="button" aria-expanded={open} onClick={() => setOpen(o => !o)} style={{ fontSize: 12.5, color: BLUE, cursor: "pointer" }}>
            {open ? `${t("ask.hideBasis")} ▲` : `${t("ask.showBasis")} ▼`}
          </a>
          {open && (
            <ul style={{ margin: "8px 0 0", paddingLeft: 20, display: "flex", flexDirection: "column", gap: 5, fontSize: 13 }}>
              {answer.basis.map((b, i) => <li key={i}><Rich text={b} onCite={cite} /></li>)}
            </ul>
          )}
        </div>
      )}

      {answer.sources.length > 0 && (
        <div style={{ marginTop: 10, borderTop: `1px solid ${BORDER}`, paddingTop: 8, display: "flex", flexDirection: "column", gap: 2, fontSize: 12 }}>
          {answer.sources.map((s, i) => (
            <div key={i}>
              <span style={{ color: SUB }}>[{i + 1}] </span>
              <a role="button" onClick={() => onOpenSource(s)} style={{ color: BLUE, cursor: "pointer" }}>{s.label}</a>
            </div>
          ))}
        </div>
      )}

      <div style={{ marginTop: 8, display: "flex", alignItems: "center", gap: 6, fontSize: 11.5, color: SUB, flexWrap: "wrap" }}>
        <span>{t("ask.asOf", { time: asOf })}</span>
        <Button size="small" type="text" aria-label={t("ask.good")} icon={<LikeOutlined style={{ color: vote === "up" ? BLUE : undefined }} />} onClick={() => setVote("up")} />
        <Button size="small" type="text" aria-label={t("ask.bad")} icon={<DislikeOutlined style={{ color: vote === "down" ? "#b91c1c" : undefined }} />} onClick={() => setVote("down")} />
        {vote === "down" && !tag && (
          <span style={{ display: "inline-flex", gap: 6 }}>
            {(["tagTooLong", "tagWrong", "tagMissing", "tagNotUseful"] as const).map(k => (
              <Button key={k} size="small" onClick={() => setTag(k)}>{t(`ask.${k}`)}</Button>
            ))}
          </span>
        )}
        {(vote === "up" || tag) && <span>{t("ask.thanks")}</span>}
      </div>
    </div>
  );
}
