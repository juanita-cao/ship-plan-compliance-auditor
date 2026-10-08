import { DeleteOutlined, InboxOutlined, PlusOutlined } from "@ant-design/icons";
import { Alert, Button, Checkbox, Input, Progress, Tag, Upload, message } from "antd";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useReducer, useRef, useState } from "react";
import type { PointerEvent as RPointerEvent } from "react";
import { useTranslation } from "react-i18next";
import {
  IS_STATIC_DEMO, apiError, confirmPlan, deletePlan, planSheet, segmentPlan, uploadPlan, type ImageInfo,
} from "../api/client";
import { UPLOAD_SPEC } from "../config";
import {
  UPLOAD_INITIAL, canConfirm, checkDims, checkFileMeta, moveBox, planStep, resizeBox, uploadReducer,
  type EditableRegion, type Handle, type RuleError,
} from "../state/uploadState";
import { PlanStepper } from "./PlanStepper";
import { StaticNotice } from "./StaticNotice";

const SUB = "#6b7280";
const BORDER = "#e5e8ed";
const BLUE = "#2F54EB";

function imageDims(file: File): Promise<{ w: number; h: number } | null> {
  return new Promise(resolve => {
    const url = URL.createObjectURL(file);
    const img = new window.Image();
    img.onload = () => { URL.revokeObjectURL(url); resolve({ w: img.naturalWidth, h: img.naturalHeight }); };
    img.onerror = () => { URL.revokeObjectURL(url); resolve(null); };
    img.src = url;
  });
}

const HANDLES: { h: Handle; style: React.CSSProperties; cursor: string }[] = [
  { h: "nw", style: { left: -5, top: -5 }, cursor: "nwse-resize" },
  { h: "n",  style: { left: "50%", top: -5, marginLeft: -5 }, cursor: "ns-resize" },
  { h: "ne", style: { right: -5, top: -5 }, cursor: "nesw-resize" },
  { h: "e",  style: { right: -5, top: "50%", marginTop: -5 }, cursor: "ew-resize" },
  { h: "se", style: { right: -5, bottom: -5 }, cursor: "nwse-resize" },
  { h: "s",  style: { left: "50%", bottom: -5, marginLeft: -5 }, cursor: "ns-resize" },
  { h: "sw", style: { left: -5, bottom: -5 }, cursor: "nesw-resize" },
  { h: "w",  style: { left: -5, top: "50%", marginTop: -5 }, cursor: "ew-resize" },
];

/** Draggable region box over the sheet. Move by the body, resize by the 8 handles. */
function Box({ r, sw, sh, n, active, pxPerUnit, onActive, onChange }: {
  r: EditableRegion; sw: number; sh: number; n: number; active: boolean; pxPerUnit: () => number;
  onActive: () => void; onChange: (b: [number, number, number, number]) => void;
}) {
  const drag = useRef<{ mode: "move" | Handle; x: number; y: number; start: [number, number, number, number] } | null>(null);
  const [x0, y0, x1, y1] = r.bbox;

  const down = (mode: "move" | Handle) => (e: RPointerEvent) => {
    e.stopPropagation();
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    drag.current = { mode, x: e.clientX, y: e.clientY, start: r.bbox };
    onActive();
  };
  const move = (e: RPointerEvent) => {
    const d = drag.current;
    if (!d) return;
    const k = pxPerUnit() || 1;
    const dx = (e.clientX - d.x) / k, dy = (e.clientY - d.y) / k;
    onChange(d.mode === "move" ? moveBox(d.start, dx, dy, sw, sh) : resizeBox(d.start, d.mode, dx, dy, sw, sh));
  };
  const up = () => { drag.current = null; };

  return (
    <div
      onPointerDown={down("move")} onPointerMove={move} onPointerUp={up} onPointerCancel={up}
      style={{
        position: "absolute", left: `${(x0 / sw) * 100}%`, top: `${(y0 / sh) * 100}%`,
        width: `${((x1 - x0) / sw) * 100}%`, height: `${((y1 - y0) / sh) * 100}%`,
        border: `2px solid ${BLUE}`, background: active ? "rgba(47,84,235,.16)" : "rgba(47,84,235,.07)",
        cursor: "move", touchAction: "none", boxSizing: "border-box", zIndex: active ? 2 : 1,
      }}
    >
      <span style={{ position: "absolute", top: -1, left: -1, background: BLUE, color: "#fff", fontSize: 11, fontWeight: 700, padding: "0 6px", borderRadius: "0 0 4px 0", pointerEvents: "none" }}>{n}</span>
      {HANDLES.map(({ h, style, cursor }) => (
        <span
          key={h} onPointerDown={down(h)} onPointerMove={move} onPointerUp={up} onPointerCancel={up}
          data-handle={h}
          style={{ position: "absolute", width: 10, height: 10, background: "#fff", border: `2px solid ${BLUE}`, borderRadius: 2, cursor, touchAction: "none", boxSizing: "border-box", ...style }}
        />
      ))}
    </div>
  );
}

