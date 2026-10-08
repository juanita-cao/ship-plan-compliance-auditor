import { DownOutlined, SearchOutlined, UpOutlined } from "@ant-design/icons";
import { Button, Input, type InputRef } from "antd";
import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { AppHeader } from "../components/AppHeader";
import { SidebarNav } from "../components/SidebarNav";
import { GUIDE_ARTICLES, GUIDE_GROUPS, type GuideArticle, type GuideGroup } from "../content/guide";
import { boldParts, filterArticles, highlightParts, toLang, tokens } from "../content/guideSearch";

const BORDER = "#e5e8ed";
const SUB    = "#6b7280";
const TXT    = "#374151";
const SUGGESTED = ["statuses", "verdicts", "submit-review"];

function Highlighted({ text, toks }: { text: string; toks: string[] }) {
  return (
    <>
      {highlightParts(text, toks).map((p, i) =>
        p.hit ? <mark key={i} style={{ background: "#fff3b0", color: "inherit", padding: "0 1px", borderRadius: 2 }}>{p.text}</mark> : <Fragment key={i}>{p.text}</Fragment>)}
    </>
  );
}

function Chip({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button onClick={onClick} style={{
      border: `1px solid ${active ? "#93c5fd" : BORDER}`, background: active ? "#eff6ff" : "#fff",
      color: active ? "#2f54eb" : TXT, fontWeight: active ? 600 : 400,
      borderRadius: 14, padding: "3px 11px", fontSize: 12, cursor: "pointer",
    }}>{label}</button>
  );
}

function WorkflowStrip() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const lastProject = (() => { try { return localStorage.getItem("pvcb_last_project") ?? "demo_ship_a"; } catch { return "demo_ship_a"; } })();
  const steps: { label: string; go: () => void }[] = [
    { label: t("help.step1"), go: () => navigate("/app") },
    { label: t("help.step2"), go: () => navigate("/app/vessel", { state: { projectId: lastProject } }) },
    { label: t("help.step3"), go: () => navigate("/app/vessel", { state: { projectId: lastProject } }) },
    { label: t("help.step4"), go: () => navigate("/app/queue") },
    { label: t("help.step5"), go: () => navigate("/app/history") },
  ];
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }} aria-label={t("help.how")}>
      <span style={{ fontSize: 11, fontWeight: 600, color: SUB, letterSpacing: ".06em", marginRight: 4 }}>{t("help.how").toUpperCase()}</span>
      {steps.map((s, i) => (
        <Fragment key={i}>
          {i > 0 && <span style={{ color: "#c0c6cf" }}>→</span>}
          <button onClick={s.go} style={{
            border: `1px solid ${BORDER}`, background: "#fff", borderRadius: 14, padding: "3px 11px",
            fontSize: 12, color: TXT, cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 6,
          }}>
            <span style={{ width: 16, height: 16, borderRadius: "50%", background: "#0a1e3d", color: "#fff", fontSize: 10, fontWeight: 700, display: "inline-flex", alignItems: "center", justifyContent: "center" }}>{i + 1}</span>
            {s.label}
          </button>
        </Fragment>
      ))}
    </div>
  );
}

