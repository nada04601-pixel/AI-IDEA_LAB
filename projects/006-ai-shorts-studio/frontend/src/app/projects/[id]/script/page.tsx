"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { countParagraphs, estimateReadSeconds, MAX_SCRIPT_LENGTH, type Project } from "@/lib/project";
import { useUnsavedWarning } from "@/lib/useUnsavedWarning";

export default function ScriptPage() {
  const { id } = useParams<{ id: string }>();
  const projectId = Number(id);
  const router = useRouter();
  const [project, setProject] = useState<Project | null>(null);
  const [script, setScript] = useState("");
  const [sceneCount, setSceneCount] = useState(0);
  const [busy, setBusy] = useState<null | "save" | "generate" | "storyboard">(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.getProject(projectId), api.listScenes(projectId)])
      .then(([p, scenes]) => {
        setProject(p);
        setScript(p.script);
        setSceneCount(scenes.length);
      })
      .catch((e: Error) => setError(e.message));
  }, [projectId]);

  const dirty = project !== null && script !== project.script;
  const tooLong = script.length > MAX_SCRIPT_LENGTH;
  useUnsavedWarning(dirty);

  async function run(kind: NonNullable<typeof busy>, task: () => Promise<void>) {
    if (busy) return;
    setBusy(kind);
    setError(null);
    setMessage(null);
    try {
      await task();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  async function saveScript(): Promise<Project> {
    const updated = await api.updateProject(projectId, { script });
    setProject(updated);
    setScript(updated.script);
    return updated;
  }

  const onSave = () =>
    run("save", async () => {
      await saveScript();
      setMessage("대본을 저장했습니다.");
    });

  const onGenerate = () =>
    run("generate", async () => {
      const hasText = script.trim().length > 0;
      if (hasText && !window.confirm("지금 대본을 mock 초안으로 바꿀까요? 현재 내용은 사라집니다.")) return;
      const updated = await api.generateScript(projectId, hasText || !!project?.script.trim());
      setProject(updated);
      setScript(updated.script);
      setMessage("mock 대본 초안을 만들었습니다. 내용을 고친 뒤 저장하세요.");
    });

  const onStoryboard = () =>
    run("storyboard", async () => {
      if (sceneCount > 0 && !window.confirm(`이미 장면이 ${sceneCount}개 있습니다. 지금 대본으로 다시 나눌까요? 기존 장면 편집 내용은 사라집니다.`)) {
        return;
      }
      if (dirty) await saveScript();
      await api.generateStoryboard(projectId, sceneCount > 0);
      router.push(`/projects/${projectId}/storyboard`);
    });

  if (!project) {
    return <section className="card">{error ? <p className="error">{error}</p> : <p className="muted">불러오는 중…</p>}</section>;
  }

  const paragraphs = countParagraphs(script);
  const readSec = estimateReadSeconds(script);

  return (
    <section className="card">
      <div className="heading-row">
        <h2>대본 편집기</h2>
        {dirty && <span className="badge">저장 안 됨</span>}
      </div>
      <p className="muted">
        {project.title} · 목표 {project.target_duration_sec}초. 빈 줄로 문단을 나누면 한 문단이 한 장면이 됩니다.
      </p>
      <textarea
        className="script"
        rows={16}
        value={script}
        onChange={(e) => setScript(e.target.value)}
        placeholder="대본을 직접 쓰거나 '대본 초안 생성'을 누르세요."
      />
      <p className={tooLong ? "error" : "muted"}>
        {script.length.toLocaleString()} / {MAX_SCRIPT_LENGTH.toLocaleString()}자 · 장면 {paragraphs}개 예상 · 읽기 약 {readSec}초
        {readSec > project.target_duration_sec && " (목표보다 깁니다)"}
      </p>
      {message && <p className="ok">{message}</p>}
      {error && <p className="error">{error}</p>}
      <div className="actions wrap">
        <button onClick={onSave} disabled={!!busy || !dirty || tooLong}>
          {busy === "save" ? "저장 중…" : "저장"}
        </button>
        <button className="secondary" onClick={onGenerate} disabled={!!busy}>
          {busy === "generate" ? "생성 중…" : "대본 초안 생성 (mock)"}
        </button>
        <button className="secondary" onClick={onStoryboard} disabled={!!busy || paragraphs === 0 || tooLong}>
          {busy === "storyboard" ? "나누는 중…" : "스토리보드로 나누기"}
        </button>
      </div>
      <p className="muted small">mock 공급자는 외부 AI를 호출하지 않고 정해진 형식의 예시 대본을 만듭니다. 비용이 들지 않습니다.</p>
    </section>
  );
}
