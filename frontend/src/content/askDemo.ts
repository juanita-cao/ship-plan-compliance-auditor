// Recorded answers for the mock Ask page (ADR-F35, content in docs/mock_chat_qa.md).
// Nothing is generated live. Figures that depend on workspace data are computed from the stores.
import { VESSEL_FLEET } from "../config";
import { vesselName } from "../domain/vessels";
import { vesselStatus } from "../domain/vesselStatus";
import { reportNo } from "../state/reviewStore";
import type { AnalyzedEntry, HistoryEntry } from "../state/reviewStore";
import type { ProjectInfo } from "../api/client";

export type Lang = "en" | "zh";

export interface AskSource { kind: "report" | "vessel" | "queue" | "guide" | "rule"; id: string; label: string }
export interface AskAnswer {
  /** Always visible. `**bold**` and `[n]` are the only markup. */
  short: string;
  /** Shown under "Show basis"; `[n]` cites `sources`. */
  basis: string[];
  sources: AskSource[];
  draft?: string;
  action?: { label: string; to: string; state?: unknown };
  /** A conclusion that needs a person to confirm. */
  proposal?: boolean;
}
export interface AskCtx { lang: Lang; now: number; history: HistoryEntry[]; queue: AnalyzedEntry[]; projects: ProjectInfo[] }
export interface AskQA {
  id: string;
  question: Record<Lang, string>;
  /** Lower-case; matched as substrings of the typed question. */
  keywords: string[];
  answer: (c: AskCtx) => AskAnswer;
}

const VERDICT = (v: string) => (v === "NO_GO" ? "NO-GO" : v);
const DAY = 86_400_000;
const daysAgo = (iso: string, now: number) => Math.max(0, Math.round((now - new Date(iso).getTime()) / DAY));
const ago = (iso: string, c: AskCtx) => { const d = daysAgo(iso, c.now); return c.lang === "zh" ? `${d} 天前` : `${d} days ago`; };
const T = (c: AskCtx, en: string, zh: string) => (c.lang === "zh" ? zh : en);

const latestFor = (c: AskCtx, key: string) =>
  c.history.filter(h => h.projectId === key).sort((a, b) => b.submittedAt.localeCompare(a.submittedAt))[0];
const reportSrc = (e: HistoryEntry): AskSource => ({ kind: "report", id: e.id, label: `${reportNo(e)} · ${vesselName(e.projectId, e.projectLabel)} · ${e.imageLabel} · ${VERDICT(e.verdict)}` });
const guide = (c: AskCtx, id: string, en: string, zh: string): AskSource => ({ kind: "guide", id, label: `Guide · ${T(c, en, zh)}` });
const rule = (id: string, en: string): AskSource => ({ kind: "rule", id, label: `Rule ${id} · ${en}` });
const names = (keys: string[]) => keys.map(k => vesselName(k)).join(", ");
const hasPlan = (c: AskCtx, id: string) => (c.projects.find(p => p.id === id)?.images.length ?? 0) > 0;

// ── The 10 questions ──────────────────────────────────────────────────────────

