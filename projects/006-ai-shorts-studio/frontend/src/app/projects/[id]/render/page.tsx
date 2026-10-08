"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api, apiUrl } from "@/lib/api";
import { isJobActive, type Asset } from "@/lib/generation";
import { AUDIO_STATUS_LABELS, formatTime, scenesNeedingAudio, type RenderCheck, type Subtitles } from "@/lib/render";
import { SCENE_STATUS_LABELS } from "@/lib/scene";
import { confirmCost, useProjectMedia } from "@/lib/useProjectMedia";

function downloadText(filename: string, text: string) {
  const url = URL.createObjectURL(new Blob([text], { type: "application/x-subrip;charset=utf-8" }));
  const a = Object.assign(document.createElement("a"), { href: url, download: filename });
  a.click();
  URL.revokeObjectURL(url);
}

export default function RenderPage() {
  const { id } = useParams<{ id: string }>();
  const projectId = Number(id);
  const { data, error, reload } = useProjectMedia(projectId);
  const [includeAudio, setIncludeAudio] = useState(true);
  const [burnSubtitles, setBurnSubtitles] = useState(true);
  const [check, setCheck] = useState<RenderCheck | null>(null);
  const [subs, setSubs] = useState<Subtitles | null>(null);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  // 작업 목록이 바뀔 때(음성·렌더링이 끝날 때)마다 점검 결과와 자막을 새로 받는다
  const jobsKey = data?.jobs.map((j) => `${j.id}:${j.status}`).join(",");
  useEffect(() => {
    if (!data) return;
    Promise.all([api.renderCheck(projectId, includeAudio), api.getSubtitles(projectId)])
      .then(([c, s]) => {
        setCheck(c);
        setSubs(s);
      })
      .catch((e: Error) => setActionError(e.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, includeAudio, jobsKey, data?.project.updated_at]);

  if (!data || !check || !subs) {
    return <section className="card">{error || actionError ? <p className="error">{error ?? actionError}</p> : <p className="muted">불러오는 중…</p>}</section>;
  }

  const { project, jobs, assets, providers } = data;
  const renderJobs = jobs.filter((j) => j.job_type === "render");
  const activeRender = renderJobs.find(isJobActive);
  const lastRender = renderJobs[0];
  const audioActive = jobs.some((j) => j.job_type === "audio" && isJobActive(j));
  const renders = assets.filter((a) => a.asset_type === "render").sort((a, b) => b.version - a.version);
  const subtitleFor = (r: Asset) => assets.find((a) => a.asset_type === "subtitle" && a.version === r.version && a.scene_id === null);
  const latest = renders[0];
  const needAudio = scenesNeedingAudio(check.scenes);
  const tts = providers.find((p) => p.kind === "audio");

  async function act(task: () => Promise<unknown>) {
    if (busy) return;
    setBusy(true);
    setActionError(null);
    try {
      await task();
      await reload();
    } catch (e) {
      setActionError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const makeAudio = () =>
    act(async () => {
      const { ok, confirmPaid } = confirmCost(providers, "audio");
      if (ok) await api.generateProjectAudio(projectId, confirmPaid);
    });

  const startRender = () => act(() => api.startRender(projectId, { include_audio: includeAudio, burn_subtitles: burnSubtitles }));
  const retryRender = () => act(() => (lastRender ? api.retryJob(lastRender.id, false) : Promise.resolve()));

  return (
    <div className="storyboard">
      <section className="card">
        <h2>최종 렌더링</h2>
        <p className="muted">
          {project.title} · 장면 {check.scenes.length}개 · 총 {formatTime(check.total_duration)} · {project.aspect_ratio}
        </p>
        <p className={check.ffmpeg.available ? "muted small" : "error"}>
          {check.ffmpeg.available ? `FFmpeg ${check.ffmpeg.version ?? ""} 사용 가능` : "FFmpeg를 찾을 수 없습니다. 설치하거나 AISS_FFMPEG_PATH를 지정하세요."}
        </p>
        {check.problems.length > 0 ? (
          <ul className="problems" data-testid="problems">
            {check.problems.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        ) : (
          <p className="ok">렌더링 준비가 끝났습니다.</p>
        )}
        {check.problems.some((p) => p.includes("승인")) && (
          <p className="muted small">
            <Link href={`/projects/${projectId}/review`}>검토</Link>에서 모든 장면을 승인해야 렌더링할 수 있습니다.
          </p>
        )}
        {(error || actionError) && <p className="error">{actionError ?? error}</p>}
      </section>

      <section className="card">
        <div className="heading-row">
          <h2>음성</h2>
          <span className="muted small-inline">{tts ? `${tts.name} · ${tts.is_paid ? "유료" : "무료"}` : ""}</span>
        </div>
        <div className="table-wrap">
          <table className="jobs">
            <thead>
              <tr>
                <th>장면</th>
                <th>검토</th>
                <th>화면</th>
                <th>길이</th>
                <th>음성</th>
              </tr>
            </thead>
            <tbody>
              {check.scenes.map((s) => (
                <tr key={s.id} data-testid={`render-scene-${s.scene_number}`}>
                  <td>{s.scene_number}</td>
                  <td>
                    <span className={`status-badge status-${s.status}`}>{SCENE_STATUS_LABELS[s.status] ?? s.status}</span>
                  </td>
                  <td>{s.visual === "video" ? "영상" : s.visual === "image" ? "이미지" : "-"}</td>
                  <td>{s.duration_sec}초</td>
                  <td>
                    <span className={`status-badge audio-${s.audio}`}>{AUDIO_STATUS_LABELS[s.audio]}</span>
                    {s.audio === "ready" && s.audio_asset_id && (
                      <audio className="mini-audio" controls preload="none" src={apiUrl(`/api/assets/${s.audio_asset_id}/file`)} />
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="actions wrap">
          <button className="secondary" onClick={makeAudio} disabled={busy || audioActive || !!activeRender || needAudio === 0}>
            {audioActive ? "음성 만드는 중…" : needAudio ? `음성 만들기 (${needAudio}개 장면)` : "모든 음성 준비됨"}
          </button>
        </div>
        <p className="muted small">mock 음성은 실제 목소리 대신 자막이 바뀌는 시점마다 짧은 소리가 나는 장면 길이의 WAV입니다.</p>
      </section>

      <section className="card">
        <div className="heading-row">
          <h2>자막</h2>
          <span className="muted small-inline">{subs.cues.length}개</span>
        </div>
        {subs.cues.length === 0 ? (
          <p className="muted">대사가 있는 장면이 없어 자막이 없습니다.</p>
        ) : (
          <ol className="cues">
            {subs.cues.map((c) => (
              <li key={c.index}>
                <span className="muted nowrap">
                  {formatTime(c.start)} – {formatTime(c.end)}
                </span>
                <span className="cue-text">{c.text}</span>
              </li>
            ))}
          </ol>
        )}
        <div className="actions wrap">
          <button className="secondary" onClick={() => downloadText(`${project.title}.srt`, subs.srt)} disabled={!subs.srt}>
            SRT 내려받기
          </button>
        </div>
        <p className="muted small">자막은 장면 대사와 길이로 자동 계산됩니다. 고치려면 스토리보드에서 대사나 장면 길이를 바꾸세요.</p>
      </section>

      <section className="card">
        <h2>렌더링</h2>
        <div className="options">
          <label className="check">
            <input type="checkbox" checked={includeAudio} onChange={(e) => setIncludeAudio(e.target.checked)} /> 음성 넣기
          </label>
          <label className="check">
            <input type="checkbox" checked={burnSubtitles} onChange={(e) => setBurnSubtitles(e.target.checked)} /> 자막을 영상에 입히기
          </label>
        </div>
        <p className="muted small">켜고 끌 수 있는 자막 트랙은 항상 함께 들어갑니다. 출력: H.264 MP4, {project.aspect_ratio === "9:16" ? "1080×1920" : project.aspect_ratio === "16:9" ? "1920×1080" : "1080×1080"}, 30fps.</p>
        {activeRender ? (
          <div data-testid="render-progress">
            <p className="muted">렌더링 중… {activeRender.progress}%</p>
            <div className="progress">
              <div style={{ width: `${activeRender.progress}%` }} />
            </div>
          </div>
        ) : (
          <div className="actions wrap">
            <button onClick={startRender} disabled={busy || !check.ready || audioActive}>
              {renders.length ? "다시 렌더링" : "MP4 렌더링"}
            </button>
          </div>
        )}
        {lastRender?.status === "failed" && !activeRender && (
          <div className="note error-box">
            <span>렌더링 실패: {lastRender.error_message}</span>
            <button className="secondary" onClick={retryRender} disabled={busy}>
              재시도
            </button>
          </div>
        )}
      </section>

      {latest && (
        <section className="card" data-testid="render-result">
          <h2>결과</h2>
          <div className="result">
            <video className="final" src={apiUrl(latest.url)} controls playsInline style={{ aspectRatio: project.aspect_ratio.replace(":", " / ") }} />
            <div className="result-info">
              <p>
                <strong>v{latest.version}</strong> · {formatTime(Number(latest.metadata.duration_sec ?? 0))} · {String(latest.metadata.width)}×{String(latest.metadata.height)}
              </p>
              <p className="muted small-inline">
                음성 {latest.metadata.include_audio ? "포함" : "없음"} · 자막 {latest.metadata.burn_subtitles ? "입힘" : "트랙만"} ·{" "}
                {new Date(latest.created_at).toLocaleString("ko-KR")}
              </p>
              <div className="actions wrap">
                <a className="button" href={apiUrl(`${latest.url}?download=true`)} download>
                  MP4 내려받기
                </a>
                {subtitleFor(latest) && (
                  <a className="button secondary" href={apiUrl(`${subtitleFor(latest)!.url}?download=true`)} download>
                    SRT 내려받기
                  </a>
                )}
              </div>
              {renders.length > 1 && (
                <>
                  <p className="muted small-inline">이전 버전</p>
                  <ul className="versions-list">
                    {renders.slice(1).map((r) => (
                      <li key={r.id}>
                        <a href={apiUrl(`${r.url}?download=true`)} download>
                          v{r.version} 내려받기
                        </a>{" "}
                        <span className="muted">{new Date(r.created_at).toLocaleString("ko-KR")}</span>
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </div>
          </div>
        </section>
      )}
    </div>
  );
}
