"use client";

import { useState } from "react";
import { api, apiUrl } from "@/lib/api";
import { ACTIVE_SCENE_STATUSES, KIND_LABELS, sceneAssets, type Asset, type Job, type MediaKind } from "@/lib/generation";
import { SCENE_STATUS_LABELS, type Scene } from "@/lib/scene";

interface Props {
  scene: Scene;
  aspectRatio: string;
  assets: Asset[];
  latestJob: Job | undefined;
  onGenerate: (scene: Scene, kind: MediaKind) => Promise<void>;
  onRetry: (job: Job) => Promise<void>;
  onChanged: () => Promise<void>;
}

export default function SceneReviewCard({ scene, aspectRatio, assets, latestJob, onGenerate, onRetry, onChanged }: Props) {
  const images = sceneAssets(assets, scene.id, "image");
  const videos = sceneAssets(assets, scene.id, "video");
  const [view, setView] = useState<MediaKind>(videos.length && !images.length ? "video" : "image");
  const [pickedId, setPickedId] = useState<number | null>(null);
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const list = view === "image" ? images : videos;
  const shown = list.find((a) => a.id === pickedId) ?? list[0];
  const active = ACTIVE_SCENE_STATUSES.includes(scene.status);
  const disabled = busy || active;

  async function act(task: () => Promise<unknown>) {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await task();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const generate = (kind: MediaKind) =>
    act(async () => {
      setView(kind);
      setPickedId(null);
      await onGenerate(scene, kind);
    });

  const approve = () =>
    act(async () => {
      await api.approveScene(scene.id);
      await onChanged();
    });

  const reject = () =>
    act(async () => {
      if (!reason.trim()) {
        setError("반려 사유를 입력하세요.");
        return;
      }
      await api.rejectScene(scene.id, reason.trim());
      setRejecting(false);
      setReason("");
      await onChanged();
    });

  return (
    <li className={`card review status-${scene.status}`} data-testid={`review-${scene.scene_number}`}>
      <div className="preview">
        <div className="preview-tabs">
          {(["image", "video"] as MediaKind[]).map((k) => (
            <button
              key={k}
              className={view === k ? "chip active" : "chip"}
              onClick={() => {
                setView(k);
                setPickedId(null);
              }}
            >
              {KIND_LABELS[k]} {k === "image" ? images.length : videos.length}
            </button>
          ))}
        </div>
        <div className="frame" style={{ aspectRatio: aspectRatio.replace(":", " / ") }}>
          {active && <div className="overlay">생성 중…</div>}
          {shown ? (
            view === "image" ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={apiUrl(shown.url)} alt={`장면 ${scene.scene_number} 이미지 v${shown.version}`} />
            ) : (
              <video src={apiUrl(shown.url)} controls loop muted playsInline />
            )
          ) : (
            <span className="muted">아직 {KIND_LABELS[view]}가 없습니다</span>
          )}
        </div>
        {list.length > 1 && (
          <div className="versions">
            {list.map((a) => (
              <button key={a.id} className={a.id === shown?.id ? "chip active" : "chip"} onClick={() => setPickedId(a.id)}>
                v{a.version}
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="review-body">
        <div className="scene-head">
          <strong>장면 {scene.scene_number}</strong>
          <span className={`status-badge status-${scene.status}`}>{SCENE_STATUS_LABELS[scene.status] ?? scene.status}</span>
          <span className="muted">{scene.duration_sec}초</span>
        </div>
        <p className="dialogue">{scene.dialogue || <span className="muted">(대사 없음)</span>}</p>
        <p className="muted small-prompt">이미지 프롬프트: {scene.image_prompt || "(비어 있음 — 화면 설명이나 대사를 사용)"}</p>

        {scene.status === "rejected" && scene.rejection_reason && (
          <p className="note warn">반려 사유: {scene.rejection_reason} — 스토리보드에서 프롬프트를 고친 뒤 재생성하세요.</p>
        )}
        {scene.status === "failed" && latestJob?.status === "failed" && (
          <div className="note error-box">
            <span>
              {KIND_LABELS[latestJob.job_type]} 생성 실패: {latestJob.error_message}
            </span>
            <button className="secondary" onClick={() => act(() => onRetry(latestJob))} disabled={busy}>
              재시도
            </button>
          </div>
        )}

        <div className="actions wrap">
          <button className="secondary" onClick={() => generate("image")} disabled={disabled}>
            {images.length ? "이미지 재생성" : "이미지 생성"}
          </button>
          <button className="secondary" onClick={() => generate("video")} disabled={disabled}>
            {videos.length ? "영상 재생성" : "영상 생성"}
          </button>
          <button onClick={approve} disabled={disabled || scene.status !== "review_required"}>
            승인
          </button>
          <button
            className="danger"
            onClick={() => setRejecting((v) => !v)}
            disabled={disabled || !["review_required", "approved"].includes(scene.status)}
          >
            반려
          </button>
        </div>

        {rejecting && (
          <div className="reject-box">
            <textarea rows={2} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="무엇을 고쳐야 하나요? 예: 고양이가 잘 안 보임" />
            <div className="actions">
              <button className="danger" onClick={reject} disabled={busy}>
                반려 확정
              </button>
              <button className="secondary" onClick={() => setRejecting(false)} disabled={busy}>
                취소
              </button>
            </div>
          </div>
        )}
        {error && <p className="error">{error}</p>}
      </div>
    </li>
  );
}
