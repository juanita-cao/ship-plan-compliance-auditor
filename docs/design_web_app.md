# Ship Plan Compliance Auditor — Web App Design

The React + FastAPI app on top of the detection pipeline (see [design_backend.md](design_backend.md)). The original Streamlit UI is described in [design_frontend.md](design_frontend.md); this document covers the web app only. All vessels, surveyors and the classification society (PVCB) are fictional. Compliance rules are illustrative.

## 1. Goals and scope

| Goal | How |
|---|---|
| A reviewer can see every vessel, open a deck plan, run the audit, and sign off | Overview → Vessel → Review Queue → History |
| Nothing counts as a result until a human signs it | Analyses wait in a queue; only signed reviews enter the compliance history |
| Bring a new plan into the tool | Upload → segment into decks → confirm boxes → analyse |
| Ask questions with cited, honest answers | Copilot page: short answer, expandable basis, sources, "missing" stated, never guessed |
| Free to share | A static build that serves recorded results and needs no backend |

Out of scope: real LLM in the Copilot page (answers are recorded), accounts and permissions (login is a demo gate), a database for reviews (browser storage).

## 2. Architecture

```
React 18 + Vite + TypeScript        FastAPI (Python)                 Pipeline (src/)
Ant Design, react-router, react-query    /api/projects, /image, /detect,   detect → count → compliance rules
i18n (EN / ZH), Vitest                   /spotlight, /projects/{id}/plans, ...
browser storage: reviews, queue, history
```

- **Server data** (projects, images, detection results, highlight images, plan upload) goes through one HTTP client. **Review state** (analysed decks, signed reviews) lives in the browser.
- **Static build:** with `VITE_STATIC_DEMO=1` the HTTP client uses an adapter that answers the same requests from pre-exported JSON in `frontend/public/demo-data/` (exported by `scripts/export_static_demo.py`). Upload and segmentation show an explanatory card instead. See [static_deploy.md](static_deploy.md).

## 3. Screens

| Route | Purpose |
|---|---|
| `/app` Vessel Overview | All vessels with a derived status badge; badges link to the related queue / history |
| `/app/vessel` | Step bar (Upload → Segment → Review decks → Analyze), deck picker, plan preview, `Run Analysis`, results |
| `/app/queue` Review Queue | Analyses not yet signed; `Open Review` runs the analysis and opens the review panel |
| `/app/history` History | Signed reviews, filters, printable survey report drawer |
| `/app/ask` Copilot | Recorded Q&A (see section 7) |
| `/guide` Help Center | Searchable articles, upload specification rendered from the same constants as the upload checks |

**Vessel status** (one rule for Overview and Copilot): analyses waiting → *To Review*; scheduled → *Scheduled*; otherwise the latest signed verdict: NO-GO → *Action Required*, CONDITIONAL → *Pending Confirm*, GO → *Up to Date*.

## 4. State machines (pure functions, unit-tested)

**Analysis page:** `IDLE → RUNNING → RESULTS`; `New Analysis` returns to IDLE; changing vessel resets.

**Review panel:**

| State | Event | Next |
|---|---|---|
| `RV_EDITING` | all detections decided + note filled | `Submit` enabled |
| `RV_EDITING` | `Submit` | `RV_SIGNING` (sign-off dialog) |
| `RV_SIGNING` | confirm signature | `RV_DONE` (review saved, completion card, `Next in queue`) |
| `RV_SIGNING` | cancel | `RV_EDITING` |
| `RV_DONE` | — | read-only; a signed deck cannot be edited or reset |

A review is *pending* when its analysis timestamp is newer than the latest signed review of the same deck.

**Upload workflow:**

| State | Event | Next |
|---|---|---|
| `UP_IDLE` | file chosen, both confirmations ticked, client checks pass | `UP_UPLOADING` |
| `UP_IDLE` | client check fails | `UP_ERROR` (rule id + message) |
| `UP_UPLOADING` | uploaded | `UP_SEGMENTING` |
| `UP_SEGMENTING` | segmented | `UP_REVIEW` (zero regions → one whole-sheet region) |
| `UP_REVIEW` | rename / remove / drag / resize / add box | `UP_REVIEW` |
| `UP_REVIEW` | confirm (≥ 1 box, all named) | `UP_DONE` |
| any | cancel | `UP_IDLE`, plan deleted on the server |

Step bar mapping: `UP_IDLE` = 1, `UP_UPLOADING`/`UP_SEGMENTING` = 2, `UP_REVIEW` = 3, `UP_DONE` or any deck selected = 4.

## 5. Upload specification and segmentation

