import { describe, expect, it } from "vitest";
import { safeName, staticPath } from "./staticAdapter";

describe("staticPath", () => {
  it("ST-S01 projects and images", () => {
    expect(staticPath("get", "/projects")).toBe("projects.json");
    expect(staticPath("get", "/image/demo_ship_a/a_deck")).toBe("image/demo_ship_a/a_deck.json");
  });
  it("ST-S02 detect reads the JSON body (string or object)", () => {
    expect(staticPath("post", "/detect", { project_id: "demo_ship_b", image_stem: "below_main_deck_bow" })).toBe("detect/demo_ship_b/below_main_deck_bow.json");
    expect(staticPath("post", "/detect", JSON.stringify({ project_id: "demo_ship_a", image_stem: "a_deck" }))).toBe("detect/demo_ship_a/a_deck.json");
    expect(staticPath("post", "/detect", "not json")).toBeNull();
  });
  it("ST-S03 spotlight: none / category / instance", () => {
    const b = "spotlight/demo_ship_a/a_deck";
    expect(staticPath("get", "/spotlight/demo_ship_a/a_deck")).toBe(`${b}/all.json`);
    expect(staticPath("get", "/spotlight/demo_ship_a/a_deck?category=extinguisher_CO2_5kg")).toBe(`${b}/cat-extinguisher_CO2_5kg.json`);
    expect(staticPath("get", "/spotlight/demo_ship_a/a_deck?instance_id=instance_3")).toBe(`${b}/inst-instance_3.json`);
  });
  it("ST-S04 a selected instance wins over the category, as in the live renderer", () => {
    expect(staticPath("get", "/spotlight/demo_ship_a/a_deck?category=extinguisher_foam_9L&instance_id=instance_1")).toBe("spotlight/demo_ship_a/a_deck/inst-instance_1.json");
  });
  it("ST-S05 anything else has no exported file", () => {
    expect(staticPath("get", "/nope")).toBeNull();
    expect(staticPath("post", "/projects/x/plans")).toBeNull();
    expect(staticPath("get", "/api/projects")).toBe("projects.json");
  });
  it("ST-S06 file names are sanitised the same way as the export script", () => {
    expect(safeName("a b/../c")).toBe("a_b_.._c");
    expect(safeName("instance_1")).toBe("instance_1");
  });
});
