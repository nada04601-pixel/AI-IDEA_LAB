"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { EMPTY_FORM, STATUS_LABELS, validateProjectForm, type Project, type ProjectForm } from "@/lib/project";
import ProjectFields from "./ProjectFields";

export default function DashboardPage() {
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [form, setForm] = useState<ProjectForm>(EMPTY_FORM);
  const [errors, setErrors] = useState<Partial<Record<keyof ProjectForm, string>>>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      setProjects(await api.listProjects());
      setLoadError(null);
    } catch (e) {
      setLoadError((e as Error).message);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    const found = validateProjectForm(form);
    setErrors(found);
    if (Object.keys(found).length > 0 || saving) return;
    setSaving(true);
    setSubmitError(null);
    try {
      await api.createProject({ ...form, title: form.title.trim() });
      setForm(EMPTY_FORM);
      await load();
    } catch (err) {
      setSubmitError((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="grid">
      <section className="card">
        <h2>새 프로젝트</h2>
        <form onSubmit={onCreate} className="form">
          <ProjectFields form={form} errors={errors} onChange={setForm} />
          {submitError && <p className="error">{submitError}</p>}
          <button type="submit" disabled={saving}>
            {saving ? "만드는 중…" : "프로젝트 만들기"}
          </button>
        </form>
      </section>

      <section className="card">
        <h2>프로젝트 목록</h2>
        {loadError && (
          <p className="error">
            {loadError} <button onClick={load}>다시 시도</button>
          </p>
        )}
        {!loadError && projects === null && <p className="muted">불러오는 중…</p>}
        {projects?.length === 0 && <p className="muted">아직 프로젝트가 없습니다. "새 프로젝트"에서 만들어 보세요.</p>}
        <ul className="list">
          {projects?.map((p) => (
            <li key={p.id}>
              <Link href={`/projects/${p.id}`}>
                <strong>{p.title}</strong>
                <span className="muted">
                  {STATUS_LABELS[p.status] ?? p.status} · {p.target_duration_sec}초 · {p.aspect_ratio}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