const Q1: AskQA = {
  id: "attention",
  question: { en: "Which vessels need my attention this week?", zh: "本周哪些船需要我关注？" },
  keywords: ["attention", "this week", "need my", "which vessels", "关注", "本周", "哪些船"],
  answer: c => {
    const by = (s: string) => VESSEL_FLEET.filter(v => vesselStatus(v) === s);
    const ar = by("action_required"), pc = by("pending_confirm"), tr = by("to_review"), sc = by("scheduled");
    const qn = c.queue.length;
    const sources: AskSource[] = [];
    const lines: string[] = [];
    for (const v of ar) { const e = latestFor(c, v.historyKey); if (e) { sources.push(reportSrc(e)); lines.push(T(c, `${v.name}: last signed review ${VERDICT(e.verdict)}, ${ago(e.submittedAt, c)} [${sources.length}].`, `${v.name}：最近一次签署的评审为 ${VERDICT(e.verdict)}，${ago(e.submittedAt, c)} [${sources.length}]。`)); } }
    for (const v of pc) { const e = latestFor(c, v.historyKey); if (e) { sources.push(reportSrc(e)); lines.push(T(c, `${v.name}: ${VERDICT(e.verdict)}, ${ago(e.submittedAt, c)}, needs re-verification [${sources.length}].`, `${v.name}：${VERDICT(e.verdict)}，${ago(e.submittedAt, c)}，需要复核 [${sources.length}]。`)); } }
    sources.push({ kind: "queue", id: "queue", label: T(c, `Review Queue (${qn} items)`, `待审队列（${qn} 项）`) });
    lines.push(T(c, `Queue: ${qn} unsigned ${qn === 1 ? "analysis" : "analyses"}, so not in the compliance history yet [${sources.length}].`, `队列：${qn} 项未签署的分析，尚未计入合规历史 [${sources.length}]。`));
    if (sc.length) lines.push(T(c, `Scheduled, no action needed now: ${names(sc.map(v => v.historyKey))}.`, `已排期，暂无需处理：${names(sc.map(v => v.historyKey))}。`));
    lines.push(T(c, "Not covered: surveys due by calendar date — the demo has no survey-due dates on file.", "未覆盖：按日历到期的检验——演示数据中没有检验到期日。"));
    const attn = ar.length + pc.length + tr.length;
    const queueNames = c.queue.map(q => `${vesselName(q.projectId, q.projectLabel)} · ${q.imageLabel}`).join(T(c, " and ", "、"));
    const parts = [
      ar.length ? T(c, `${names(ar.map(v => v.historyKey))} is Action Required`, `${names(ar.map(v => v.historyKey))} 需整改`) : "",
      pc.length ? T(c, `${names(pc.map(v => v.historyKey))} is Pending Confirm`, `${names(pc.map(v => v.historyKey))} 待会签`) : "",
      tr.length ? T(c, `${names(tr.map(v => v.historyKey))} ${tr.length === 1 ? "has" : "have"} analyses to review`, `${names(tr.map(v => v.historyKey))} 有待评审的分析`) : "",
    ].filter(Boolean).join(T(c, ". ", "；"));
    return {
      short: T(c,
        `**${attn} ${attn === 1 ? "vessel needs" : "vessels need"} action and ${qn} ${qn === 1 ? "analysis is" : "analyses are"} waiting for review.** ${parts}.${qn ? ` In the Review Queue: ${queueNames}.` : ""}`,
        `**${attn} 艘船需要处理，${qn} 项分析等待评审。** ${parts}。${qn ? `待审队列：${queueNames}。` : ""}`),
      basis: lines, sources,
    };
  },
};

const Q2: AskQA = {
  id: "why-nogo",
  question: { en: "Why is Southern Cross NO-GO?", zh: "Southern Cross 为什么是 NO-GO？" },
  keywords: ["southern cross", "why", "no-go", "nogo", "为什么", "原因"],
  answer: c => {
    const e = latestFor(c, "southern_cross");
    if (!e) return { short: T(c, "There is no signed review for Southern Cross in this workspace, so I can't explain a verdict.", "本工作区没有 Southern Cross 的已签署评审，无法解释结论。"), basis: [], sources: [] };
    const src = reportSrc(e);
    const fleet: AskSource = { kind: "vessel", id: "southern_cross", label: T(c, "Fleet record · Southern Cross", "船舶档案 · Southern Cross") };
    if (e.verdict !== "NO_GO") {
      return {
        short: T(c, `**Southern Cross is not NO-GO on the latest record.** The latest signed review (${e.imageLabel}) is ${VERDICT(e.verdict)}.`, `**按最新记录，Southern Cross 并非 NO-GO。** 最近签署的评审（${e.imageLabel}）结论为 ${VERDICT(e.verdict)}。`),
        basis: [T(c, `${reportNo(e)}, signed by ${e.reviewer}, ${ago(e.submittedAt, c)} [1].`, `${reportNo(e)}，由 ${e.reviewer} 签署，${ago(e.submittedAt, c)} [1]。`)],
        sources: [src, fleet],
      };
    }
    return {
      short: T(c,
        `**Suggested conclusion:** the NO-GO comes from two findings in the ${e.imageLabel} review: the **CO₂ release point is obstructed** and **one portable extinguisher has an expired tag (2024)**. Signed by ${e.reviewer}; ${e.confirmedCount} of ${e.instanceCount} detections confirmed, ${e.flaggedCount} flagged.`,
        `**建议结论：** ${e.imageLabel}评审出现 NO-GO，原因是两项发现：**CO₂ 释放点被遮挡**，以及**一具便携式灭火器标签过期（2024）**。由 ${e.reviewer} 签署；${e.instanceCount} 项检出中 ${e.confirmedCount} 项确认，${e.flaggedCount} 项标记。`),
      proposal: true,
      basis: [
        T(c, `The surveyor's note records both findings and the ${e.confirmedCount} / ${e.flaggedCount} split between confirmed and flagged detections [1].`, `验船师的备注记录了这两项发现，以及确认 / 标记 ${e.confirmedCount} / ${e.flaggedCount} 的划分 [1]。`),
        T(c, "The two flagged detections match the two findings; the report does not list which symbol each one is.", "两个被标记的检出与这两项发现对应；报告没有列出各自是哪个符号。"),
        T(c, "**Uncertainty:** the records contain no follow-up. I cannot tell whether the obstruction was cleared or the extinguisher replaced, so the NO-GO may be out of date.", "**不确定性：** 记录里没有后续跟进。我无法判断遮挡是否已清除、灭火器是否已更换，所以这个 NO-GO 可能已过时。"),
        T(c, "**Missing:** a re-inspection report, the rectification date, and the plan sheet for Southern Cross (no plan is uploaded, so I cannot re-count anything).", "**缺失：** 复检报告、整改日期，以及 Southern Cross 的图纸（未上传图纸，我无法重新计数）。"),
        T(c, "Next step I'd suggest: a re-inspection after the master confirms rectification.", "我建议的下一步：待船长确认整改后安排复检。"),
      ],
      sources: [src, fleet],
    };
  },
};

