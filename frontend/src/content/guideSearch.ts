import type { GuideArticle, GuideGroup } from "./guide";

export type Lang = "en" | "zh";
export const toLang = (l: string): Lang => (l.startsWith("zh") ? "zh" : "en");

const stripMarkup = (s: string) => s.replace(/\*\*/g, "");

export function tokens(query: string): string[] {
  return query.toLowerCase().split(/\s+/).filter(Boolean);
}

export function matches(a: GuideArticle, lang: Lang, toks: string[]): boolean {
  if (toks.length === 0) return true;
  const hay = stripMarkup(`${a.q[lang]} ${a.a[lang].join(" ")}`).toLowerCase();
  return toks.every(t => hay.includes(t));
}

export function filterArticles(
  articles: GuideArticle[],
  opts: { lang: Lang; query: string; group: GuideGroup | "all" },
): GuideArticle[] {
  const toks = tokens(opts.query);
  return articles.filter(a => (opts.group === "all" || a.group === opts.group) && matches(a, opts.lang, toks));
}

const escapeRe = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

/** Splits text into parts, flagging the ones that match a search token. */
export function highlightParts(text: string, toks: string[]): { text: string; hit: boolean }[] {
  if (toks.length === 0 || text === "") return [{ text, hit: false }];
  const re = new RegExp(`(${toks.map(escapeRe).join("|")})`, "i");
  return text.split(re).map((p, i) => ({ text: p, hit: i % 2 === 1 })).filter(p => p.text !== "");
}

/** Splits `**bold**` markup into segments. */
export function boldParts(text: string): { text: string; bold: boolean }[] {
  return text.split(/(\*\*[^*]+\*\*)/g).filter(Boolean).map(p =>
    p.startsWith("**") ? { text: p.slice(2, -2), bold: true } : { text: p, bold: false });
}
