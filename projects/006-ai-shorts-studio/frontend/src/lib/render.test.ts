import { describe, expect, it } from "vitest";
import { formatTime, scenesNeedingAudio } from "./render";

describe("render helpers", () => {
  it("formats times", () => {
    expect(formatTime(0)).toBe("0:00");
    expect(formatTime(3.5)).toBe("0:03.5");
    expect(formatTime(61)).toBe("1:01");
    expect(formatTime(75.25)).toBe("1:15.3");
    expect(formatTime(6.033)).toBe("0:06");
    expect(formatTime(59.97)).toBe("1:00");
  });
  it("counts scenes needing audio", () => {
    expect(scenesNeedingAudio([{ audio: "ready" }, { audio: "none" }, { audio: "stale" }, { audio: "no_text" }])).toBe(2);
  });
});