| ID | Requirement | Enforced |
|---|---|---|
| U1 | PNG, JPEG or PDF (PDF pages are rasterised and stitched top to bottom); DWG / DXF not supported | Client + server (magic bytes) |
| U2 | Image ≤ 20 MB; PDF ≤ 50 MB and ≤ 10 pages | Client + server |
| U3 | Long edge 2000–12000 px; 100 M pixel cap | Client + server |
| U4 | A fire control / general arrangement plan, one vessel per upload, scale 1:100–1:500, symbols legible | Confirm checkbox |
| U5 | Upright, not mirrored, not a photo of a screen | Confirm checkbox |
| U6 | Demo only, no confidential plans; files deleted after 24 h | Notice |

**Segmentation** is classical image processing (no model, no paid API): binarise → recursive cut along horizontal / vertical blank gaps → drop regions under 1.5 % of the inked area (favouring recall; the user can delete extras) → at most 12 regions named *Deck 1…N* top to bottom. The user always reviews the result on the sheet: move or resize boxes (8 handles, ≥ 100 px, inside the sheet), add, rename, remove, or treat the whole sheet as one deck. The server re-validates every adjusted box on confirm.

Uploaded decks get a clearly labelled **sample** detection result (no model is connected in the demo).

## 6. API (FastAPI)

| Method | Path | Notes |
|---|---|---|
| GET | `/api/projects` | All vessels; those without plans have `images: []` |
| GET | `/api/image/{project}/{stem}` | Deck image as a data URL |
| POST | `/api/detect` | `DetectResult` (instances, per-category totals, compliance result) |
| GET | `/api/spotlight/{project}/{stem}?category=&instance_id=` | Highlight image; a selected instance overrides the category |
| POST | `/api/projects/{id}/plans` | Upload (rules U1–U3, 5 plans per vessel) |
| POST | `/api/plans/{id}/segment` | Regions with bounding boxes and confidence |
| GET | `/api/plans/{id}/sheet` | The stitched sheet |
| POST | `/api/plans/{id}/confirm` | `{decks: [{region_id, label, bbox?}]}`; empty = whole sheet |
| DELETE | `/api/plans/{id}` | Discard an unconfirmed plan |

Errors use `{rule, message}` so the UI can show the specification rule that failed.

## 7. Copilot page

Ten recorded questions with answers computed from the live browser data where they depend on it (vessel status, queue, history, whether a plan exists), so they stay true after a review is signed.

Answer anatomy: short answer (always visible) → `Show basis` (supporting points with `[n]` citations, counter-evidence, **missing information**, what is general knowledge and not a record) → source list (opens the report, vessel, queue or Help Center article) → "as of" time → thumbs. Conclusions that need a person are marked *proposal — needs review*. Drafts are copy-only. Acceptance criterion: when a file or fact is missing the answer says so, names it and offers the next action; unmatched questions get a fixed honest fallback.

The question deck is in [mock_chat_qa.md](mock_chat_qa.md).

## 8. Internationalisation and consistency

English and Chinese dictionaries have identical key sets (checked by a test). Server-generated text (rule descriptions, deck names) stays English. One vessel name per vessel everywhere (`vesselName`). Demo data can be reset from the header menu.

## 9. Tests

| Area | Coverage |
|---|---|
| State machines | Upload FSM, review panel FSM, step mapping, drag maths (move / resize / clamp) |
| Content | Help Center search, i18n key parity, Copilot matching and computed answers |
| Static adapter | Request → exported file mapping, sanitised names |
| Backend | API contract, upload validation, segmentation, adjusted boxes, static export completeness |

End-to-end browser passes (EN and ZH) cover upload → drag → confirm, review → sign-off → next in queue, and the static build served with the API stopped.

## 10. Task list and implementation status

| # | Task | Status |
|---|---|---|
| T1 | Vessel Overview, Review Queue, History pages with consistent layout | ✅ done |
| T2 | Diverse fleet data, derived vessel status, survey report drawer (print) | ✅ done |
| T3 | Mascot with idle animation, click motion and sound | ✅ done |
| T4 | Review loop: panel state machine, sign-off dialog, completion card, next in queue | ✅ done |
| T5 | Help Center rewrite: search, categories, deep links | ✅ done |
| T6 | Journey fixes: every vessel openable, one name per vessel, breadcrumbs, full i18n, reset | ✅ done |
| T7 | Plan upload API: validation, quota, cleanup | ✅ done |
| T8 | Segmentation (blank-gap cuts) and confirm API | ✅ done |
| T9 | Upload workflow UI: step bar, dropzone with specification, progress | ✅ done |
| T10 | Segment review canvas: draggable / resizable / addable boxes, server validation | ✅ done |
| T11 | Copilot page: recorded Q&A, cited answers, expandable basis | ✅ done |
| T12 | Static demo export and adapter | ✅ done |
| T13 | Static notice for upload, static build and deploy guide | ✅ done |
| T14 | Real LLM behind the Copilot page | ⬜ not built |
| T15 | Persistent review storage on a server | ⬜ not built |
