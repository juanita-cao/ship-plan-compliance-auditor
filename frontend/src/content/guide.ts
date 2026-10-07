import { UPLOAD_SPEC } from "../config";

export type GuideGroup = "start" | "vessels" | "detection" | "rules" | "review" | "data";
export type L10n = { en: string; zh: string };

export interface GuideLink { label: L10n; to: string }
export interface GuideArticle {
  id: string;
  group: GuideGroup;
  q: L10n;
  /** Paragraphs; `**bold**` is the only markup. */
  a: { en: string[]; zh: string[] };
  links?: GuideLink[];
}

export const GUIDE_GROUPS: { id: GuideGroup; label: L10n }[] = [
  { id: "start",     label: { en: "Getting started",   zh: "入门" } },
  { id: "vessels",   label: { en: "Vessels & plans",   zh: "船舶与图纸" } },
  { id: "detection", label: { en: "Detection",         zh: "检测" } },
  { id: "rules",     label: { en: "Verdicts & rules",  zh: "结论与规则" } },
  { id: "review",    label: { en: "Review workflow",   zh: "评审流程" } },
  { id: "data",      label: { en: "Data & access",     zh: "数据与访问" } },
];

const L = {
  overview: { en: "Vessel Overview", zh: "船舶总览" },
  queue:    { en: "Review Queue",    zh: "待审队列" },
  history:  { en: "History",         zh: "历史记录" },
};

