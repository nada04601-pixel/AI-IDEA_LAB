import { afterEach, describe, expect, it, vi } from "vitest";
import { confirmLeave, hasUnsavedChanges } from "./useUnsavedWarning";

describe("confirmLeave", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("allows leaving when nothing is dirty", () => {
    const confirm = vi.fn(() => false);
    vi.stubGlobal("window", { confirm });
    expect(hasUnsavedChanges()).toBe(false);
    expect(confirmLeave()).toBe(true);
    expect(confirm).not.toHaveBeenCalled();
  });
});
