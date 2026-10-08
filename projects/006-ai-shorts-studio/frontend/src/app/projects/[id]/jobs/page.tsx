"use client";

import { useParams } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { formatCost, isJobActive, JOB_STATUS_LABELS, KIND_LABELS, totalCost, type Job } from "@/lib/generation";
import { confirmCost, useProjectMedia } from "@/lib/useProjectMedia";

export default function JobsPage() {
  const { id } = useParams<{ id: string }>();
  const projectId = Number(id);
  const { data, error, reload } = useProjectMedia(projectId);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  if (!data) {
    return <section className="card">{error ? <p className="error">{error}</p> : <p className="muted">불러오는 중…</p>}</section>;
  }

  const { scenes, jobs, assets, providers } = data;
  const sceneNumber = (sceneId: number | null) => scenes.find((s) => s.id === sceneId)?.scene_number;
  const actual = totalCost(assets.map((a) => ({ amount: a.cost_amount, currency: a.cost_currency })));
  const actualText = Object.keys(actual).length
    ? Object.entries(actual)
        .map(([cur, amt]) => formatCost(amt, cur))
        .join(", ")
    : "없음";
  const failed = jobs.filter((j) => j.status === "failed").length;
  const active = jobs.filter(isJobActive).length;

  async function retry(job: Job) {
    if (busyId) return;
    const { ok, confirmPaid } = confirmCost(providers, job.job_type);
    if (!ok) return;
    setBusyId(job.id);
    setActionError(null);
    try {
      await api.retryJob(job.id, confirmPaid);
      await reload();
    } catch (e) {
      setActionError((e as Error).message);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <section className="card">
      <h2>작업 상태</h2>
      <p className="muted">
        전체 {jobs.length}건 · 진행 중 {active} · 실패 {failed} · 실제 비용 합계 {actualText}
      </p>
      {(error || actionError) && <p className="error">{actionError ?? error}</p>}
      {jobs.length === 0 ? (
        <p className="muted">아직 작업이 없습니다. 검토 화면에서 장면 이미지나 영상을 생성하세요.</p>
      ) : (
        <div className="table-wrap">
          <table className="jobs">
            <thead>
              <tr>
                <th>#</th>
                <th>장면</th>
                <th>종류</th>
                <th>공급자</th>
                <th>상태</th>
                <th>시도</th>
                <th>예상 비용</th>
                <th>요청 시각</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {jobs.map((job) => (
                <tr key={job.id} data-testid={`job-${job.id}`}>
                  <td>{job.id}</td>
                  <td>{sceneNumber(job.scene_id) ?? "-"}</td>
                  <td>{KIND_LABELS[job.job_type] ?? job.job_type}</td>
                  <td>{job.provider}</td>
                  <td>
                    <span className={`status-badge job-${job.status}`}>{JOB_STATUS_LABELS[job.status]}</span>
                    {job.error_message && <div className="error small-err">{job.error_message}</div>}
                  </td>
                  <td>{job.attempts}</td>
                  <td>{formatCost(job.estimated_cost, job.cost_currency)}</td>
                  <td className="nowrap">{new Date(job.created_at).toLocaleString("ko-KR")}</td>
                  <td>
                    {job.status === "failed" && (
                      <button className="secondary" onClick={() => retry(job)} disabled={busyId !== null}>
                        재시도
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
