import { describe, expect, it } from "vitest";
import { isSceneFormDirty, moveItem, toSceneForm, totalDuration, validateSceneForm, type Scene } from "./scene";
import { countParagraphs, estimateReadSeconds } from "./project";

const scene: Scene = {
  id: 1,
  project_id: 1,
  scene_number: 1,
  dialogue: "안녕",
  visual_description: "",
  image_prompt: "",
  video_prompt: "",
  duration_sec: 3,
  status: "draft",
  rejection_reason: null,
  approved_at: null,
  created_at: "",
  updated_at: "",
};

describe("moveItem", () => {
  it("swaps with neighbour", () => {
    expect(moveItem([1, 2, 3], 0, 1)).toEqual([2, 1, 3]);
    expect(moveItem([1, 2, 3], 2, -1)).toEqual([1, 3, 2]);
  });
  it("ignores moves past the ends", () => {
    const items = [1, 2, 3];
    expect(moveItem(items, 0, -1)).toBe(items);
    expect(moveItem(items, 2, 1)).toBe(items);
  });
});

describe("scene form", () => {
  it("detects edits", () => {
    expect(isSceneFormDirty(toSceneForm(scene), scene)).toBe(false);
    expect(isSceneFormDirty({ ...toSceneForm(scene), duration_sec: 4 }, scene)).toBe(true);
  });
  it("validates duration", () => {
    expect(validateSceneForm(toSceneForm(scene))).toEqual({});
    expect(validateSceneForm({ ...toSceneForm(scene), duration_sec: 0.1 }).duration_sec).toBeDefined();
    expect(validateSceneForm({ ...toSceneForm(scene), duration_sec: NaN }).duration_sec).toBeDefined();
  });
});

describe("helpers", () => {
  it("sums durations without float noise", () => {
    expect(totalDuration([{ duration_sec: 0.1 }, { duration_sec: 0.2 }])).toBe(0.3);
  });
  it("counts paragraphs like the backend", () => {
    expect(countParagraphs("a\n\n\nb\r\n\r\nc\n  \n")).toBe(3);
    expect(countParagraphs("한 줄\n다음 줄")).toBe(1);
    expect(countParagraphs("  ")).toBe(0);
  });
  it("estimates read time", () => {
    expect(estimateReadSeconds("가".repeat(70))).toBe(10);
    expect(estimateReadSeconds("   ")).toBe(0);
  });
});
