import { describe, expect, it } from "vitest";
import { ASK_QA, fallbackAnswer, matchQuestion, type AskCtx, type Lang } from "./askDemo";
import { getHistory, getPendingQueue } from "../state/reviewStore";

const projects = [
  { id: "demo_ship_a", label: "Demo Ship A", images: [{ stem: "a", label: "A" }, { stem: "b", label: "B" }, { stem: "c", label: "C" }], categories: [] },
  { id: "northern_star", label: "Northern Star", images: [], categories: [] },
];
const ctx = (lang: Lang = "en", over: Partial<AskCtx> = {}): AskCtx => ({ lang, now: Date.now(), history: getHistory(), queue: getPendingQueue(), projects, ...over });
const ans = (id: string, c = ctx()) => ASK_QA.find(q => q.id === id)!.answer(c);

describe("matchQuestion", () => {
  it("AS-S01 every recorded question matches itself, in both languages", () => {
    for (const q of ASK_QA) {
      expect(matchQuestion(q.question.en)?.id).toBe(q.id);
      expect(matchQuestion(q.question.zh)?.id).toBe(q.id);
    }
  });
  it("AS-S02 free text finds the right answer", () => {
    expect(matchQuestion("why is southern cross no-go")?.id).toBe("why-nogo");
    expect(matchQuestion("please draft a rectification notice for the master of Southern Cross")?.id).toBe("draft-notice");
    expect(matchQuestion("can I upload a dwg")?.id).toBe("dwg");
  });
  it("AS-S03 unrelated text matches nothing (so the honest fallback is used)", () => {
    expect(matchQuestion("what is the weather in Singapore")).toBeNull();
    expect(matchQuestion("   ")).toBeNull();
  });
});

describe("answers", () => {
  it("AS-S04 every answer has a short text, a basis and, for cited bases, sources", () => {
    for (const q of ASK_QA) for (const lang of ["en", "zh"] as Lang[]) {
      const a = q.answer(ctx(lang));
      expect(a.short.length).toBeGreaterThan(20);
      expect(a.basis.length).toBeGreaterThan(0);
      const cited = Math.max(0, ...a.basis.flatMap(b => [...b.matchAll(/\[(\d+)\]/g)].map(m => Number(m[1]))));
      expect(a.sources.length).toBeGreaterThanOrEqual(cited);
    }
  });
  it("AS-S05 missing plan: Northern Star foam question refuses and offers the upload", () => {
    const a = ans("foam-missing");
    expect(a.short).toMatch(/can't confirm/i);
    expect(a.basis.join(" ")).toMatch(/Missing/);
    expect(a.action?.label).toMatch(/Upload plan/);
  });
  it("AS-S06 once a plan exists the same question no longer claims it is missing", () => {
    const withPlan = ctx("en", { projects: [{ ...projects[1], images: [{ stem: "acc", label: "Accommodation" }] }] });
    expect(ans("foam-missing", withPlan).short).not.toMatch(/no plan sheet is uploaded/);
  });
  it("AS-S07 certification question says no", () => {
    expect(ans("certify").short).toMatch(/^\*\*No\.\*\*/);
  });
  it("AS-S08 NO-GO count is computed from history, not hard-coded", () => {
    const base = ctx();
    const noGo = base.history.filter(h => h.verdict === "NO_GO").length;
    expect(ans("nogo-count", base).short).toContain(`${noGo} of ${base.history.length}`);
    const none = ctx("en", { history: base.history.filter(h => h.verdict !== "NO_GO") });
    expect(ans("nogo-count", none).short).toMatch(/No NO-GO verdicts/);
  });
  it("AS-S09 queue answer follows the live queue, including an empty one", () => {
    expect(ans("queue-priority", ctx("en", { queue: [] })).short).toMatch(/empty/);
    expect(ans("queue-priority").short).toContain(`${getPendingQueue().length} analyses`);
  });
  it("AS-S10 the fallback admits it does not know", () => {
    expect(fallbackAnswer(ctx()).short).toMatch(/don't have a recorded answer/);
  });
});
