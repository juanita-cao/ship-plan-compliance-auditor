export type Mood = "tired" | "calm" | "eating";

export function moodOf(pending: number): Mood {
  if (pending >= 5) return "tired";
  if (pending >= 2) return "calm";
  return "eating";
}
