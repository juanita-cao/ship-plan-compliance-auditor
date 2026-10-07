import { describe, expect, it } from "vitest";
import { en } from "./en";
import { zh } from "./zh";
import { enUi } from "./en.ui";
import { zhUi } from "./zh.ui";

function keys(o: unknown, prefix = ""): string[] {
  if (o === null || typeof o !== "object") return [prefix];
  return Object.entries(o as Record<string, unknown>).flatMap(([k, v]) => keys(v, prefix ? `${prefix}.${k}` : k));
}

describe("i18n parity", () => {
  it("IJ-S07 en and zh have identical key sets", () => {
    expect(keys({ ...zh, ...zhUi }).sort()).toEqual(keys({ ...en, ...enUi }).sort());
  });
  it("no empty strings", () => {
    const flat = (o: object): string[] => Object.values(o).flatMap(v => (typeof v === "object" ? flat(v as object) : [String(v)]));
    for (const s of [...flat(enUi), ...flat(zhUi)]) expect(s.trim().length).toBeGreaterThan(0);
  });
});