export const GUIDE_ARTICLES: GuideArticle[] = [
  {
    id: "what-is", group: "start",
    q: { en: "What is the PVCB Compliance Auditor?", zh: "什么是 PVCB 合规审核系统？" },
    a: {
      en: ["It checks the fire-safety plans of a vessel against SOLAS Chapter II-2 and the FSS Code: it finds the fire equipment on each deck plan, checks the counts against the rules, and hands the result to a human surveyor to confirm.",
           "Nothing is final until a surveyor signs the review."],
      zh: ["系统对照 SOLAS 第 II-2 章和 FSS 规则检查船舶的消防安全图纸：在每张甲板图上找出消防设备，按规则核对数量，再交给验船师人工确认。",
           "验船师签署之前，任何结果都不是最终结论。"],
    },
  },
  {
    id: "real-data", group: "start",
    q: { en: "Is this real data?", zh: "这是真实数据吗？" },
    a: {
      en: ["No. Vessel names, IMO numbers, surveyors, the society (PVCB) and all plans are fictional or anonymised. Do not enter confidential or commercially sensitive material."],
      zh: ["不是。船名、IMO 编号、验船师、船级社（PVCB）和所有图纸均为虚构或已匿名。请勿输入任何保密或商业敏感的资料。"],
    },
  },
  {
    id: "workflow", group: "start",
    q: { en: "What is the typical workflow?", zh: "典型的使用流程是什么？" },
    a: {
      en: ["1. Pick a vessel in Vessel Overview.", "2. Choose a deck.", "3. Run Analysis.",
           "4. Review each detection, then sign off and submit the review.",
           "5. Find the signed result in History and open the survey report."],
      zh: ["1. 在船舶总览中选择一艘船。", "2. 选择一块甲板。", "3. 点击开始分析。",
           "4. 逐项评审检测结果，然后签署并提交评审。", "5. 在历史记录中查看已签署的结果，并打开检验报告。"],
    },
    links: [{ label: L.overview, to: "/app" }, { label: L.queue, to: "/app/queue" }, { label: L.history, to: "/app/history" }],
  },
  {
    id: "statuses", group: "vessels",
    q: { en: "What do the vessel statuses mean?", zh: "船舶状态分别代表什么？" },
    a: {
      en: ["**To Review** — an analysis is waiting in the Review Queue.",
           "**Pending Confirm** — the latest result is CONDITIONAL and awaits supervisor countersign.",
           "**Action Required** — the latest result is NO-GO; rectification is outstanding.",
           "**Up to Date** — the latest result is GO.",
           "**Scheduled** — the next survey is booked.",
           "The Compliance column always shows the latest signed verdict. Click a status to see the related reviews."],
      zh: ["**待评审** — 有分析结果在待审队列中等待。",
           "**待会签** — 最近结论为有条件通过，等待主管会签。",
           "**需整改** — 最近结论为 NO-GO，整改尚未完成。",
           "**已达标** — 最近结论为 GO。",
           "**已排期** — 下一次检验已安排。",
           "“合规结论”列始终显示最近一次已签署的结论。点击状态可查看相关评审。"],
    },
    links: [{ label: L.overview, to: "/app" }],
  },
  {
    id: "which-plans", group: "vessels",
    q: { en: "Which plans can I analyze?", zh: "可以分析哪些图纸？" },
    a: {
      en: ["The bundled fire-safety general arrangement plans of Demo Ship A (3 decks) and Demo Ship B (3 decks) work with the full detection demo. For any vessel you can also upload your own plan; see “How do I upload a plan?”.",
           "Plans are expected at scale 1:100–1:500 with standard IMO fire-equipment symbols."],
      zh: ["Demo Ship A（3 块甲板）和 Demo Ship B（3 块甲板）自带的消防安全总布置图可体验完整的检测演示。你也可以为任意船舶上传自己的图纸，见“如何上传图纸？”。",
           "图纸应为 1:100–1:500 比例，并使用标准的 IMO 消防设备图例。"],
    },
    links: [{ label: L.overview, to: "/app" }],
  },
  {
    id: "switch-vessel", group: "vessels",
    q: { en: "How do I switch vessels?", zh: "如何切换船舶？" },
    a: {
      en: ["Click a vessel in Vessel Overview, or use the vessel selector at the top right of the analysis page. Switching resets the current analysis, not your saved reviews."],
      zh: ["在船舶总览中点击船舶，或使用分析页右上角的船舶选择器。切换只会重置当前分析，不影响已保存的评审。"],
    },
    links: [{ label: L.overview, to: "/app" }],
  },
  {
    id: "upload-how", group: "vessels",
    q: { en: "How do I upload a plan?", zh: "如何上传图纸？" },
    a: {
      en: ["Open a vessel and click “Upload plan” (top right of the deck list, or in the empty state). Tick the two confirmations, then drop or choose a file.",
           "The file is checked, split into decks automatically, and shown to you for review. Rename a deck, remove anything that is not a deck, then confirm. The new decks appear in the deck list tagged “Uploaded”."],
      zh: ["打开一艘船，点击“上传图纸”（在甲板列表右上角，或空状态中）。勾选两项确认后，拖入或选择文件。",
           "系统会检查文件、自动切分成甲板，并展示给你核对。可以修改甲板名称、移除不是甲板的区域，然后确认。新甲板会出现在甲板列表中，并带有“已上传”标记。"],
    },
    links: [{ label: L.overview, to: "/app" }],
  },
  {
    id: "upload-spec", group: "vessels",
    q: { en: "What must an upload meet?", zh: "上传的文件需要满足什么要求？" },
    a: {
      en: UPLOAD_SPEC.map(r => `**${r.id} ${r.label.en}** — ${r.text.en}`),
      zh: UPLOAD_SPEC.map(r => `**${r.id} ${r.label.zh}** — ${r.text.zh}`),
    },
  },
  {
    id: "segmentation", group: "vessels",
    q: { en: "What is segmentation, and can I correct it?", zh: "什么是分割？可以修正吗？" },
    a: {
      en: ["A plan sheet often holds several decks. Segmentation finds the blank gaps between them and cuts the sheet into separate deck images, named Deck 1, Deck 2 … from top to bottom. It uses simple image processing, not an AI model.",
           "You always review the result on the sheet: drag a box to move it, drag its edges or corners to resize it, add a missing deck, rename or remove one, or choose “Treat whole sheet as one deck” if the split is wrong. Only the decks you confirm are added."],
      zh: ["一张图纸上常常有多块甲板。分割会找出它们之间的空白间隔，把整张图切成独立的甲板图，并从上到下命名为 Deck 1、Deck 2……。它使用简单的图像处理，不是 AI 模型。",
           "分割结果始终由你在图上核对：可以拖动方框移动位置、拖动边或角调整大小、添加漏掉的甲板、改名或移除，切分不对时也可选择“整张图当作一个甲板”。只有你确认的甲板才会被添加。"],
    },
  },
  {
    id: "sample-result", group: "detection",
    q: { en: "Why does an uploaded deck show a “sample result”?", zh: "为什么上传的甲板显示“示例结果”？" },
    a: {
      en: ["The public demo has no detection model connected. For an uploaded deck, the counts, compliance table and highlight come from a bundled sample plan (named in the banner) and do not describe your drawing.",
           "Your own drawing is still shown as the Original Plan, and the review workflow works the same way."],
      zh: ["公开演示没有接入检测模型。对于上传的甲板，数量、合规表格和高亮图都来自自带的示例图纸（横幅中会写明），并不代表你的图纸。",
           "你自己的图纸仍会作为“原图”显示，评审流程的用法完全相同。"],
    },
  },
  {
    id: "how-detect", group: "detection",
    q: { en: "How does detection work?", zh: "检测是如何进行的？" },
    a: {
      en: ["A vision-language model reads the plan and lists fire-equipment instances with their locations. Several runs are compared by voting to reduce one-off errors, and positions are refined locally.",
           "In this public demo, the results for the bundled plans are pre-computed from recorded runs, so no live model call is made."],
      zh: ["视觉语言模型读取图纸，列出消防设备及其位置；多次运行的结果通过投票对比，以减少偶发错误，位置再在本地做精修。",
           "在这个公开演示中，自带图纸的结果是根据已录制的运行预先计算好的，因此不会实时调用模型。"],
    },
  },
  {
    id: "categories", group: "detection",
    q: { en: "What equipment is detected?", zh: "会检测哪些设备？" },
    a: {
      en: ["Portable extinguishers (for example CO₂ 5 kg, dry powder 6 kg, foam 9 L) and other categories configured per vessel. The categories checked for a vessel are listed in the equipment inventory of the results."],
      zh: ["便携式灭火器（例如 CO₂ 5 kg、干粉 6 kg、泡沫 9 L）以及按船舶配置的其他类别。每艘船检查的类别会列在结果页的设备清单中。"],
    },
  },
  {
    id: "read-results", group: "detection",
    q: { en: "How do I read the results?", zh: "如何阅读分析结果？" },
    a: {
      en: ["The left image is the original plan; the middle image highlights the detections. In the inventory, click a category to isolate it, click one instance to locate it, or “All Found Equipment” to reset."],
      zh: ["左侧是原图，中间高亮显示检出的设备。在设备清单中，点击某个类别可单独查看，点击单个实例可定位，点击“全部检出设备”可恢复。"],
    },
  },
  {
    id: "trace", group: "detection",
    q: { en: "How do I see the reasoning trace?", zh: "如何查看推理过程？" },
    a: {
      en: ["On the results page, expand “Detection Reasoning Trace” below the compliance table. It shows the raw model response used for the result."],
      zh: ["在结果页的合规表格下方展开“检测推理过程”，可以看到本次结果所使用的模型原始输出。"],
    },
  },
  {
    id: "regulations", group: "rules",
    q: { en: "What regulations are checked?", zh: "检查哪些规则？" },
    a: {
      en: ["SOLAS Chapter II-2 (fire protection, detection and extinction) and the FSS Code — for example the minimum number of extinguishers per plan. The compliance table lists exactly which articles were applied."],
      zh: ["SOLAS 第 II-2 章（防火、探火与灭火）和 FSS 规则，例如每张图纸的灭火器最低数量。合规表格会列出具体应用了哪些条款。"],
    },
  },
  {
    id: "verdicts", group: "rules",
    q: { en: "What do the verdicts mean?", zh: "各个结论是什么意思？" },
    a: {
      en: ["**GO** — all checked rules pass.", "**NO-GO** — a mandatory rule fails; the plan cannot be approved as is.",
           "**CONDITIONAL** — minor deficiencies; approval is subject to corrective action.", "**N/A** — the rule does not apply to this vessel type."],
      zh: ["**GO** — 所检规则全部通过。", "**NO-GO** — 有强制性规则未满足，图纸不能按现状批准。",
           "**CONDITIONAL** — 存在轻微缺陷，整改后方可批准。", "**N/A** — 该规则不适用于此类船舶。"],
    },
  },
  {
    id: "mock-badge", group: "rules",
    q: { en: "Why does a result say MOCK or “illustrative”?", zh: "为什么结果上标着“演示”或“仅供示意”？" },
    a: {
      en: ["The compliance rules in this demo are simplified and are not an official interpretation. Results marked MOCK are for illustration only and must not be used for real approvals."],
      zh: ["本演示中的合规规则经过简化，不是官方解释。标有“演示”的结果仅供示意，不得用于真实审批。"],
    },
  },
  {
    id: "human-review", group: "review",
    q: { en: "What is Human Review and why is it required?", zh: "什么是人工评审？为什么必须有？" },
    a: {
      en: ["The AI proposes; a surveyor decides. For each detection you Confirm or Flag it, you may add anything the AI missed, and you may override the overall verdict with a written note. The reviewer, time and decisions are recorded with the result."],
      zh: ["AI 提出建议，验船师做决定。对每个检测结果，你可以确认或标记；可以补充 AI 漏检的设备；也可以附上书面说明来修改整体结论。评审人、时间和各项决定会与结果一起记录。"],
    },
  },
  {
    id: "submit-review", group: "review",
    q: { en: "How do I review and submit?", zh: "如何评审并提交？" },
    a: {
      en: ["Confirm or flag every detection (Accept All confirms the rest). You may override the verdict — a note is then required. Submit Review opens a sign-off window that summarises your decision; Sign & Submit records it.",
           "After signing, the review cannot be edited. The item leaves the Review Queue, and you can open its report or jump to the next item in the queue."],
      zh: ["对每个检测结果选择确认或标记（“全部确认”可一次确认剩余项）。可以修改结论，此时必须填写备注。点击“提交评审”会弹出签署窗口，汇总你的决定；点击“签署并提交”即正式记录。",
           "签署后评审不可修改。该项会离开待审队列，你可以打开报告，或直接进入队列中的下一项。"],
    },
    links: [{ label: L.queue, to: "/app/queue" }],
  },
  {
    id: "queue-history", group: "review",
    q: { en: "What are the Review Queue and History?", zh: "待审队列和历史记录是什么？" },
    a: {
      en: ["The Review Queue lists analyses that are not yet signed off. History lists signed reviews. Open a History row to read the survey report, and use Print / Save PDF to export it."],
      zh: ["待审队列列出尚未签署的分析；历史记录列出已签署的评审。点击历史记录中的一行可查看检验报告，并用“打印 / 保存 PDF”导出。"],
    },
    links: [{ label: L.queue, to: "/app/queue" }, { label: L.history, to: "/app/history" }],
  },
  {
    id: "correct-ai", group: "review",
    q: { en: "How do I correct the AI?", zh: "如何纠正 AI 的错误？" },
    a: {
      en: ["Flag a wrong detection (it is not counted as confirmed), or use “Add Missing Instance” for something the AI missed. Both are recorded as manual decisions in the review."],
      zh: ["对错误的检测结果点“标记”（不计入已确认）；对漏检的设备使用“补充漏检设备”。两者都会作为人工决定记录在评审中。"],
    },
  },
  {
    id: "who-access", group: "data",
    q: { en: "Who can access this, and where is my data kept?", zh: "谁可以访问？我的数据存放在哪里？" },
    a: {
      en: ["Anyone with the demo credentials. Reviews and history are stored only in this browser (local storage) and are not sent anywhere. Use “Reset demo data” in the user menu to return to the seeded demo state; clearing the site data does the same.",
           "A production system would use an audited server-side log."],
      zh: ["任何拥有演示账号的人。评审和历史记录只保存在当前浏览器（本地存储）中，不会发送到任何地方。在用户菜单中选择“重置演示数据”即可恢复初始演示状态，清除站点数据也有同样效果。",
           "正式系统会使用带审计的服务器端日志。"],
    },
  },
];