const Q3: AskQA = {
  id: "foam-missing",
  question: { en: "Does Northern Star's accommodation deck meet the foam extinguisher requirement?", zh: "Northern Star 的起居甲板满足泡沫灭火器要求吗？" },
  keywords: ["northern star", "foam", "accommodation", "泡沫", "起居"],
  answer: c => {
    const e = latestFor(c, "northern_star");
    const plan = hasPlan(c, "northern_star");
    const sources: AskSource[] = [rule("R03", T(c, "accommodation foam (illustrative)", "起居处所泡沫（示例）"))];
    if (e) sources.push(reportSrc(e));
    return {
      short: plan
        ? T(c, "**A plan is on file for Northern Star, but I have no analysis of the accommodation deck yet.** The applicable rule is **R03** (≥ 1 foam extinguisher in accommodation spaces). Run the analysis and R03 is evaluated on the real count.", "**Northern Star 已有图纸，但起居甲板还没有分析结果。** 适用规则是 **R03**（起居处所至少 1 具泡沫灭火器）。运行分析后，R03 将按真实数量判定。")
        : T(c, "**I can't confirm that from the records.** The rule that applies is **R03** (≥ 1 foam extinguisher in accommodation spaces), but **no plan sheet is uploaded for Northern Star**, and the signed review stores only totals, not a count per extinguisher type.", "**仅凭现有记录，我无法确认。** 适用的规则是 **R03**（起居处所至少 1 具泡沫灭火器），但 **Northern Star 没有上传图纸**，而已签署的评审只存了总数，没有按灭火器类型分别计数。"),
      basis: [
        T(c, "R03 applies to accommodation spaces and is a warning-level rule: no foam unit gives CONDITIONAL, not NO-GO [1].", "R03 适用于起居处所，属于“警告”级规则：没有泡沫灭火器会得到 CONDITIONAL，而不是 NO-GO [1]。"),
        ...(e ? [T(c, `The ${e.imageLabel} review shows ${e.instanceCount} detections, ${e.confirmedCount} confirmed, ${e.flaggedCount} flagged, ${VERDICT(e.verdict)}. The note is about **smoke detector spacing**, not extinguishers [2]. So the verdict does not tell us whether foam is present.`, `${e.imageLabel}评审显示 ${e.instanceCount} 项检出，${e.confirmedCount} 项确认，${e.flaggedCount} 项标记，结论 ${VERDICT(e.verdict)}。备注说的是**烟感探测器间距**，不是灭火器 [2]。所以这个结论无法说明有没有泡沫灭火器。`)] : []),
        T(c, "I will **not** infer foam presence from the verdict: a CONDITIONAL could come from R03 or from something else.", "我**不会**从结论反推有没有泡沫灭火器：CONDITIONAL 可能来自 R03，也可能来自别的原因。"),
        T(c, `**Missing:** ${plan ? "the analysis of the accommodation deck" : "the Northern Star plan sheet"}; a per-category detection count for that review.`, `**缺失：** ${plan ? "起居甲板的分析结果" : "Northern Star 的图纸"}；该评审按类别的检出数量。`),
        plan ? T(c, "**To get a real answer:** open Northern Star, select the accommodation deck and run the analysis.", "**要得到真实答案：** 打开 Northern Star，选择起居甲板并运行分析。")
             : T(c, "**To get a real answer:** upload the plan (Vessel → Northern Star → Upload plan), run the analysis, and R03 is evaluated on the actual count.", "**要得到真实答案：** 上传图纸（船舶 → Northern Star → 上传图纸），运行分析，R03 就会按实际数量判定。"),
        T(c, "Note: the R03 wording in this demo is an illustrative rule, not a quotation of the FSS Code.", "注意：本演示中的 R03 是示例规则，不是 FSS 规则的原文。"),
      ],
      sources,
      action: { label: plan ? T(c, "Open Northern Star →", "打开 Northern Star →") : T(c, "Upload plan for Northern Star →", "为 Northern Star 上传图纸 →"), to: "/app/vessel", state: { projectId: "northern_star" } },
    };
  },
};

