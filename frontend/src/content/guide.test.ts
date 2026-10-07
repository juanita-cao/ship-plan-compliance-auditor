import { describe, expect, it } from "vitest";
import { GUIDE_ARTICLES, GUIDE_GROUPS } from "./guide";
import { filterArticles, highlightParts, tokens } from "./guideSearch";

const ROUTES = ["/app", "/app/vessel", "/app/queue", "/app/history", "/guide"];

describe("guide content", () => {
  it("GD-S10 every article is complete in both languages with unique ids", () => {
    const ids = new Set<string>();
    for (const a of GUIDE_ARTICLES) {
      expect(ids.has(a.id)).toBe(false);
      ids.add(a.id);
      expect(GUIDE_GROUPS.some(g => g.id === a.group)).toBe(true);
      for (const l of ["en", "zh"] as const) {
        expect(a.q[l].trim().length).toBeGreaterThan(0);
        expect(a.a[l].length).toBeGreaterThan(0);
        a.a[l].forEach(p => expect(p.trim().length).toBeGreaterThan(0));
      }
      expect(a.a.en.length).toBe(a.a.zh.length);
    }
  });
  it("GD-S09 every link points to an existing route", () => {
    for (const a of GUIDE_ARTICLES) for (const l of a.links ?? []) expect(ROUTES).toContain(l.to);
  });
  it("every group has at least one article", () => {
    for (const g of GUIDE_GROUPS) expect(GUIDE_ARTICLES.some(a => a.group === g.id)).toBe(true);
  });
});

describe("guide search", () => {
  it("GD-S01 filters live on question and answer text", () => {
    const r = filterArticles(GUIDE_ARTICLES, { lang: "en", query: "verdict", group: "all" });
    expect(r.length).toBeGreaterThan(0);
    expect(r.some(a => a.id === "verdicts")).toBe(true);
  });
  it("GD-S02 multiple terms are ANDed", () => {
    const both = filterArticles(GUIDE_ARTICLES, { lang: "en", query: "review queue", group: "all" });
    const one = filterArticles(GUIDE_ARTICLES, { lang: "en", query: "queue", group: "all" });
    expect(both.length).toBeLessThanOrEqual(one.length);
    expect(both.length).toBeGreaterThan(0);
  });
  it("GD-S03 no match returns an empty list", () => {
    expect(filterArticles(GUIDE_ARTICLES, { lang: "en", query: "zzzzqq", group: "all" })).toEqual([]);
  });
  it("GD-S04 group filter combines with the query", () => {
    const r = filterArticles(GUIDE_ARTICLES, { lang: "en", query: "review", group: "rules" });
    expect(r.every(a => a.group === "rules")).toBe(true);
  });
  it("GD-S07 searches in the current language", () => {
    expect(filterArticles(GUIDE_ARTICLES, { lang: "zh", query: "验船师", group: "all" }).length).toBeGreaterThan(0);
    expect(filterArticles(GUIDE_ARTICLES, { lang: "en", query: "验船师", group: "all" })).toEqual([]);
  });
  it("highlights matches case-insensitively", () => {
    const parts = highlightParts("Review the Queue", tokens("queue"));
    expect(parts.filter(p => p.hit).map(p => p.text)).toEqual(["Queue"]);
  });
  it("special characters in the query do not break highlighting", () => {
    expect(() => highlightParts("CO₂ (5kg)", tokens("(5kg"))).not.toThrow();
  });
});