function ArticleRow({ a, open, toks, lang, onToggle }: {
  a: GuideArticle; open: boolean; toks: string[]; lang: "en" | "zh"; onToggle: () => void;
}) {
  const { t } = useTranslation();
  return (
    <div id={a.id} style={{ borderBottom: `1px solid ${BORDER}` }}>
      <button
        type="button" aria-expanded={open} aria-controls={`${a.id}-body`} onClick={onToggle}
        style={{
          width: "100%", textAlign: "left", border: 0, cursor: "pointer",
          padding: "11px var(--gutter)", display: "flex", alignItems: "center", justifyContent: "space-between",
          color: "#111827", fontSize: 13, background: open ? "#f8faff" : "#fff",
        }}
        onMouseEnter={e => { if (!open) e.currentTarget.style.background = "#fafafa"; }}
        onMouseLeave={e => { if (!open) e.currentTarget.style.background = "#fff"; }}
      >
        <span><Highlighted text={a.q[lang]} toks={toks} /></span>
        {open ? <UpOutlined style={{ fontSize: 10, color: SUB }} /> : <DownOutlined style={{ fontSize: 10, color: SUB }} />}
      </button>
      {open && (
        <div id={`${a.id}-body`} style={{ padding: "4px var(--gutter) 16px", background: "#f8faff", borderTop: `1px solid ${BORDER}` }}>
          <div style={{ maxWidth: 760, fontSize: 12.5, lineHeight: 1.7, color: TXT, paddingTop: 10 }}>
            {a.a[lang].map((para, i) => (
              <p key={i} style={{ margin: "0 0 6px" }}>
                {boldParts(para).map((seg, j) => seg.bold
                  ? <strong key={j} style={{ color: "#111827" }}><Highlighted text={seg.text} toks={toks} /></strong>
                  : <Highlighted key={j} text={seg.text} toks={toks} />)}
              </p>
            ))}
            {a.links && (
              <div style={{ marginTop: 8, display: "flex", gap: 14, alignItems: "center", flexWrap: "wrap" }}>
                <span style={{ fontSize: 11, color: SUB, fontWeight: 600 }}>{t("help.related")}</span>
                {a.links.map(l => <Link key={l.to} to={l.to} style={{ fontSize: 12.5 }}>{l.label[lang]} →</Link>)}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export function GuidePage() {
  const { t, i18n } = useTranslation();
  const lang = toLang(i18n.language);
  const loc = useLocation();
  const navigate = useNavigate();
  const searchRef = useRef<InputRef>(null);

  const [query, setQuery] = useState("");
  const [group, setGroup] = useState<GuideGroup | "all">("all");
  const [open, setOpen] = useState<string | null>(null);

  const toks = useMemo(() => tokens(query), [query]);
  const shown = useMemo(() => filterArticles(GUIDE_ARTICLES, { lang, query, group }), [lang, query, group]);

  // Deep link: /guide#article-id expands and scrolls to the article
  useEffect(() => {
    const id = loc.hash.replace(/^#/, "");
    if (!id || !GUIDE_ARTICLES.some(a => a.id === id)) return;
    setQuery(""); setGroup("all"); setOpen(id);
    window.setTimeout(() => document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "center" }), 80);
  }, [loc.hash]);

  // "/" focuses the search box
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement).tagName;
      if (e.key === "/" && tag !== "INPUT" && tag !== "TEXTAREA") { e.preventDefault(); searchRef.current?.focus(); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const toggle = (id: string) => {
    const next = open === id ? null : id;
    setOpen(next);
    navigate({ hash: next ? `#${next}` : "" }, { replace: true });
  };

  const byGroup = GUIDE_GROUPS
    .map(g => ({ g, items: shown.filter(a => a.group === g.id) }))
    .filter(x => x.items.length > 0);

  return (
    <div style={{ display: "flex", flex: 1, minHeight: "100%" }}>
      <SidebarNav />

      <div style={{ flex: 1, minWidth: 0, background: "#f0f2f5", display: "flex", flexDirection: "column" }}>
        <AppHeader crumbs={[{ label: t("nav.helpCenter") }]} />

        <div style={{ padding: "24px var(--gutter) 14px" }}>
          <h1 style={{ fontSize: 20, fontWeight: 700, color: "#111827", margin: "0 0 16px" }}>{t("help.title")}</h1>
          <Input
            ref={searchRef} allowClear value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => { if (e.key === "Escape") setQuery(""); }}
            prefix={<SearchOutlined style={{ color: SUB }} />}
            placeholder={t("help.searchPh")}
            suffix={query ? null : <span style={{ fontSize: 11, color: "#9ca3af" }}>{t("help.searchHint")}</span>}
            aria-label={t("help.searchPh")}
          />
          <div style={{ marginTop: 14 }}><WorkflowStrip /></div>
          <div style={{ marginTop: 12, display: "flex", gap: 6, flexWrap: "wrap" }}>
            <Chip label={t("help.all")} active={group === "all"} onClick={() => setGroup("all")} />
            {GUIDE_GROUPS.map(g => <Chip key={g.id} label={g.label[lang]} active={group === g.id} onClick={() => setGroup(g.id)} />)}
          </div>
        </div>

        <div style={{ background: "#fff", borderTop: `1px solid ${BORDER}`, flex: 1 }}>
          {byGroup.length === 0 ? (
            <div style={{ padding: "48px var(--gutter)", textAlign: "center" }}>
              <div style={{ fontSize: 15, fontWeight: 600, color: TXT }}>{t("help.emptyTitle", { q: query })}</div>
              <div style={{ fontSize: 13, color: SUB, marginTop: 4 }}>{t("help.emptyBody")}</div>
              <Button style={{ marginTop: 14 }} onClick={() => { setQuery(""); setGroup("all"); }}>{t("help.clear")}</Button>
              <div style={{ marginTop: 22, fontSize: 11, fontWeight: 600, color: SUB, letterSpacing: ".06em" }}>{t("help.suggested").toUpperCase()}</div>
              <div style={{ marginTop: 8, display: "flex", gap: 14, justifyContent: "center", flexWrap: "wrap" }}>
                {GUIDE_ARTICLES.filter(a => SUGGESTED.includes(a.id)).map(a => (
                  <a key={a.id} href={`#${a.id}`} onClick={e => { e.preventDefault(); setQuery(""); setGroup("all"); setOpen(a.id); navigate({ hash: `#${a.id}` }, { replace: true }); }} style={{ fontSize: 13 }}>{a.q[lang]}</a>
                ))}
              </div>
            </div>
          ) : byGroup.map(({ g, items }) => (
            <section key={g.id}>
              <div style={{ padding: "9px var(--gutter)", background: "#f8f9fb", borderBottom: `1px solid ${BORDER}`, fontSize: 11, fontWeight: 600, color: SUB, letterSpacing: ".06em", textTransform: "uppercase" }}>
                {g.label[lang]}
              </div>
              {items.map(a => (
                <ArticleRow key={a.id} a={a} open={open === a.id} toks={toks} lang={lang} onToggle={() => toggle(a.id)} />
              ))}
            </section>
          ))}

          <div style={{ padding: "8px var(--gutter)", fontSize: 11, color: SUB, display: "flex", justifyContent: "space-between", borderTop: byGroup.length ? "none" : `1px solid ${BORDER}` }}>
            <span>{t("help.count", { shown: shown.length, total: GUIDE_ARTICLES.length })}</span>
            <span>{t("help.demo")}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
