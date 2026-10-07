import { describe, expect, it } from "vitest";
import { UPLOAD_LIMITS } from "../config";
import { UPLOAD_INITIAL, canConfirm, checkDims, checkFileMeta, clampBox, moveBox, planStep, resizeBox, uploadReducer, type UploadState } from "./uploadState";

const plan = { plan_id: "p", project_id: "x", filename: "a.png", kind: "png", width: 3000, height: 2000, size_bytes: 1, pages: 1 };
const region = (id: string) => ({ id, label: `Deck ${id}`, bbox: [0, 0, 10, 10] as [number, number, number, number], confidence: 1 });
const ticked: UploadState = { ...UPLOAD_INITIAL, u4: true, u5: true };

describe("client checks", () => {
  it("UP-S02 rejects unsupported formats", () => {
    expect(checkFileMeta("ship.dwg", 10)?.rule).toBe("U1");
    expect(checkFileMeta("plan.PNG", 10)).toBeNull();
    expect(checkFileMeta("plan.pdf", 10)).toBeNull();
  });
  it("UP-S03 enforces per-type size limits", () => {
    expect(checkFileMeta("a.png", UPLOAD_LIMITS.imageBytes + 1)?.rule).toBe("U2");
    expect(checkFileMeta("a.pdf", UPLOAD_LIMITS.imageBytes + 1)).toBeNull();
    expect(checkFileMeta("a.pdf", UPLOAD_LIMITS.pdfBytes + 1)?.rule).toBe("U2");
  });
  it("UP-S04 enforces resolution", () => {
    expect(checkDims(1200, 1000)?.rule).toBe("U3");
    expect(checkDims(3000, 2000)).toBeNull();
    expect(checkDims(13000, 100)?.rule).toBe("U3");
  });
});

describe("uploadReducer", () => {
  it("UP-S05 a file is ignored until both confirmations are ticked", () => {
    expect(() => uploadReducer(UPLOAD_INITIAL, { type: "fileChosen", clientError: null })).toThrow();
    const one = uploadReducer(UPLOAD_INITIAL, { type: "toggleConfirm", which: "u4", value: true });
    expect(() => uploadReducer(one, { type: "fileChosen", clientError: null })).toThrow();
  });
  it("happy path: idle → uploading → segmenting → review → done", () => {
    let s = uploadReducer(ticked, { type: "fileChosen", clientError: null });
    expect(s.step).toBe("UP_UPLOADING");
    s = uploadReducer(s, { type: "uploaded", plan });
    expect(s.step).toBe("UP_SEGMENTING");
    s = uploadReducer(s, { type: "segmented", regions: [region("r1"), region("r2")].map(r => ({ ...r })) });
    expect(s.step).toBe("UP_REVIEW");
    expect(s.regions).toHaveLength(2);
    s = uploadReducer(s, { type: "confirmSucceeded" });
    expect(s.step).toBe("UP_DONE");
  });
  it("client check failure goes to error and retry returns to idle", () => {
    let s = uploadReducer(ticked, { type: "fileChosen", clientError: { rule: "U1", message: "x" } });
    expect(s.step).toBe("UP_ERROR");
    s = uploadReducer(s, { type: "retry" });
    expect(s.step).toBe("UP_IDLE");
  });
  it("server failure after upload returns to error; retry without a plan goes to idle", () => {
    const up = uploadReducer(uploadReducer(ticked, { type: "fileChosen", clientError: null }), { type: "uploadFailed", error: { rule: "U2", message: "big" } });
    expect(up.step).toBe("UP_ERROR");
    expect(uploadReducer(up, { type: "retry" }).step).toBe("UP_IDLE");
  });
  it("UP-S08 rename and remove regions", () => {
    let s: UploadState = { ...ticked, step: "UP_REVIEW", plan, regions: [region("r1"), region("r2"), region("r3")] };
    s = uploadReducer(s, { type: "regionRenamed", id: "r1", label: "Main Deck" });
    s = uploadReducer(s, { type: "regionRemoved", id: "r2" });
    expect(s.regions.map(r => r.label)).toEqual(["Main Deck", "Deck r3"]);
  });
  it("UP-S09 confirm needs at least one region with a name", () => {
    expect(canConfirm([])).toBe(false);
    expect(canConfirm([{ ...region("r1"), label: "  " }])).toBe(false);
    expect(canConfirm([region("r1")])).toBe(true);
  });
  it("UP-S12 cancel resets from any state", () => {
    const mid: UploadState = { ...ticked, step: "UP_SEGMENTING", plan };
    expect(uploadReducer(mid, { type: "cancelClicked" })).toEqual(UPLOAD_INITIAL);
  });
  it("unknown (state,event) hard fails", () => {
    expect(() => uploadReducer(UPLOAD_INITIAL, { type: "segmented", regions: [] })).toThrow();
    expect(() => uploadReducer({ ...UPLOAD_INITIAL, step: "UP_DONE" }, { type: "retry" })).toThrow();
  });
});

