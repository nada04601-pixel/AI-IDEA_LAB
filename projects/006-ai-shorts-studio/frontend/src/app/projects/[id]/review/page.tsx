"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { latestJob, summarizeReview, type Job, type MediaKind } from "@/lib/generation";
import type { Scene } from "@/lib/scene";
import { confirmCost, useProjectMedia } from "@/lib/useProjectMedia";
import SceneReviewCard from "./SceneReviewCard";

export default function ReviewPage() {
  const { id } = useParams<{ id: string }>();
  const projectId = Number(id);
  const { data, error, reload } = useProjectMedia(projectId);

  if (!data) {
    return <section className="card">{error ? <p className="error">{error}</p> : <p className="muted">불러오는 중…</p>}</section>;
  }

  const { project, scenes, jobs, assets, providers } = data;
  const summary = summarizeReview(scenes);
  const paid = providers.filter((p) => p.kind !== "script" && p.is_paid);

  async function onGenerate(scene: Scene, kind: MediaKind) {
    const { ok, confirmPaid } = confirmCost(providers, kind);
    if (!ok) return;
    await api.generateMedia(scene.id, kind, confirmPaid);
    await reload();
  }

  async function onRetry(job: Job) {
    const { ok, confirmPaid } = confirmCost(providers, job.job_type);
    if (!ok) return;
    await api.retryJob(job.id, confirmPaid);
    await reload();
  }

  return (
    <div className="storyboard">
      <section className="card">
        <h2>장면 검토</h2>
        <p className="muted">
          {project.title} · 승인 {summary.approved}/{summary.total}
          {summary.reviewRequired > 0 && ` · 검토 필요 ${summary.reviewRequired}`}
          {summary.active > 0 && ` · 생성 중 ${summary.active}`}
          {summary.rejected > 0 && ` · 반려 ${summary.rejected}`}
          {summary.failed > 0 && ` · 실패 ${summary.failed}`}
          {summary.notStarted > 0 && ` · 미생성 ${summary.notStarted}`}
        </p>
        <div className="progress" aria-label="승인 진행률">
          <div style={{ width: `${summary.total ? (summary.approved / summary.total) * 100 : 0}%` }} />
        </div>
        <p className="muted small">
          공급자:{" "}
          {providers
            .filter((p) => p.kind !== "script")
            .map((p) => `${p.kind === "image" ? "이미지" : "영상"} ${p.name}${p.is_paid ? " (유료)" : " (무료)"}`)
            .join(" · ")}
          {paid.length === 0 && " — 외부 AI를 호출하지 않으며 비용이 들지 않습니다."}
        </p>
        {summary.total > 0 && summary.approved === summary.total && <p className="ok">모든 장면이 승인되었습니다. 다음 단계(음성·자막·렌더링)로 넘어갈 수 있습니다.</p>}
        {error && <p className="error">{error}</p>}
        {scenes.length === 0 && (
          <p className="muted">
            장면이 없습니다. <Link href={`/projects/${projectId}/storyboard`}>스토리보드</Link>에서 먼저 장면을 만드세요.
          </p>
        )}
      </section>

      <ol className="scenes">
        {scenes.map((scene) => (
          <SceneReviewCard
            key={scene.id}
            scene={scene}
            aspectRatio={project.aspect_ratio}
            assets={assets}
            latestJob={latestJob(jobs, scene.id)}
            onGenerate={onGenerate}
            onRetry={onRetry}
            onChanged={reload}
          />
        ))}
      </ol>
    </div>
  );
}
