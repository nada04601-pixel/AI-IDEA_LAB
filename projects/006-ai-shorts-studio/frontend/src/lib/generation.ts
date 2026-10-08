import type { Scene } from "./scene";

export type MediaKind = "image" | "video";

export interface Job {
  id: number;
  project_id: number;
  scene_id: number | null;
  job_type: string;
  status: "queued" | "running" | "succeeded" | "failed";
  progress: number;
  provider: string;
  prompt: string;
  estimated_cost: number | null;
  cost_currency: string | null;
  attempts: number;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  finished_at: string | null;
}

export interface Asset {
  id: number;
  project_id: number;
  scene_id: number | null;
  job_id: number | null;
  asset_type: string;
  version: number;
  provider: string | null;
  status: string;
  cost_amount: number | null;
  cost_currency: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
  url: string;
}

export interface ProviderInfo {
  kind: string;
  name: string;
  is_paid: boolean;
  estimated_cost_per_job: number;
  currency: string;
}

export const JOB_STATUS_LABELS: Record<Job["status"], string> = {
  queued: "대기",
  running: "실행 중",
  succeeded: "성공",
  failed: "실패",
};

export const KIND_LABELS: Record<string, string> = { image: "이미지", video: "영상", audio: "음성", render: "렌더링" };

export const ACTIVE_SCENE_STATUSES = ["queued", "generating"];

export function isJobActive(job: Pick<Job, "status">): boolean {
  return job.status === "queued" || job.status === "running";
}

/** 장면의 해당 종류 자산을 버전 내림차순으로 돌려준다. */
export function sceneAssets(assets: Asset[], sceneId: number, kind: MediaKind): Asset[] {
  return assets.filter((a) => a.scene_id === sceneId && a.asset_type === kind).sort((a, b) => b.version - a.version);
}

/** 장면의 가장 최근 작업. */
export function latestJob(jobs: Job[], sceneId: number): Job | undefined {
  return jobs.filter((j) => j.scene_id === sceneId).sort((a, b) => b.id - a.id)[0];
}

export interface ReviewSummary {
  total: number;
  approved: number;
  reviewRequired: number;
  rejected: number;
  failed: number;
  active: number;
  notStarted: number;
}

export function summarizeReview(scenes: Pick<Scene, "status">[]): ReviewSummary {
  const count = (...statuses: string[]) => scenes.filter((s) => statuses.includes(s.status)).length;
  return {
    total: scenes.length,
    approved: count("approved"),
    reviewRequired: count("review_required"),
    rejected: count("rejected"),
    failed: count("failed"),
    active: count(...ACTIVE_SCENE_STATUSES),
    notStarted: count("draft"),
  };
}

export function formatCost(amount: number | null | undefined, currency: string | null | undefined): string {
  if (amount == null) return "-";
  if (amount === 0) return "무료";
  return `${amount.toFixed(amount < 0.1 ? 3 : 2)} ${currency ?? ""}`.trim();
}

/** 통화별 합계. 예: { USD: 0.12 } */
export function totalCost(items: { amount: number | null; currency: string | null }[]): Record<string, number> {
  const totals: Record<string, number> = {};
  for (const { amount, currency } of items) {
    if (amount == null || !currency) continue;
    totals[currency] = Math.round(((totals[currency] ?? 0) + amount) * 10000) / 10000;
  }
  return totals;
}
