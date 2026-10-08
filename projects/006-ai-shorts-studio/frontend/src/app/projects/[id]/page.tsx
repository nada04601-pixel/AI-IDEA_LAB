"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { STATUS_LABELS, toForm, validateProjectForm, type Project, type ProjectForm } from "@/lib/project";
import ProjectFields from "../../ProjectFields";

export default function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const projectId = Number(id);
  const router = useRouter();
  const [project, setProject] = useState<Project | null>(null);
  const [form, setForm] = useState<ProjectForm | null>(null);
  const [errors, setErrors] = useState<Partial<Record<keyof ProjectForm, string>>>({});
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api
      .getProject(projectId)
      .then((p) => {
        setProject(p);
        setForm(toForm(p));
      })
      .catch((e: Error) => setError(e.message));
  }, [projectId]);

  async function onSave(e: React.FormEvent) {
    e.preventDefault();
    if (!form || busy) return;
    const found = validateProjectForm(form);
    setErrors(found);
    if (Object.keys(found).length > 0) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const updated = await api.updateProject(projectId, { ...form, title: form.title.trim() });
      setProject(updated);
      setForm(toForm(updated));
      setMessage("저장했습니다.");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function onDelete() {
    if (!project || busy) return;
    if (!window.confirm(`"${project.title}" 프로젝트를 삭제할까요? 되돌릴 수 없습니다.`)) return;
    setBusy(true);
    try {
      await api.deleteProject(projectId);
      router.push("/");
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  if (!project || !form) {
    return (
      <section className="card">
        {error ? <p className="error">{error}</p> : <p className="muted">불러오는 중…</p>}
      </section>
    );
  }

  return (
    <section className="card narrow">
      <h2>{project.title}</h2>
      <p className="muted">
        상태: {STATUS_LABELS[project.status] ?? project.status} · 만든 날짜:{" "}
        {new Date(project.created_at).toLocaleString("ko-KR")}
      </p>
      <form onSubmit={onSave} className="form">
        <ProjectFields form={form} errors={errors} onChange={setForm} />
        {message && <p className="ok">{message}</p>}
        {error && <p className="error">{error}</p>}
        <div className="actions">
          <button type="submit" disabled={busy}>
            저장
          </button>
          <button type="button" className="danger" onClick={onDelete} disabled={busy}>
            삭제
          </button>
        </div>
      </form>
    </section>
  );
}
