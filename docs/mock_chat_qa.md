# Mock Chat — the 10 demo questions (ADR-F35)

Content for the mock Ask page. All figures come from the demo workspace (fleet records, seeded reviews, the five illustrative rules R01–R05, the Guide). Nothing is generated live. Each answer follows one anatomy:

- **Short answer** (always visible, 1–3 sentences, bold lead-in) → **Show basis ▼** (long answer: supporting points `[n]`, counter-evidence / uncertainty, missing information, what is general knowledge and not a company record) → **Sources** list `[n]` (click opens the report / vessel / rule) → *As of HH:MM* · 👍 👎.
- Where a file is missing the answer **says so, names the file, and offers the next action**. It never fills the gap.
- Every conclusion that needs a person is labelled **(proposal — needs review)**. Nothing is saved or sent from the chat.

Source types: **[Report]** signed review (`PVCB-FS-…`), **[Analysis]** an AI analysis awaiting review, **[Fleet]** vessel record, **[Rule]** audit rule R01–R05, **[Guide]** Help Center article. Report numbers below are the seeded ones.

| # | Question | Shows |
|---|---|---|
| 1 | Which vessels need my attention this week? | Short only (deterministic list) |
| 2 | Why is Southern Cross NO-GO? | Short + basis, uncertainty |
| 3 | Does Northern Star's accommodation deck meet the foam requirement? | **Missing file — won't guess** |
| 4 | What is the spare CO₂ rule (R05) and when does it apply? | Demo rule vs real regulation, general-knowledge flag |
| 5 | Draft a rectification notice to the master of Southern Cross | Draft + Copy, placeholders for unknowns |
| 6 | How is CONDITIONAL different from NO-GO, and what turns Northern Star into GO? | Explanation + gaps |
| 7 | What is in my review queue and what should I do first? | Prioritised proposal |
| 8 | Can you certify that Demo Ship A's plan complies with SOLAS? | **Refuses to over-claim** |
| 9 | How many NO-GO verdicts in the last 60 days, and which vessels? | Aggregate with caveats |
| 10 | Can I upload the shipyard's DWG for Northern Star? | Process guidance, spec citations |

Unmatched questions get an honest fallback: "I don't have a recorded answer for that in this demo. Try one of these:" plus three chips.

---

## Q1 · Which vessels need my attention this week?

**Short answer**
**2 vessels and 2 analyses need action.** Southern Cross is *Action Required* (NO-GO, Engine Room). Northern Star is *Pending Confirm* (CONDITIONAL). Two analyses are waiting in the Review Queue: Demo Ship B · Below Main Deck (Bow) and Demo Ship A · B Deck.

**Show basis**
- Southern Cross: last signed review NO-GO, 8 days ago [1].
- Northern Star: CONDITIONAL, 5 days ago, re-verification requested [2].
- Queue: both analyses are unsigned, so they are not in the compliance history yet [3].
- Scheduled, no action needed now: Pacific Trader, Ocean Pioneer, Eastern Wind.
- Not covered: surveys that are due by calendar date — the demo has no survey-due dates on file.

**Sources** [1] Report PVCB-FS-2026-0002 · Southern Cross · Engine Room · NO-GO  [2] Report PVCB-FS-2026-0003 · Northern Star · Accommodation Deck · CONDITIONAL  [3] Review Queue (2 items)

---

## Q2 · Why is Southern Cross NO-GO?

**Short answer**
**Suggested conclusion:** the NO-GO comes from two findings in the Engine Room review: the **CO₂ release point is obstructed** and **one portable extinguisher has an expired tag (2024)**. Signed by M. Tan; 5 of 7 detections confirmed, 2 flagged. *(proposal — needs review)*

**Show basis**
- The surveyor's note records both findings and the 5 / 2 split between confirmed and flagged detections [1].
- The two flagged detections match the two findings; the report does not list which symbol each one is.
- **Uncertainty:** the records contain no follow-up. I cannot tell whether the obstruction was cleared or the extinguisher replaced, so the NO-GO may be out of date.
- **Missing:** a re-inspection report, the rectification date, and the plan sheet for Southern Cross (no plan is uploaded, so I cannot re-count anything).
- Next step I'd suggest: a re-inspection after the master confirms rectification.

**Sources** [1] Report PVCB-FS-2026-0002 · Southern Cross · Engine Room · NO-GO  [2] Fleet record · Southern Cross (status: Action Required)

---

## Q3 · Does Northern Star's accommodation deck meet the foam requirement? — *missing file*

**Short answer**
**I can't confirm that from the records.** The rule that applies is **R03** (≥ 1 foam extinguisher in accommodation spaces), but **no plan sheet is uploaded for Northern Star**, and the signed review stores only totals, not a count per extinguisher type.

