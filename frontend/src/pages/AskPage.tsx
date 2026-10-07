import { PlusOutlined, SendOutlined } from "@ant-design/icons";
import { Alert, Button, Input } from "antd";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { get, type ProjectInfo } from "../api/client";
import { AnswerCard } from "../components/AnswerCard";
import { AppHeader } from "../components/AppHeader";
import { ReviewReportDrawer } from "../components/ReviewReportDrawer";
import { SidebarNav } from "../components/SidebarNav";
import { ASK_QA, fallbackAnswer, matchQuestion, type AskAnswer, type AskSource, type Lang } from "../content/askDemo";
import { getHistory, getPendingQueue, useReviewStore } from "../state/reviewStore";
import type { HistoryEntry } from "../state/reviewStore";

type Turn =
  | { role: "user"; text: string }
  | { role: "ai"; answer: AskAnswer; asOf: string };

const BORDER = "#e5e8ed";
const SUB = "#6b7280";

export function AskPage() {
  const { t, i18n } = useTranslation();
  const lang: Lang = i18n.language.startsWith("zh") ? "zh" : "en";
  const navigate = useNavigate();
  const { data: projects = [] } = useQuery<ProjectInfo[]>({ queryKey: ["projects"], queryFn: () => get<ProjectInfo[]>("/projects"), staleTime: Infinity });
  const [free, setFree] = useState<Turn[] | null>(null);   // null = showing the recorded conversation
  const [text, setText] = useState("");
  const [busy, setBusy] = useState<number | null>(null);   // index into t("ask.thinking") while "thinking"
  const [allChips, setAllChips] = useState(false);
  const [report, setReport] = useState<HistoryEntry | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const timers = useRef<number[]>([]);

  useEffect(() => () => { timers.current.forEach(clearTimeout); }, []);
  useEffect(() => { if (free) endRef.current?.scrollIntoView?.({ behavior: "smooth", block: "end" }); }, [free, busy]);

  // Like the email app, the page opens with the recorded conversation already on screen.
  const store = useReviewStore();
  const recorded = useMemo<Turn[]>(() => {
    if (!projects.length) return [];
    const now = Date.now();
    const c = { lang, now, history: getHistory(), queue: getPendingQueue(), projects };
    const asOf = new Date(now).toTimeString().slice(0, 5);
    return ASK_QA.flatMap<Turn>(q => [{ role: "user", text: q.question[lang] }, { role: "ai", answer: q.answer(c), asOf }]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lang, projects, store]);
  const turns = free ?? recorded;
  const setTurns = (f: (ts: Turn[]) => Turn[]) => setFree(prev => f(prev ?? recorded));

  const steps = t("ask.thinking", { returnObjects: true }) as unknown as string[];

  const ask = (q: string) => {
    const question = q.trim();
    if (!question || busy !== null) return;
    setText("");
    setTurns(ts => [...ts, { role: "user", text: question }]);
    setBusy(0);
    timers.current.push(window.setTimeout(() => setBusy(1), 300), window.setTimeout(() => setBusy(2), 600));
    timers.current.push(window.setTimeout(() => {
      const now = Date.now();
      const c = { lang, now, history: getHistory(), queue: getPendingQueue(), projects };
      const qa = matchQuestion(question);
      const answer = qa ? qa.answer(c) : fallbackAnswer(c);
      setTurns(ts => [...ts, { role: "ai", answer, asOf: new Date(now).toTimeString().slice(0, 5) }]);
      setBusy(null);
    }, 900));
  };

  const reset = () => { timers.current.forEach(clearTimeout); timers.current = []; setFree([]); setBusy(null); setText(""); };

  const openSource = (s: AskSource) => {
    if (s.kind === "report") { const e = getHistory().find(h => h.id === s.id); if (e) setReport(e); }
    else if (s.kind === "vessel") navigate("/app/vessel", { state: { projectId: s.id } });
    else if (s.kind === "queue") navigate(s.id === "history" ? "/app/history" : "/app/queue");
    else if (s.kind === "guide") navigate({ pathname: "/guide", hash: `#${s.id}` });
    else navigate({ pathname: "/guide", hash: "#regulations" });
  };

  const chips = allChips ? ASK_QA : ASK_QA.slice(0, 4);

  return (
    <div style={{ display: "flex", flex: 1, minHeight: "100%" }}>
      <SidebarNav />
      <div style={{ flex: 1, minWidth: 0, background: "#f0f2f5", display: "flex", flexDirection: "column", height: "100vh" }}>
        <AppHeader crumbs={[{ label: t("nav.ask") }]} />

        <div style={{ flex: 1, overflowY: "auto" }}>
          <div style={{ padding: "24px 28px 12px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
              <h1 style={{ fontSize: 20, fontWeight: 700, color: "#111827", margin: 0 }}>{t("ask.title")}</h1>
              <Button icon={<PlusOutlined />} onClick={reset}>{t("ask.newChat")}</Button>
            </div>
            <div style={{ fontSize: 12.5, color: SUB, margin: "6px 0 10px" }}>{t("ask.intro")}</div>
            <Alert type="info" showIcon message={t("ask.banner")} style={{ fontSize: 12.5 }} />

            <div style={{ display: "flex", flexDirection: "column", gap: 14, marginTop: 18 }}>
              {turns.length === 0 && (
                <div>
                  <div style={{ fontSize: 11, fontWeight: 600, color: SUB, letterSpacing: ".06em", marginBottom: 8 }}>{t("ask.tryAsking").toUpperCase()}</div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 8, alignItems: "flex-start" }}>
                    {chips.map(q => (
                      <button key={q.id} onClick={() => ask(q.question[lang])} style={{
                        border: `1px solid ${BORDER}`, background: "#fff", borderRadius: 18, padding: "7px 14px",
                        fontSize: 13, color: "#374151", cursor: "pointer", textAlign: "left",
                      }}>{q.question[lang]}</button>
                    ))}
                    <a role="button" onClick={() => setAllChips(v => !v)} style={{ fontSize: 12.5, color: "#1d4ed8", cursor: "pointer" }}>{allChips ? t("ask.fewer") : t("ask.more")}</a>
                  </div>
                </div>
              )}

              {turns.map((turn, i) => turn.role === "user" ? (
                <div key={i} style={{ alignSelf: "flex-end", maxWidth: "75%", background: "#1d4ed8", color: "#fff", borderRadius: 16, padding: "8px 16px", fontSize: 13.5 }}>{turn.text}</div>
              ) : (
                <div key={i} style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
                  <span style={{ fontSize: 11, fontWeight: 700, color: SUB, width: 22, paddingTop: 12 }}>{t("ask.ai")}</span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <AnswerCard answer={turn.answer} asOf={turn.asOf} onOpenSource={openSource} onAction={(to, state) => navigate(to, { state })} />
                    {turn.answer.sources.length === 0 && i === turns.length - 1 && (
                      <div style={{ display: "flex", flexDirection: "column", gap: 6, alignItems: "flex-start", marginTop: 10 }}>
                        {ASK_QA.slice(0, 3).map(q => (
                          <button key={q.id} onClick={() => ask(q.question[lang])} style={{ border: `1px solid ${BORDER}`, background: "#fff", borderRadius: 18, padding: "6px 14px", fontSize: 13, cursor: "pointer", textAlign: "left" }}>{q.question[lang]}</button>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))}

              {busy !== null && (
                <div style={{ display: "flex", gap: 10 }} aria-live="polite">
                  <span style={{ fontSize: 11, fontWeight: 700, color: SUB, width: 22 }}>{t("ask.ai")}</span>
                  <span style={{ fontSize: 13, color: SUB }}>{steps[busy]}</span>
                </div>
              )}
              <div ref={endRef} />
            </div>
          </div>
        </div>

        <div style={{ borderTop: `1px solid ${BORDER}`, background: "#fff", padding: "12px 28px" }}>
          <div style={{ display: "flex", gap: 8 }}>
            <Input
              size="large" value={text} onChange={e => setText(e.target.value)} onPressEnter={() => ask(text)}
              placeholder={t("ask.placeholder")} aria-label={t("ask.send")} maxLength={300}
            />
            <Button size="large" type="primary" icon={<SendOutlined />} disabled={!text.trim() || busy !== null} onClick={() => ask(text)}>{t("ask.send")}</Button>
          </div>
        </div>
      </div>
      <ReviewReportDrawer entry={report} onClose={() => setReport(null)} />
    </div>
  );
}