const Q4: AskQA = {
  id: "spare-co2",
  question: { en: "What is the spare CO₂ rule (R05) and when does it apply?", zh: "备用 CO₂ 规则（R05）是什么，什么时候适用？" },
  keywords: ["r05", "spare", "co2", "co₂", "备用", "spare co"],
  answer: c => ({
    short: T(c, "**R05 requires at least 1 spare CO₂ extinguisher when the plan shows 2 or more CO₂ extinguishers;** with 0 or 1 CO₂ unit it is not applicable. A missing spare gives CONDITIONAL (a warning, not a failure).", "**当图纸上有 2 具或以上 CO₂ 灭火器时，R05 要求至少 1 具备用 CO₂；** 只有 0 或 1 具时不适用。缺少备用只会得到 CONDITIONAL（警告，不是不通过）。"),
    basis: [
      T(c, 'Demo rule set: R05, article reference "FSS Code Ch.6/2.2", required ≥ 1 spare when CO₂ ≥ 2 [1].', "演示规则集：R05，条款引用“FSS Code Ch.6/2.2”，CO₂ ≥ 2 时要求 ≥ 1 具备用 [1]。"),
      T(c, "Example: 3 CO₂ units and 0 spare → CONDITIONAL; 3 CO₂ and 1 spare → GO; 1 CO₂ and 0 spare → N/A.", "例：3 具 CO₂、0 具备用 → CONDITIONAL；3 具 CO₂、1 具备用 → GO；1 具 CO₂、0 具备用 → 不适用。"),
      T(c, "**This is a demo rule.** The article numbers are placeholders, not a legal citation, and every one of R01–R05 is marked as illustrative.", "**这是演示规则。** 条款编号只是占位，不是法律引用，R01–R05 全部标注为示例。"),
      T(c, "**General knowledge, not a company record:** the real requirement works differently. Under SOLAS II-2 and the FSS Code, spare charges are provided for portable extinguishers that can be recharged on board — roughly 100 % of the first 10 and 50 % of the rest, capped at 60 in total. Check the current consolidated edition before relying on this; I have no live regulation source connected.", "**通用知识，不是公司记录：** 真实要求并不是这样。按 SOLAS II-2 和 FSS 规则，可在船上重新充装的便携式灭火器需配备备用药剂——大致为前 10 具的 100%、其余的 50%，总数上限 60。使用前请对照现行合订本核实；我没有连接实时法规来源。"),
      T(c, "**Missing:** the class society's own interpretation for a specific vessel.", "**缺失：** 船级社对具体船舶的解释。"),
    ],
    sources: [rule("R05", T(c, "spare CO₂ (illustrative)", "备用 CO₂（示例）")), guide(c, "regulations", "Which regulations does it check?", "检查依据哪些法规？")],
  }),
};

const Q5: AskQA = {
  id: "draft-notice",
  question: { en: "Draft a rectification notice to the master of Southern Cross", zh: "给 Southern Cross 的船长起草一份整改通知" },
  keywords: ["draft", "notice", "master", "rectification", "southern cross", "起草", "整改", "船长", "通知"],
  answer: c => {
    const e = latestFor(c, "southern_cross");
    const ref = e ? reportNo(e) : "[report no.]";
    const deck = e?.imageLabel ?? "[deck]";
    const known = e?.id === "seed-h2";
    const draft = c.lang === "zh"
      ? `主题：Southern Cross（IMO 9 512 087）——${deck}消防安全发现，报告 ${ref}\n\n尊敬的 [船长姓名] 船长：\n\n根据对${deck}消防安全图纸的检验，以下发现仍未关闭：\n${known ? "1. CO₂ 释放点被遮挡。请清理通道，并确认释放点畅通且标识清晰。\n2. 一具便携式灭火器的检验标签已过期（2024）。请送检或更换，并告知该灭火器的位置和新的标签日期。" : `1. ${e?.note ?? "[发现事项]"}`}\n\n请在 [商定日期] 前提供相关照片证据，并在完成后申请复检。\n\n此致\n[验船师姓名]，太平洋船级社`
      : `Subject: Southern Cross (IMO 9 512 087) — ${deck} fire-safety findings, report ${ref}\n\nDear Captain [Master's name],\n\nFollowing the fire-safety plan survey of the ${deck}, the following findings are open:\n${known ? "1. The CO₂ release point is obstructed. Please clear access and confirm the release point is unobstructed and clearly marked.\n2. One portable extinguisher carries an expired service tag (2024). Please service or replace it and confirm the unit's location and new tag date." : `1. ${e?.note ?? "[finding]"}`}\n\nPlease send photographic evidence by [date to be agreed] and request a re-inspection once complete.\n\nBest regards,\n[Surveyor name], Pacific Vessel Classification Bureau`;
    return {
      short: T(c, `Draft prepared for **Southern Cross**, based on the findings in the last ${deck} review. Check the facts and fill the bracketed fields before use.`, `已根据最近一次${deck}评审的发现，为 **Southern Cross** 起草通知。使用前请核对事实并填写方括号内的内容。`),
      draft,
      basis: [
        T(c, "Both findings and the report number come from the signed review [1].", "两项发现和报告编号均来自已签署的评审 [1]。"),
        T(c, "**Left blank on purpose:** master's name, deadline, extinguisher location / ID — none are in the records. The deadline is a commercial / class decision for the surveyor.", "**刻意留空：** 船长姓名、期限、灭火器位置 / 编号——记录里都没有。期限应由验船师根据商务 / 船级要求决定。"),
        T(c, "I did not add a regulatory citation: the report does not state which requirement each finding breaches.", "我没有添加法规引用：报告并未说明每项发现违反了哪一条要求。"),
      ],
      sources: e ? [reportSrc(e), { kind: "vessel", id: "southern_cross", label: T(c, "Fleet record · Southern Cross", "船舶档案 · Southern Cross") }] : [],
    };
  },
};

