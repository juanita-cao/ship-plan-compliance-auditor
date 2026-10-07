import { describe, expect, it } from "vitest";
import { rvTransition } from "./reviewPanelState";

describe("rvTransition", () => {
  it("RV-S01 blocks submit while instances are pending", () => {
    expect(rvTransition("RV_EDITING", { type: "submitClicked", pending: 2, override: null, note: "" }))
      .toEqual({ next: "RV_EDITING", blocked: "pending" });
  });
  it("RV-S02 opens sign-off when everything is reviewed", () => {
    expect(rvTransition("RV_EDITING", { type: "submitClicked", pending: 0, override: null, note: "" }).next).toBe("RV_SIGNING");
  });
  it("RV-S03 override requires a note", () => {
    expect(rvTransition("RV_EDITING", { type: "submitClicked", pending: 0, override: "NO_GO", note: "  " }))
      .toEqual({ next: "RV_EDITING", blocked: "note" });
    expect(rvTransition("RV_EDITING", { type: "submitClicked", pending: 0, override: "NO_GO", note: "why" }).next).toBe("RV_SIGNING");
  });
  it("RV-S04 sign success finishes, RV-S11 failure returns to editing", () => {
    expect(rvTransition("RV_SIGNING", { type: "signSucceeded" }).next).toBe("RV_DONE");
    expect(rvTransition("RV_SIGNING", { type: "signFailed" }).next).toBe("RV_EDITING");
  });
  it("RV-S12 cancel returns to editing", () => {
    expect(rvTransition("RV_SIGNING", { type: "cancelClicked" }).next).toBe("RV_EDITING");
  });
  it("RV-S05 a finished review cannot be edited or re-submitted", () => {
    expect(() => rvTransition("RV_DONE", { type: "edited" })).toThrow();
    expect(() => rvTransition("RV_DONE", { type: "submitClicked", pending: 0, override: null, note: "" })).toThrow();
  });
  it("unknown combinations hard fail", () => {
    expect(() => rvTransition("RV_EDITING", { type: "signSucceeded" })).toThrow();
  });
});
