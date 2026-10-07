export type RvState = "RV_EDITING" | "RV_SIGNING" | "RV_DONE";

export type RvEvent =
  | { type: "edited" }
  | { type: "submitClicked"; pending: number; override: string | null; note: string }
  | { type: "cancelClicked" }
  | { type: "signSucceeded" }
  | { type: "signFailed" };

export interface RvResult {
  next: RvState;
  blocked?: "pending" | "note";
}

export function rvTransition(state: RvState, event: RvEvent): RvResult {
  if (state === "RV_EDITING") {
    if (event.type === "edited") return { next: "RV_EDITING" };
    if (event.type === "submitClicked") {
      if (event.pending > 0) return { next: "RV_EDITING", blocked: "pending" };
      if (event.override && !event.note.trim()) return { next: "RV_EDITING", blocked: "note" };
      return { next: "RV_SIGNING" };
    }
  }
  if (state === "RV_SIGNING") {
    if (event.type === "cancelClicked") return { next: "RV_EDITING" };
    if (event.type === "signSucceeded") return { next: "RV_DONE" };
    if (event.type === "signFailed") return { next: "RV_EDITING" };
  }
  throw new Error(`Unrecognised (state=${state}, event=${event.type})`);
}
