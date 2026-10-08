import { describe, expect, it } from "vitest";
import { filterJobs, formatCost, jobSeconds, latestJob, sceneAssets, summarizeReview, totalCost, type Asset, type Job } from "./generation";

const asset = (id: number, scene_id: number, asset_type: string, version: number) =>
  ({ id, scene_id, asset_type, version }) as Asset;
const job = (id: number, scene_id: number) => ({ id, scene_id }) as Job;

describe("generation helpers", () => {
  it("picks scene assets newest first", () => {
    const list = [asset(1, 1, "image", 1), asset(2, 1, "image", 2), asset(3, 2, "image", 1), asset(4, 1, "video", 1)];
    expect(sceneAssets(list, 1, "image").map((a) => a.id)).toEqual([2, 1]);
    expect(sceneAssets(list, 1, "video").map((a) => a.id)).toEqual([4]);
  });

  it("finds the latest job of a scene", () => {
    expect(latestJob([job(1, 1), job(3, 1), job(2, 2)], 1)?.id).toBe(3);
    expect(latestJob([], 1)).toBeUndefined();
  });

  it("summarizes scene statuses", () => {
    const s = summarizeReview(["approved", "approved", "review_required", "failed", "queued", "generating", "draft", "rejected"].map((status) => ({ status })));
    expect(s).toEqual({ total: 8, approved: 2, reviewRequired: 1, rejected: 1, failed: 1, active: 2, notStarted: 1 });
  });

  it("formats and totals costs", () => {
    expect(formatCost(0, "USD")).toBe("무료");
    expect(formatCost(null, "USD")).toBe("-");
    expect(formatCost(0.04, "USD")).toBe("0.040 USD");
    expect(formatCost(1.5, "USD")).toBe("1.50 USD");
    expect(totalCost([{ amount: 0.1, currency: "USD" }, { amount: 0.2, currency: "USD" }, { amount: null, currency: "USD" }])).toEqual({ USD: 0.3 });
  });
});

describe("job list helpers", () => {
  const jobs = [
    { id: 1, job_type: "image", status: "failed" },
    { id: 2, job_type: "video", status: "running" },
    { id: 3, job_type: "image", status: "succeeded" },
    { id: 4, job_type: "audio", status: "queued" },
  ] as Job[];

  it("filters by status and kind", () => {
    expect(filterJobs(jobs, "all", "all").map((j) => j.id)).toEqual([1, 2, 3, 4]);
    expect(filterJobs(jobs, "active", "all").map((j) => j.id)).toEqual([2, 4]);
    expect(filterJobs(jobs, "failed", "all").map((j) => j.id)).toEqual([1]);
    expect(filterJobs(jobs, "all", "image").map((j) => j.id)).toEqual([1, 3]);
    expect(filterJobs(jobs, "succeeded", "video")).toEqual([]);
  });

  it("measures job time", () => {
    expect(jobSeconds({ created_at: "2026-10-08T00:00:00Z", finished_at: "2026-10-08T00:00:02.340Z" })).toBe(2.3);
    expect(jobSeconds({ created_at: "2026-10-08T00:00:00Z", finished_at: null })).toBeNull();
  });
});