/** In-page upload workflow (ADR-F34): Upload → Segment → Review decks. Replaces the old modal. */
function LiveUploadWorkspace({ projectId, hasDecks, onCancel, onAdded }: {
  projectId: string; hasDecks: boolean; onCancel?: () => void; onAdded: (images: ImageInfo[]) => void;
}) {
  const { t, i18n } = useTranslation();
  const lang = i18n.language.startsWith("zh") ? "zh" : "en";
  const qc = useQueryClient();
  const [s, dispatch] = useReducer(uploadReducer, UPLOAD_INITIAL);
  const [sheet, setSheet] = useState<{ src: string; w: number; h: number } | null>(null);
  const [saving, setSaving] = useState(false);
  const [activeId, setActiveId] = useState<string | null>(null);
  const planRef = useRef<string | null>(null);
  const canvasRef = useRef<HTMLDivElement>(null);

  useEffect(() => { planRef.current = s.plan?.plan_id ?? null; }, [s.plan]);
  // Leaving the page discards an unconfirmed plan so nothing is left on the server
  useEffect(() => () => { const id = planRef.current; if (id) void deletePlan(id).catch(() => undefined); }, []);

  const discard = async () => {
    const id = planRef.current;
    planRef.current = null;
    if (id) { try { await deletePlan(id); } catch { /* already gone */ } }
  };

  const cancel = async () => {
    await discard();
    dispatch({ type: "cancelClicked" });
    setSheet(null);
    onCancel?.();
  };

  const errText = (e: RuleError) => {
    const k = `upload.err.${e.message}`;
    return i18n.exists(k) ? t(k) : e.message;
  };

  const handleFile = async (file: File) => {
    let clientError = checkFileMeta(file.name, file.size);
    if (!clientError && !/\.pdf$/i.test(file.name)) {
      const dims = await imageDims(file);
      clientError = dims ? checkDims(dims.w, dims.h) : { rule: "U1", message: "unreadable" };
    }
    dispatch({ type: "fileChosen", clientError });
    if (clientError) return;
    try {
      const plan = await uploadPlan(projectId, file);
      dispatch({ type: "uploaded", plan });
      const seg = await segmentPlan(plan.plan_id);
      const img = await planSheet(plan.plan_id);
      setSheet({ src: img.data, w: seg.sheet_w, h: seg.sheet_h });
      dispatch({ type: "segmented", regions: seg.regions });
    } catch (e) {
      await discard();
      dispatch({ type: "uploadFailed", error: apiError(e) });
    }
  };

  const confirm = async (whole: boolean) => {
    if (!s.plan) return;
    setSaving(true);
    try {
      const res = await confirmPlan(s.plan.plan_id, whole ? [] : s.regions.map(r => ({ region_id: r.id, label: r.label.trim(), bbox: r.bbox })));
      dispatch({ type: "confirmSucceeded" });
      await qc.invalidateQueries({ queryKey: ["projects"] });
      const n = res.images.length;
      message.success(n === 1 ? t("upload.addedToast", { n }) : t("upload.addedManyToast", { n }));
      planRef.current = null;
      onAdded(res.images);
      dispatch({ type: "cancelClicked" });
      setSheet(null);
    } catch (e) {
      dispatch({ type: "confirmFailed", error: apiError(e) });
    } finally {
      setSaving(false);
    }
  };

  const ticked = s.u4 && s.u5;
  const stepNo = planStep(s, hasDecks);
  const processing = s.step === "UP_UPLOADING" || s.step === "UP_SEGMENTING";
  const showIdle = s.step === "UP_IDLE" || (s.step === "UP_ERROR" && !s.plan);
  const spec = (id: string) => UPLOAD_SPEC.find(r => r.id === id)!.text[lang];

  return (
    <div style={{ background: "#fff", border: `1px solid ${BORDER}`, borderRadius: 10, padding: "20px 22px", marginTop: 8, display: "flow-root" }}>
      <PlanStepper current={stepNo} />

      {s.error && (
        <Alert
          type="error" showIcon style={{ marginTop: 16 }}
          message={<span><Tag color="red" style={{ marginRight: 6 }}>{s.error.rule}</Tag>{errText(s.error)}</span>}
          action={s.step === "UP_ERROR" ? <Button size="small" onClick={() => dispatch({ type: "retry" })}>{t("upload.retry")}</Button> : undefined}
        />
      )}

      {showIdle && (
        <div style={{ display: "flex", gap: 24, marginTop: 20, flexWrap: "wrap" }}>
          <div style={{ flex: "1 1 340px", minWidth: 0 }}>
            {!hasDecks && (
              <>
                <div style={{ fontSize: 16, fontWeight: 600, color: "#111827" }}>{t("upload.emptyTitle")}</div>
                <div style={{ fontSize: 13, color: SUB, margin: "4px 0 14px" }}>{t("upload.emptyBody")}</div>
              </>
            )}
            <div style={{ display: "flex", flexDirection: "column", gap: 6, marginBottom: 12 }}>
              <Checkbox checked={s.u4} onChange={e => dispatch({ type: "toggleConfirm", which: "u4", value: e.target.checked })}>
                <span style={{ fontSize: 12.5 }}><b>U4</b> {spec("U4")}</span>
              </Checkbox>
              <Checkbox checked={s.u5} onChange={e => dispatch({ type: "toggleConfirm", which: "u5", value: e.target.checked })}>
                <span style={{ fontSize: 12.5 }}><b>U5</b> {spec("U5")}</span>
              </Checkbox>
            </div>
            <div className="plan-dropzone"><Upload.Dragger
              accept=".png,.jpg,.jpeg,.pdf" multiple={false} showUploadList={false} disabled={!ticked || s.step !== "UP_IDLE"}
              beforeUpload={file => { void handleFile(file); return false; }}
              >

              <p className="ant-upload-drag-icon"><InboxOutlined /></p>
              <p style={{ fontSize: 14, margin: 0 }}>{ticked ? t("upload.drop") : t("upload.dropDisabled")}</p>
              <p style={{ fontSize: 12, color: SUB, margin: "4px 0 0" }}>{t("upload.dropHint")}</p>
            </Upload.Dragger></div>
            {onCancel && <Button style={{ marginTop: 12 }} onClick={cancel}>{t("upload.cancel")}</Button>}
          </div>
          <div style={{ flex: "1 1 320px", minWidth: 0, borderLeft: `1px solid ${BORDER}`, paddingLeft: 24 }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: SUB, letterSpacing: ".06em", marginBottom: 6 }}>{t("upload.specTitle").toUpperCase()}</div>
            {UPLOAD_SPEC.map(r => (
              <div key={r.id} style={{ display: "flex", gap: 8, fontSize: 12.5, padding: "3px 0", color: "#374151" }}>
                <span style={{ width: 24, flexShrink: 0, fontWeight: 700, color: r.kind === "hard" ? "#15803d" : r.kind === "confirm" ? "#b45309" : SUB }}>{r.id}</span>
                <span><b>{r.label[lang]}</b> — {r.text[lang]}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {processing && (
        <div style={{ padding: "36px 0 var(--gutter)", maxWidth: 460, margin: "0 auto", textAlign: "center" }}>
          <Progress percent={s.step === "UP_UPLOADING" ? 35 : 80} status="active" showInfo={false} />
          <div style={{ marginTop: 14, color: "#374151", fontSize: 14, fontWeight: 600 }}>{s.step === "UP_UPLOADING" ? t("upload.uploading") : t("upload.segmenting")}</div>
          <div style={{ marginTop: 4, color: SUB, fontSize: 12.5 }}>{t("upload.why")}</div>
          {s.plan && <div style={{ marginTop: 6, color: SUB, fontSize: 12 }}>{s.plan.filename}</div>}
        </div>
      )}

      {s.step === "UP_REVIEW" && sheet && (
        <>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginTop: 18, gap: 8, flexWrap: "wrap" }}>
            <div>
              <div style={{ fontSize: 14, fontWeight: 600 }}>{s.regions.length === 1 ? t("upload.foundOne") : t("upload.foundMany", { n: s.regions.length })}</div>
              <div style={{ fontSize: 12, color: SUB, marginTop: 2 }}>{t("upload.reviewHint")} {t("upload.dragHint")}</div>
            </div>
            <Button size="small" icon={<PlusOutlined />} onClick={() => dispatch({ type: "regionAdded", sheetW: sheet.w, sheetH: sheet.h })}>{t("upload.addDeck")}</Button>
          </div>
          <div style={{ display: "flex", gap: 20, alignItems: "flex-start", marginTop: 12, flexWrap: "wrap" }}>
            <div
              ref={canvasRef} data-testid="seg-canvas" onPointerDown={() => setActiveId(null)}
              style={{ position: "relative", flex: "1 1 420px", maxWidth: 640, minWidth: 280, border: `1px solid ${BORDER}`, background: "#fff", userSelect: "none" }}
            >
              <img src={sheet.src} alt="" draggable={false} style={{ display: "block", width: "100%", height: "auto" }} />
              {s.regions.map((r, i) => (
                <Box
                  key={r.id} r={r} sw={sheet.w} sh={sheet.h} n={i + 1} active={activeId === r.id}
                  pxPerUnit={() => (canvasRef.current ? canvasRef.current.getBoundingClientRect().width / sheet.w : 1)}
                  onActive={() => setActiveId(r.id)}
                  onChange={bbox => dispatch({ type: "regionResized", id: r.id, bbox })}
                />
              ))}
            </div>
            <div style={{ flex: "1 1 280px", minWidth: 0, maxHeight: 460, overflowY: "auto" }}>
              {s.regions.length === 0 && <div style={{ fontSize: 13, color: SUB, padding: "12px 0" }}>{t("upload.noneLeft")}</div>}
              {s.regions.map((r, i) => (
                <div
                  key={r.id} onMouseEnter={() => setActiveId(r.id)}
                  style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 8px", borderBottom: `1px solid ${BORDER}`, background: activeId === r.id ? "#f5f8ff" : "transparent" }}
                >
                  <span style={{ width: 18, fontWeight: 700, color: BLUE, fontSize: 12 }}>{i + 1}</span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <Input
                      size="small" value={r.label} maxLength={60} placeholder={t("upload.namePh")}
                      status={r.label.trim() ? undefined : "error"}
                      onFocus={() => setActiveId(r.id)}
                      onChange={e => dispatch({ type: "regionRenamed", id: r.id, label: e.target.value })}
                    />
                    {r.confidence < 0.4 && <div style={{ fontSize: 11, color: "#b45309", marginTop: 2 }}>{t("upload.lowConfidence")}</div>}
                  </div>
                  <Button size="small" type="text" icon={<DeleteOutlined />} aria-label={t("upload.remove")} onClick={() => dispatch({ type: "regionRemoved", id: r.id })} />
                </div>
              ))}
            </div>
          </div>
          <div style={{ marginTop: 18, display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            <Button onClick={() => confirm(true)} disabled={saving}>{t("upload.whole")}</Button>
            <div style={{ display: "flex", gap: 8 }}>
              <Button onClick={cancel} disabled={saving}>{t("upload.cancel")}</Button>
              <Button type="primary" disabled={!canConfirm(s.regions)} loading={saving} onClick={() => confirm(false)}>
                {s.regions.length === 1 ? t("upload.confirmOne") : t("upload.confirmMany", { n: s.regions.length })}
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

/** Live build: the real workflow. Static demo build: an explanatory card instead (ADR-F36). */
export function UploadWorkspace(props: { projectId: string; hasDecks: boolean; onCancel?: () => void; onAdded: (images: ImageInfo[]) => void }) {
  if (IS_STATIC_DEMO) return <StaticNotice step={props.hasDecks ? 4 : 1} onBack={props.onCancel} />;
  return <LiveUploadWorkspace {...props} />;
}