**Show basis**
- R03 applies to accommodation spaces and is a *warning*-level rule: no foam unit gives CONDITIONAL, not NO-GO [1].
- The Accommodation Deck review shows 6 detections, 5 confirmed, 1 flagged, CONDITIONAL. The note is about **smoke detector spacing**, not extinguishers [2]. So the CONDITIONAL does not tell us whether foam is present.
- I will **not** infer foam presence from the verdict: a CONDITIONAL could come from R03 or from something else.
- **Missing:** the Northern Star plan sheet; a per-category detection count for that review.
- **To get a real answer:** upload the plan (Vessel → Northern Star → Upload plan), run the analysis, and R03 is evaluated on the actual count.
- Note: the R03 wording in this demo is an illustrative rule, not a quotation of the FSS Code.

**Sources** [1] Rule R03 · accommodation foam (illustrative)  [2] Report PVCB-FS-2026-0003 · Northern Star · Accommodation Deck
**Action chip:** *Upload plan for Northern Star →*

---

## Q4 · What is the spare CO₂ rule (R05) and when does it apply?

**Short answer**
**R05 requires at least 1 spare CO₂ extinguisher when the plan shows 2 or more CO₂ extinguishers;** with 0 or 1 CO₂ unit it is *not applicable*. Missing spare → CONDITIONAL (a warning, not a failure).

**Show basis**
- Demo rule set: R05, article reference "FSS Code Ch.6/2.2", `required ≥ 1 spare when CO₂ ≥ 2` [1].
- Example: 3 CO₂ units and 0 spare → CONDITIONAL; 3 CO₂ and 1 spare → GO; 1 CO₂ and 0 spare → N/A.
- **This is a demo rule.** The article numbers are placeholders, not a legal citation, and every R01–R05 is marked as illustrative.
- **General knowledge, not a company record:** the real requirement works differently. Under SOLAS II-2 and the FSS Code, spare charges are provided for portable extinguishers that can be recharged on board — roughly 100 % of the first 10 and 50 % of the rest, capped at 60 in total. Check the current consolidated edition before relying on this; I have no live regulation source connected.
- **Missing:** the class society's own interpretation for a specific vessel.

**Sources** [1] Rule R05 · spare CO₂ (illustrative)  [2] Guide · "What does the audit check?"

---

## Q5 · Draft a rectification notice to the master of Southern Cross

**Short answer**
Draft prepared for **Southern Cross**, based on the two findings in the last Engine Room review. Check the facts and fill the bracketed fields before use.