const Q6: AskQA = {
  id: "conditional-vs-nogo",
  question: { en: "How is CONDITIONAL different from NO-GO, and what turns Northern Star into GO?", zh: "CONDITIONAL 和 NO-GO 有什么区别？Northern Star 怎样才能变成 GO？" },
  keywords: ["conditional", "difference", "different", "turns", "区别", "变成 go", "怎样才能"],
  answer: c => {
    const e = latestFor(c, "northern_star");
    return {
      short: T(c, "**NO-GO = a mandatory check failed; CONDITIONAL = no failure but a warning to resolve; GO = all checks pass.** Northern Star is CONDITIONAL because of marginal smoke-detector spacing in the crew corridor, so it can reach GO once that is re-verified and signed.", "**NO-GO = 有必检项不通过；CONDITIONAL = 没有不通过项，但有需要解决的警告；GO = 全部通过。** Northern Star 是 CONDITIONAL，原因是船员走廊的烟感探测器间距偏临界，复核并签署后即可达到 GO。"),
      proposal: true,
      basis: [
        T(c, "In the rule set, R01 / R02 / R04 are fail rules (→ NO-GO); R03 and R05 are warning rules (→ CONDITIONAL) [1].", "规则集中，R01 / R02 / R04 是“不通过”级规则（→ NO-GO）；R03 和 R05 是“警告”级规则（→ CONDITIONAL）[1]。"),
        T(c, "The overall verdict is the worst of the individual checks.", "整体结论取各项检查中最差的一项。"),
        T(c, `Northern Star's note: "${e?.note ?? "—"}" [2]. That is a surveyor judgement, not one of R01–R05.`, `Northern Star 的备注：“${e?.note ?? "—"}”[2]。这是验船师的判断，不属于 R01–R05。`),
        T(c, "**Missing:** the date of the next survey; the detector spacing numbers; who owns the re-verification. I can't say when GO would be reached.", "**缺失：** 下次检验日期；探测器间距的具体数值；谁负责复核。我无法说明何时能达到 GO。"),
        T(c, "What a CONDITIONAL means for a real flag state or class record is outside these records.", "CONDITIONAL 对真实旗国或船级记录意味着什么，超出了这些记录的范围。"),
      ],
      sources: [guide(c, "verdicts", "What do GO, CONDITIONAL and NO-GO mean?", "GO、CONDITIONAL、NO-GO 分别是什么意思？"), ...(e ? [reportSrc(e)] : [])],
    };
  },
};

