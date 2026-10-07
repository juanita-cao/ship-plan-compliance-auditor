import type { VesselFleetEntry, VesselStatus } from "../config";
import { getHistory, getPendingQueue } from "../state/reviewStore";

/** Latest signed verdict for a vessel (by history key), or null. */
export function latestVerdict(key: string): string | null {
  const latest = getHistory().filter(h => h.projectId === key).sort((a, b) => b.submittedAt.localeCompare(a.submittedAt))[0];
  return latest?.verdict ?? null;
}

export function pendingCount(key: string): number {
  return getPendingQueue().filter(e => e.projectId === key).length;
}

/** The one status rule used by Vessel Overview and the Ask page (ADR-F28/F33). */
export function vesselStatus(entry: VesselFleetEntry): VesselStatus {
  const verdict = latestVerdict(entry.historyKey) ?? entry.complianceMock;
  return pendingCount(entry.historyKey) > 0 ? "to_review"
    : entry.status === "scheduled" ? "scheduled"
    : verdict === "NO_GO" ? "action_required"
    : verdict === "CONDITIONAL" ? "pending_confirm"
    : "up_to_date";
}