> **Subject:** Southern Cross (IMO 9 512 087) — Engine Room fire-safety findings, report PVCB-FS-2026-0002
>
> Dear Captain [Master's name],
>
> Following the fire-safety plan survey of the Engine Room, the following findings are open:
> 1. The CO₂ release point is obstructed. Please clear access and confirm the release point is unobstructed and clearly marked.
> 2. One portable extinguisher carries an expired service tag (2024). Please service or replace it and confirm the unit's location and new tag date.
>
> Please send photographic evidence of both items by [date to be agreed] and request a re-inspection once complete.
>
> Best regards,
> [Surveyor name], Pacific Vessel Classification Bureau

*Draft only: check the facts first. Nothing is sent from the chat.* **[Copy]**

**Show basis**
- Both findings and the report number come from the signed review [1].
- **Left blank on purpose:** master's name, deadline, extinguisher location / ID — none are in the records. The deadline is a commercial / class decision for the surveyor.
- I did not add a regulatory citation: the report does not state which requirement each finding breaches.

**Sources** [1] Report PVCB-FS-2026-0002  [2] Fleet record · Southern Cross

---

## Q6 · How is CONDITIONAL different from NO-GO, and what turns Northern Star into GO?

**Short answer**
**NO-GO = a mandatory check failed; CONDITIONAL = no failure but a warning to resolve; GO = all checks pass.** Northern Star is CONDITIONAL because of marginal smoke-detector spacing in the crew corridor, so it can reach GO once that is re-verified and signed. *(proposal — needs review)*

**Show basis**
- In the rule set, R01 / R02 / R04 are *fail* rules (→ NO-GO); R03 and R05 are *warning* rules (→ CONDITIONAL) [1].
- The overall verdict is the worst of the individual checks.
- Northern Star's note: "smoke detector spacing marginal in crew corridor; re-verify on next survey" [2]. That is a surveyor judgement, not one of R01–R05.
- **Missing:** the date of the next survey; the detector spacing numbers; who owns the re-verification. I can't say when GO would be reached.
- What a CONDITIONAL means for a real flag state or class record is outside these records.

**Sources** [1] Guide · "What do GO, CONDITIONAL and NO-GO mean?"  [2] Report PVCB-FS-2026-0003 · Northern Star · Accommodation Deck

---

## Q7 · What is in my review queue and what should I do first?

**Short answer**
**2 analyses are waiting:** Demo Ship A · B Deck (analysed 2 h ago) and Demo Ship B · Below Main Deck (Bow) (analysed 1 h ago). **Suggested order: Demo Ship A · B Deck first, because it has waited longest.** I can't rank them by risk. *(proposal — needs review)*

**Show basis**
- Both are unsigned AI analyses, so neither counts toward compliance history until a surveyor reviews it [1].
- The queue record stores no AI verdict or flagged-item count, so I have no basis to say which deck is more likely to be NO-GO. Oldest-first is a neutral default, not a risk call.
- If you want a risk-based order, open each analysis and look at its verdict first; I can then re-rank.
- **Missing:** AI verdict and flagged count per queued item.
- Each review takes: accept / flag detections → Submit → Sign & Submit.

**Sources** [1] Review Queue (2 items)  [2] Guide · "How do I complete a review?"
**Action chip:** *Open Review Queue →*

---

## Q8 · Can you certify that Demo Ship A's fire control plan complies with SOLAS?

**Short answer**
**No.** I can't certify compliance, and neither can this tool. It counts portable extinguishers on **one deck** against **five illustrative rules**; the verdict is made by a certified surveyor when they sign.

**Show basis**
- What the audit covers: portable extinguisher counts by type, per deck, against R01–R05 [1].
- What it does **not** cover: fixed fire-extinguishing systems, fire detection and alarm, fire doors and divisions, escape routes, the fire control plan's own format and symbols, and anything not visible on the uploaded sheet.
- Demo Ship A has 3 plan sheets on file; only the decks that have been analysed and signed produce a verdict, and a verdict on one deck says nothing about the others [2].
- The regulation set is labelled "SOLAS 2020 + FSS Code 2015 (illustrative)" — it is a teaching set, not the regulation.
- **What I can do:** show the signed reviews for Demo Ship A, list which decks are still unreviewed, or draft a summary for the surveyor.

**Sources** [1] Guide · "What does the audit check?"  [2] Fleet record · Demo Ship A (3 decks)

---

## Q9 · How many NO-GO verdicts in the last 60 days, and which vessels?

**Short answer**
**2 of 6 signed reviews (33 %) were NO-GO:** Southern Cross · Engine Room (8 days ago) and Pacific Trader · Cargo Hold 2 (47 days ago). Both signed by M. Tan.

**Show basis**
- Southern Cross: CO₂ release point obstructed; one extinguisher tag expired [1].
- Pacific Trader: fixed fire-extinguishing coverage incomplete at the aft bulkhead [2].
- Of the other 4: 3 GO, 1 CONDITIONAL.
- **Caveats:** this counts only reviews recorded in this workspace (6). It is not a fleet-wide rate: the vessels reviewed are not a sample, and a vessel can have several decks reviewed on different dates. One reviewer signed both NO-GO reports, which may reflect assignment, not strictness.
- **Missing:** reviews done before this workspace was set up; the number of decks not yet reviewed per vessel.

**Sources** [1] Report PVCB-FS-2026-0002  [2] Report PVCB-FS-2026-0006  [3] History (6 reports)

---

## Q10 · Can I upload the shipyard's DWG file for Northern Star?

**Short answer**
**Not directly — DWG and DXF are not supported (rule U1).** Export the fire control plan from CAD as **PDF, PNG or JPEG** and upload that.

**Show basis**
- Accepted: PNG, JPEG, PDF (U1). Images ≤ 20 MB; PDFs ≤ 50 MB and ≤ 10 pages (U2). Long edge 2000–12000 px (U3); PDF pages are rasterised automatically [1].
- Before upload you confirm the sheet is a fire control / general arrangement plan of this vessel, scale 1:100–1:500, symbols legible (U4), upright and not a screen photo (U5).
- After upload the sheet is split into decks (segmentation). Check the boxes, drag to adjust, then confirm.
- **General advice, not a company rule:** export at a high enough resolution that extinguisher symbols stay legible after the split; a plotted PDF is usually cleaner than a screenshot.
- **Missing:** which scale and symbol set the yard's drawing uses — if it doesn't follow the IMO fire control plan symbols, detection quality can drop and I can't predict by how much.
- Demo notice: files are deleted after 24 hours; do not upload confidential plans (U6).

**Sources** [1] Guide · "What must an upload meet?" (U1–U6)  [2] Guide · "What is segmentation?"
**Action chip:** *Open Northern Star →*
