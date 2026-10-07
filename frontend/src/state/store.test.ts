import { describe, it, expect } from "vitest";
import { appReducer, INITIAL_STATE, type AppState } from "./store";
import type { DetectResult } from "../api/client";

const mockResult: DetectResult = {
  session_id: "test-123",
  project_id: "demo_ship_a",
  image_stem: "a_deck",
  instances: [],
  total_by_category: { extinguisher_CO2_5kg: 1 },
  compliance_result: null,
  raw_response: null,
};

const withImage: AppState = { ...INITIAL_STATE, imageStem: "a_deck" };
const inResults: AppState = { ...INITIAL_STATE, stage: "RESULTS", imageStem: "a_deck", detectResult: mockResult };

// ─── FE-S01 ──────────────────────────────────────────────────────────────────
it("FE-S01: analyzeClicked with imageStem → RUNNING", () => {
  const s = appReducer(withImage, { type: "analyzeClicked" });
  expect(s.stage).toBe("RUNNING");
  expect(s.lastError).toBeNull();
});

// ─── FE-S02 ──────────────────────────────────────────────────────────────────
it("FE-S02: analyzeClicked without imageStem → stays IDLE", () => {
  const s = appReducer(INITIAL_STATE, { type: "analyzeClicked" });
  expect(s.stage).toBe("IDLE");
});

// ─── FE-S03 ──────────────────────────────────────────────────────────────────
it("FE-S03: detectComplete → RESULTS with result, selections cleared", () => {
  const running: AppState = { ...withImage, stage: "RUNNING" };
  const s = appReducer(running, { type: "detectComplete", result: mockResult });
  expect(s.stage).toBe("RESULTS");
  expect(s.detectResult).toBe(mockResult);
  expect(s.selectedCategory).toBeNull();
  expect(s.selectedInstanceId).toBeNull();
});

// ─── FE-S04 ──────────────────────────────────────────────────────────────────
it("FE-S04: detectError → IDLE with error message", () => {
  const running: AppState = { ...withImage, stage: "RUNNING" };
  const s = appReducer(running, { type: "detectError", message: "timeout" });
  expect(s.stage).toBe("IDLE");
  expect(s.lastError).toBe("timeout");
  expect(s.detectResult).toBeNull();
});

// ─── FE-S05 ──────────────────────────────────────────────────────────────────
it("FE-S05: categoryClicked → selectedCategory set, instanceId cleared", () => {
  const s = appReducer(inResults, { type: "categoryClicked", category: "extinguisher_CO2_5kg" });
  expect(s.selectedCategory).toBe("extinguisher_CO2_5kg");
  expect(s.selectedInstanceId).toBeNull();
});

// ─── FE-S06 ──────────────────────────────────────────────────────────────────
it("FE-S06: showAllClicked → both selection fields null", () => {
  const s1 = appReducer(inResults, { type: "categoryClicked", category: "extinguisher_CO2_5kg" });
  const s2 = appReducer(s1, { type: "showAllClicked" });
  expect(s2.selectedCategory).toBeNull();
  expect(s2.selectedInstanceId).toBeNull();
});

// ─── FE-S07 ──────────────────────────────────────────────────────────────────
it("FE-S07: unknown action → throws", () => {
  expect(() => appReducer(INITIAL_STATE, { type: "UNKNOWN" } as never)).toThrow();
});

// ─── projectChanged clears image and result ───────────────────────────────────
it("projectChanged clears imageStem and detectResult", () => {
  const s = appReducer(inResults, { type: "projectChanged", projectId: "demo_ship_b" });
  expect(s.projectId).toBe("demo_ship_b");
  expect(s.imageStem).toBeNull();
  expect(s.detectResult).toBeNull();
});