const Q7: AskQA = {
  id: "queue-priority",
  question: { en: "What is in my review queue and what should I do first?", zh: "我的待审队列里有什么？应该先做哪个？" },
  keywords: ["queue", "first", "priority", "prioritise", "队列", "先做", "优先"],
  answer: c => {
    const q = [...c.queue].sort((a, b) => a.analyzedAt.localeCompare(b.analyzedAt));
    const hoursAgo = (iso: string) => Math.max(1, Math.round((c.now - new Date(iso).getTime()) / 3_600_000));
    const item = (e: AnalyzedEntry) => `${vesselName(e.projectId, e.projectLabel)} · ${e.imageLabel} (${T(c, `analysed ${hoursAgo(e.analyzedAt)} h ago`, `${hoursAgo(e.analyzedAt)} 小时前分析`)})`;
    const queueSrc: AskSource = { kind: "queue", id: "queue", label: T(c, `Review Queue (${q.length} items)`, `待审队列（${q.length} 项）`) };
    if (q.length === 0) {
      return { short: T(c, "**Your review queue is empty.** Nothing is waiting for a signature.", "**你的待审队列是空的。** 没有等待签署的项目。"), basis: [T(c, "Every analysis so far has a signed review [1].", "目前所有分析都已有签署的评审 [1]。")], sources: [queueSrc] };
    }
    const hasVerdicts = q.every(e => e.aiVerdict);
    const rank = (v?: string) => (v === "NO_GO" ? 0 : v === "CONDITIONAL" ? 1 : 2);
    const ordered = hasVerdicts ? [...q].sort((a, b) => rank(a.aiVerdict) - rank(b.aiVerdict) || a.analyzedAt.localeCompare(b.analyzedAt)) : q;
    return {
      short: T(c,
        `**${q.length} ${q.length === 1 ? "analysis is" : "analyses are"} waiting:** ${q.map(item).join("; ")}. **Suggested order: ${ordered[0] ? `${vesselName(ordered[0].projectId, ordered[0].projectLabel)} · ${ordered[0].imageLabel} first` : ""}${hasVerdicts ? ", because its AI verdict is the most severe." : ", because it has waited longest. I can't rank them by risk."}**`,
        `**${q.length} 项分析等待评审：** ${q.map(item).join("；")}。**建议顺序：先做 ${ordered[0] ? `${vesselName(ordered[0].projectId, ordered[0].projectLabel)} · ${ordered[0].imageLabel}` : ""}${hasVerdicts ? "，因为它的 AI 结论最严重。" : "，因为它等得最久。我无法按风险排序。"}**`),
      proposal: true,
      basis: [
        T(c, "All are unsigned AI analyses, so none counts toward compliance history until a surveyor reviews it [1].", "它们都是未签署的 AI 分析，验船师评审之前不会计入合规历史 [1]。"),
        hasVerdicts ? T(c, "Order: most severe AI verdict first, then oldest.", "排序：AI 结论越严重越靠前，其次是等待越久越靠前。")
          : T(c, "The queue record stores no AI verdict or flagged-item count, so I have no basis to say which deck is more likely to be NO-GO. Oldest-first is a neutral default, not a risk call.", "队列记录没有保存 AI 结论或被标记项数量，所以我无法判断哪块甲板更可能是 NO-GO。“先进先出”只是中性的默认顺序，不是风险判断。"),
        ...(hasVerdicts ? [] : [T(c, "If you want a risk-based order, open each analysis and look at its verdict first; I can then re-rank.", "如果想按风险排序，请先打开每项分析看它的结论，之后我可以重新排序。"), T(c, "**Missing:** AI verdict and flagged count per queued item.", "**缺失：** 每个队列项的 AI 结论和标记数量。")]),
        T(c, "Each review: accept / flag detections → Submit → Sign & Submit.", "每次评审：接受 / 标记检出 → 提交 → 签署并提交。"),
      ],
      sources: [queueSrc, guide(c, "submit-review", "How do I complete a review?", "如何完成一次评审？")],
      action: { label: T(c, "Open Review Queue →", "打开待审队列 →"), to: "/app/queue" },
    };
  },
};

const Q8: AskQA = {
  id: "certify",
  question: { en: "Can you certify that Demo Ship A's fire control plan complies with SOLAS?", zh: "你能证明 Demo Ship A 的消防控制图符合 SOLAS 吗？" },
  keywords: ["certify", "certification", "comply", "complies", "solas", "证明", "认证", "符合"],
  answer: c => {
    const a = c.projects.find(p => p.id === "demo_ship_a");
    const n = a?.images.length ?? 0;
    const signed = new Set(c.history.filter(h => h.projectId === "demo_ship_a").map(h => h.imageStem)).size;
    return {
      short: T(c, "**No.** I can't certify compliance, and neither can this tool. It counts portable extinguishers on **one deck** against **five illustrative rules**; the verdict is made by a certified surveyor when they sign.", "**不能。** 我无法出具合规证明，这个工具也不能。它只是按**五条示例规则**统计**单块甲板**上的便携式灭火器；结论由持证验船师签署时作出。"),
      basis: [
        T(c, "What the audit covers: portable extinguisher counts by type, per deck, against R01–R05 [1].", "审核覆盖的内容：按类型统计每块甲板的便携式灭火器数量，并对照 R01–R05 [1]。"),
        T(c, "What it does **not** cover: fixed fire-extinguishing systems, fire detection and alarm, fire doors and divisions, escape routes, the fire control plan's own format and symbols, and anything not visible on the uploaded sheet.", "**不**覆盖的内容：固定灭火系统、火灾探测与报警、防火门与防火分隔、逃生通道、消防控制图本身的格式和符号，以及上传图纸上看不到的一切。"),
        T(c, `Demo Ship A has ${n} plan sheets on file and ${signed} of them ${signed === 1 ? "has" : "have"} a signed review; a verdict on one deck says nothing about the others [2].`, `Demo Ship A 有 ${n} 张图纸，其中 ${signed} 张已有签署的评审；一块甲板的结论不能说明其他甲板 [2]。`),
        T(c, 'The regulation set is labelled "SOLAS 2020 + FSS Code 2015 (illustrative)" — a teaching set, not the regulation.', "规则集标注为“SOLAS 2020 + FSS Code 2015（示例）”——它是教学用的规则集，不是法规本身。"),
        T(c, "**What I can do:** show the signed reviews for Demo Ship A, list which decks are still unreviewed, or draft a summary for the surveyor.", "**我能做的：** 展示 Demo Ship A 已签署的评审、列出还没评审的甲板，或为验船师起草一份摘要。"),
      ],
      sources: [guide(c, "what-is", "What does the audit check?", "审核检查什么？"), { kind: "vessel", id: "demo_ship_a", label: T(c, `Fleet record · Demo Ship A (${n} decks)`, `船舶档案 · Demo Ship A（${n} 块甲板）`) }],
    };
  },
};

