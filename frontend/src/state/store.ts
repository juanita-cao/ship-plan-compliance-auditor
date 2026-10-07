import { createContext, useContext, useReducer, type Dispatch } from "react";
import type { DetectResult } from "../api/client";

// ─── State ────────────────────────────────────────────────────────────────────

export type Stage = "IDLE" | "RUNNING" | "RESULTS";

export interface AppState {
  stage: Stage;
  projectId: string;
  imageStem: string | null;
  detectResult: DetectResult | null;
  selectedCategory: string | null;
  selectedInstanceId: string | null;
  lastError: string | null;
}

export const INITIAL_STATE: AppState = {
  stage: "IDLE",
  projectId: "demo_ship_a",
  imageStem: null,
  detectResult: null,
  selectedCategory: null,
  selectedInstanceId: null,
  lastError: null,
};

// ─── Actions ──────────────────────────────────────────────────────────────────

export type AppAction =
  | { type: "analyzeClicked" }
  | { type: "projectChanged"; projectId: string }
  | { type: "imageChanged"; imageStem: string }
  | { type: "detectComplete"; result: DetectResult }
  | { type: "detectError"; message: string }
  | { type: "newAnalysisClicked" }
  | { type: "categoryClicked"; category: string }
  | { type: "instanceClicked"; instanceId: string }
  | { type: "showAllClicked" };

// ─── Reducer ──────────────────────────────────────────────────────────────────

export function appReducer(state: AppState, action: AppAction): AppState {
  switch (action.type) {
    case "analyzeClicked":
      if (state.imageStem === null) return state;
      return { ...state, stage: "RUNNING", lastError: null };

    case "projectChanged":
      return { ...state, projectId: action.projectId, imageStem: null, detectResult: null, selectedCategory: null, selectedInstanceId: null };

    case "imageChanged":
      return { ...state, imageStem: action.imageStem };

    case "detectComplete":
      return { ...state, stage: "RESULTS", detectResult: action.result, selectedCategory: null, selectedInstanceId: null, lastError: null };

    case "detectError":
      return { ...state, stage: "IDLE", lastError: action.message, detectResult: null };

    case "newAnalysisClicked":
      return { ...state, stage: "IDLE", detectResult: null, selectedCategory: null, selectedInstanceId: null, lastError: null };

    case "categoryClicked":
      return { ...state, selectedCategory: action.category, selectedInstanceId: null };

    case "instanceClicked":
      return { ...state, selectedInstanceId: action.instanceId, selectedCategory: null };

    case "showAllClicked":
      return { ...state, selectedCategory: null, selectedInstanceId: null };

    default:
      throw new Error(`Unknown action: ${(action as AppAction).type}`);
  }
}

// ─── Context ──────────────────────────────────────────────────────────────────

export const AppStateContext = createContext<AppState>(INITIAL_STATE);
export const AppDispatchContext = createContext<Dispatch<AppAction>>(() => {});

export function useAppState() { return useContext(AppStateContext); }
export function useAppDispatch() { return useContext(AppDispatchContext); }

export function useAppStore(): [AppState, Dispatch<AppAction>] {
  return useReducer(appReducer, INITIAL_STATE);
}
