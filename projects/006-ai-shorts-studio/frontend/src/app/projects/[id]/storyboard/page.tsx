"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Project } from "@/lib/project";
import { moveItem, totalDuration, type Scene } from "@/lib/scene";
import { useUnsavedWarning } from "@/lib/useUnsavedWarning";
import SceneCard from "./SceneCard";

export default function StoryboardPage() {
  const { id } = useParams<{ id: string }>();
  const projectId = Number(id);
  const [project, setProject] = useState<Project | null>(null);
  const [scenes, setScenes] = useState<Scene[] | null>(null);
  const [dirtyIds, setDirtyIds] = useState<Set<number>>(new Set());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [p, list] = await Promise.all([api.getProject(projectId), api.listScenes(projectId)]);
      setProject(p);
      setScenes(list);
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }, [projectId]);

  useEffect(() => {
    load();
  }, [load]);

  useUnsavedWarning(dirtyIds.size > 0);

  const onDirtyChange = useCallback((sceneId: number, dirty: boolean) => {
    setDirtyIds((prev) => {
      if (prev.has(sceneId) === dirty) return prev;
      const next = new Set(prev);
      if (dirty) next.add(sceneId);
      else next.delete(sceneId);
      return next;
    });
  }, []);

  async function mutate(task: () => Promise<Scene[] | void>) {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const result = await task();
      if (result) setScenes(result);
    } catch (e) {
      setError((e as Error).message);
      await load();
    } finally {
      setBusy(false);
    }
  }

  const onAdd = () =>
    mutate(async () => {
      const created = await api.createScene(projectId, { duration_sec: 3 });
      return [...(scenes ?? []), created];
    });

  const onMove = (index: number, direction: -1 | 1) =>
    mutate(async () => {
      if (!scenes) return;
      const ids = moveItem(scenes.map((s) => s.id), index, direction);
      return api.reorderScenes(projectId, ids);
    });

  const onDelete = (scene: Scene) =>
    mutate(async () => {
      if (!window.confirm(`장면 ${scene.scene_number}을(를) 삭제할까요?`)) return;
      await api.deleteScene(scene.id);
      onDirtyChange(scene.id, false);
      return api.listScenes(projectId);
    });

  const onSaved = (saved: Scene) => setScenes((prev) => prev?.map((s) => (s.id === saved.id ? saved : s)) ?? prev);

  if (!project || !scenes) {
    return <section className="card">{error ? <p className="error">{error}</p> : <p className="muted">불러오는 중…</p>}</section>;
  }

  const total = totalDuration(scenes);

  return (
    <div className="storyboard">
      <section className="card">
        <div className="heading-row">
          <h2>스토리보드</h2>
          {dirtyIds.size > 0 && <span className="badge">저장 안 된 장면 {dirtyIds.size}개</span>}
        </div>
        <p className="muted">
          {project.title} · 장면 {scenes.length}개 · 합계 {total}초 / 목표 {project.target_duration_sec}초
          {total !== project.target_duration_sec && ` (${total > project.target_duration_sec ? "+" : ""}${Math.round((total - project.target_duration_sec) * 10) / 10}초)`}
        </p>
        {error && <p className="error">{error}</p>}
        {scenes.length === 0 && (
          <p className="muted">
            아직 장면이 없습니다. <Link href={`/projects/${projectId}/script`}>대본</Link>에서 &ldquo;스토리보드로 나누기&rdquo;를 누르거나 직접 장면을 추가하세요.
          </p>
        )}
      </section>

      <ol className="scenes">
        {scenes.map((scene, i) => (
          <SceneCard
            key={scene.id}
            scene={scene}
            isFirst={i === 0}
            isLast={i === scenes.length - 1}
            disabled={busy}
            onSaved={onSaved}
            onDirtyChange={onDirtyChange}
            onMove={(dir) => onMove(i, dir)}
            onDelete={() => onDelete(scene)}
          />
        ))}
      </ol>

      <button className="secondary add" onClick={onAdd} disabled={busy}>
        + 장면 추가
      </button>
    </div>
  );
}