const Q9: AskQA = {
  id: "nogo-count",
  question: { en: "How many NO-GO verdicts in the last 60 days, and which vessels?", zh: "最近 60 天有多少 NO-GO 结论，分别是哪些船？" },
  keywords: ["how many", "last 60", "60 days", "多少", "最近 60", "60 天"],
  answer: c => {
    const recent = c.history.filter(h => c.now - new Date(h.submittedAt).getTime() <= 60 * DAY);
    const no = recent.filter(h => h.verdict === "NO_GO").sort((a, b) => b.submittedAt.localeCompare(a.submittedAt));
    const pct = recent.length ? Math.round((no.length / recent.length) * 100) : 0;
    const go = recent.filter(h => h.verdict === "GO").length, cond = recent.filter(h => h.verdict === "CONDITIONAL").length;
    const reviewers = Array.from(new Set(no.map(h => h.reviewer)));
    const sources: AskSource[] = [...no.map(reportSrc), { kind: "queue", id: "history", label: T(c, `History (${recent.length} reports)`, `历史记录（${recent.length} 份报告）`) }];
    return {
      short: no.length === 0
        ? T(c, `**No NO-GO verdicts in the last 60 days** (${recent.length} signed ${recent.length === 1 ? "review" : "reviews"}).`, `**最近 60 天没有 NO-GO 结论**（共 ${recent.length} 份已签署评审）。`)
        : T(c, `**${no.length} of ${recent.length} signed reviews (${pct} %) were NO-GO:** ${no.map(h => `${vesselName(h.projectId, h.projectLabel)} · ${h.imageLabel} (${ago(h.submittedAt, c)})`).join("; ")}.${reviewers.length === 1 ? ` ${no.length > 1 ? "Both" : "It was"} signed by ${reviewers[0]}.` : ""}`,
                  `**${recent.length} 份已签署评审中有 ${no.length} 份（${pct}%）为 NO-GO：** ${no.map(h => `${vesselName(h.projectId, h.projectLabel)} · ${h.imageLabel}（${ago(h.submittedAt, c)}）`).join("；")}。${reviewers.length === 1 ? `均由 ${reviewers[0]} 签署。` : ""}`),
      basis: [
        ...no.map((h, i) => `${vesselName(h.projectId, h.projectLabel)}: ${h.note || "—"} [${i + 1}]`),
        T(c, `Of the other ${recent.length - no.length}: ${go} GO, ${cond} CONDITIONAL.`, `其余 ${recent.length - no.length} 份：${go} 份 GO，${cond} 份 CONDITIONAL。`),
        T(c, `**Caveats:** this counts only reviews recorded in this workspace (${recent.length}). It is not a fleet-wide rate: the vessels reviewed are not a sample, and a vessel can have several decks reviewed on different dates.${reviewers.length === 1 && no.length > 1 ? " One reviewer signed all NO-GO reports, which may reflect assignment, not strictness." : ""}`, `**注意：** 这里只统计本工作区记录的评审（${recent.length} 份）。这不是全船队的比例：被评审的船不是抽样，且同一艘船的多块甲板可能在不同日期评审。${reviewers.length === 1 && no.length > 1 ? "所有 NO-GO 报告由同一位评审人签署，这可能反映任务分配，而不是严格程度。" : ""}`),
        T(c, "**Missing:** reviews done before this workspace was set up; the number of decks not yet reviewed per vessel.", "**缺失：** 本工作区建立之前的评审；每艘船尚未评审的甲板数量。"),
      ],
      sources,
    };
  },
};

