import { describe, expect, it } from "vitest";
import { EMPTY_FORM, validateProjectForm } from "./project";

describe("validateProjectForm", () => {
  it("accepts a valid form", () => {
    expect(validateProjectForm({ ...EMPTY_FORM, title: "고양이 쇼츠" })).toEqual({});
  });

  it("requires a title", () => {
    expect(validateProjectForm({ ...EMPTY_FORM, title: "   " }).title).toBeDefined();
  });

  it("checks duration range", () => {
    const base = { ...EMPTY_FORM, title: "x" };
    expect(validateProjectForm({ ...base, target_duration_sec: 4 }).target_duration_sec).toBeDefined();
    expect(validateProjectForm({ ...base, target_duration_sec: 181 }).target_duration_sec).toBeDefined();
    expect(validateProjectForm({ ...base, target_duration_sec: 12.5 }).target_duration_sec).toBeDefined();
    expect(validateProjectForm({ ...base, target_duration_sec: 180 })).toEqual({});
  });
});
