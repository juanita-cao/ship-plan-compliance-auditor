import { describe, expect, it } from "vitest";
import { moodOf } from "./mascot";

describe("moodOf", () => {
  it("FE-S08 maps pending count to mood", () => {
    expect(moodOf(0)).toBe("eating");
    expect(moodOf(1)).toBe("eating");
    expect(moodOf(2)).toBe("calm");
    expect(moodOf(4)).toBe("calm");
    expect(moodOf(5)).toBe("tired");
    expect(moodOf(30)).toBe("tired");
  });
});