const Q10: AskQA = {
  id: "dwg",
  question: { en: "Can I upload the shipyard's DWG file for Northern Star?", zh: "我可以为 Northern Star 上传船厂的 DWG 文件吗？" },
  keywords: ["dwg", "dxf", "cad", "shipyard", "upload", "船厂", "上传"],
  answer: c => ({
    short: T(c, "**Not directly — DWG and DXF are not supported (rule U1).** Export the fire control plan from CAD as **PDF, PNG or JPEG** and upload that.", "**不能直接上传——不支持 DWG 和 DXF（规则 U1）。** 请从 CAD 把消防控制图导出为 **PDF、PNG 或 JPEG** 再上传。"),
    basis: [
      T(c, "Accepted: PNG, JPEG, PDF (U1). Images ≤ 20 MB; PDFs ≤ 50 MB and ≤ 10 pages (U2). Long edge 2000–12000 px (U3); PDF pages are rasterised automatically [1].", "支持：PNG、JPEG、PDF（U1）。图片 ≤ 20 MB；PDF ≤ 50 MB 且 ≤ 10 页（U2）。长边 2000–12000 像素（U3）；PDF 页面自动转为图片 [1]。"),
      T(c, "Before upload you confirm the sheet is a fire control / general arrangement plan of this vessel, scale 1:100–1:500, symbols legible (U4), upright and not a screen photo (U5).", "上传前你需确认：图纸是本船的消防控制图 / 总布置图，比例 1:100–1:500，符号清晰（U4），方向正确且不是屏幕照片（U5）。"),
      T(c, "After upload the sheet is split into decks (segmentation). Check the boxes, drag to adjust, then confirm [2].", "上传后图纸会被拆分成甲板（分割）。核对方框、拖动调整，然后确认 [2]。"),
      T(c, "**General advice, not a company rule:** export at a high enough resolution that extinguisher symbols stay legible after the split; a plotted PDF is usually cleaner than a screenshot.", "**通用建议，不是公司规定：** 导出时分辨率要足够高，使分割后灭火器符号仍然清晰；打印输出的 PDF 通常比截图更干净。"),
      T(c, "**Missing:** which scale and symbol set the yard's drawing uses — if it doesn't follow the IMO fire control plan symbols, detection quality can drop and I can't predict by how much.", "**缺失：** 船厂图纸使用的比例和符号体系——如果不是 IMO 消防控制图符号，检测质量可能下降，我无法预测下降多少。"),
      T(c, "Demo notice: files are deleted after 24 hours; do not upload confidential plans (U6).", "演示提示：文件 24 小时后自动删除；请勿上传保密图纸（U6）。"),
    ],
    sources: [guide(c, "upload-spec", "What must an upload meet? (U1–U6)", "上传需要满足什么？（U1–U6）"), guide(c, "segmentation", "What is segmentation?", "什么是分割？")],
    action: { label: T(c, "Open Northern Star →", "打开 Northern Star →"), to: "/app/vessel", state: { projectId: "northern_star" } },
  }),
};

export const ASK_QA: AskQA[] = [Q1, Q2, Q3, Q4, Q5, Q6, Q7, Q8, Q9, Q10];

const norm = (s: string) => s.toLowerCase().replace(/\s+/g, " ").trim();

/** Exact question text first (either language), then keyword overlap (≥ 2 hits, best wins, ties → earlier). */
export function matchQuestion(text: string): AskQA | null {
  const t = norm(text);
  if (!t) return null;
  const exact = ASK_QA.find(q => norm(q.question.en) === t || norm(q.question.zh) === t);
  if (exact) return exact;
  let best: AskQA | null = null, bestScore = 1;
  for (const q of ASK_QA) {
    const score = q.keywords.filter(k => t.includes(k)).length;
    if (score > bestScore) { best = q; bestScore = score; }
  }
  return best;
}

export function fallbackAnswer(c: AskCtx): AskAnswer {
  return {
    short: T(c, "**I don't have a recorded answer for that in this demo.** I would rather say so than guess. Try one of the examples below.", "**演示里没有录制这个问题的答案。** 我宁可直说，也不会猜。请试试下面的示例问题。"),
    basis: [T(c, "This demo answers 10 recorded questions about the fleet, reviews, rules and uploads. A live version would search the signed reports, plans and rules and cite what it read.", "本演示只回答 10 个关于船队、评审、规则和上传的预录问题。正式版会检索已签署的报告、图纸和规则，并引用它读到的内容。")],
    sources: [],
  };
}