describe("stepper + drag maths (ADR-F34)", () => {
  const at = (step: UploadState["step"], withPlan = false): UploadState => ({ ...ticked, step, plan: withPlan ? plan : null });
  it("SP-S01 closed workspace: no decks = step 1, decks = step 4", () => {
    expect(planStep(null, false)).toBe(1);
    expect(planStep(null, true)).toBe(4);
  });
  it("SP-S02 idle = 1, processing = 2, review = 3, done = 4", () => {
    expect(planStep(at("UP_IDLE"), false)).toBe(1);
    expect(planStep(at("UP_UPLOADING", true), false)).toBe(2);
    expect(planStep(at("UP_SEGMENTING", true), false)).toBe(2);
    expect(planStep(at("UP_REVIEW", true), false)).toBe(3);
    expect(planStep(at("UP_DONE", true), true)).toBe(4);
  });
  it("SP-S03 an error stays on the step where it happened", () => {
    expect(planStep(at("UP_ERROR"), false)).toBe(1);
    expect(planStep(at("UP_ERROR", true), false)).toBe(2);
  });
  it("SP-S04 resize and add regions in review only", () => {
    let s = uploadReducer(at("UP_SEGMENTING", true), { type: "segmented", regions: [{ ...region("r1") }] });
    s = uploadReducer(s, { type: "regionResized", id: "r1", bbox: [5, 5, 500, 500] });
    expect(s.regions[0].bbox).toEqual([5, 5, 500, 500]);
    s = uploadReducer(s, { type: "regionAdded", sheetW: 3000, sheetH: 2000 });
    expect(s.regions).toHaveLength(2);
    expect(s.regions[1].label).toBe("Deck 2");
    expect(() => uploadReducer(UPLOAD_INITIAL, { type: "regionAdded", sheetW: 1, sheetH: 1 })).toThrow();
  });
  it("SP-S05 clampBox keeps the box inside the sheet and above the minimum size", () => {
    expect(clampBox([-20, -20, 40, 40], 3000, 2000)).toEqual([0, 0, 100, 100]);
    expect(clampBox([2900, 1900, 4000, 3000], 3000, 2000)).toEqual([2900, 1900, 3000, 2000]);
  });
  it("SP-S06 moveBox keeps size and stays on the sheet", () => {
    expect(moveBox([100, 100, 400, 300], 5000, 5000, 3000, 2000)).toEqual([2700, 1800, 3000, 2000]);
    expect(moveBox([100, 100, 400, 300], -500, -500, 3000, 2000)).toEqual([0, 0, 300, 200]);
  });
  it("SP-S07 resizeBox moves only the dragged edges and keeps the minimum size", () => {
    expect(resizeBox([100, 100, 500, 400], "e", 50, 999, 3000, 2000)).toEqual([100, 100, 550, 400]);
    expect(resizeBox([100, 100, 500, 400], "nw", 20, 30, 3000, 2000)).toEqual([120, 130, 500, 400]);
    expect(resizeBox([100, 100, 500, 400], "w", 900, 0, 3000, 2000)).toEqual([400, 100, 500, 400]);
    expect(resizeBox([100, 100, 500, 400], "se", 9000, 9000, 3000, 2000)).toEqual([100, 100, 3000, 2000]);
  });
});
