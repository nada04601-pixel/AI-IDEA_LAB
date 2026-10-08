"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import {
  isSceneFormDirty,
  MAX_SCENE_SEC,
  MIN_SCENE_SEC,
  SCENE_STATUS_LABELS,
  toSceneForm,
  validateSceneForm,
  type Scene,
  type SceneForm,
} from "@/lib/scene";

interface Props {
  scene: Scene;
  isFirst: boolean;
  isLast: boolean;
  disabled: boolean;
  onSaved: (scene: Scene) => void;
  onDirtyChange: (sceneId: number, dirty: boolean) => void;
  onMove: (direction: -1 | 1) => void;
  onDelete: () => void;
}

const FIELDS: { key: Exclude<keyof SceneForm, "duration_sec">; label: string; rows: number }[] = [
  { key: "dialogue", label: "내레이션/대사", rows: 3 },
  { key: "visual_description", label: "화면 설명", rows: 2 },
  { key: "image_prompt", label: "이미지 프롬프트", rows: 2 },
  { key: "video_prompt", label: "영상 프롬프트", rows: 2 },
];

export default function SceneCard({ scene, isFirst, isLast, disabled, onSaved, onDirtyChange, onMove, onDelete }: Props) {
  const [form, setForm] = useState<SceneForm>(() => toSceneForm(scene));
  const [errors, setErrors] = useState<Partial<Record<keyof SceneForm, string>>>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const dirty = isSceneFormDirty(form, scene);

  function update(next: SceneForm) {
    setForm(next);
    onDirtyChange(scene.id, isSceneFormDirty(next, scene));
  }

  async function onSave() {
    const found = validateSceneForm(form);
    setErrors(found);
    if (Object.keys(found).length > 0 || saving) return;
    setSaving(true);
    setError(null);
    try {
      const saved = await api.updateScene(scene.id, form);
      setForm(toSceneForm(saved));
      onDirtyChange(scene.id, false);
      onSaved(saved);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <li className="scene card" data-testid={`scene-${scene.scene_number}`}>
      <div className="scene-head">
        <strong>장면 {scene.scene_number}</strong>
        <span className="muted">{SCENE_STATUS_LABELS[scene.status] ?? scene.status}</span>
        {dirty && <span className="badge">저장 안 됨</span>}
        <div className="spacer" />
        <button className="icon" onClick={() => onMove(-1)} disabled={disabled || isFirst} aria-label="위로">
          ↑
        </button>
        <button className="icon" onClick={() => onMove(1)} disabled={disabled || isLast} aria-label="아래로">
          ↓
        </button>
        <button className="icon danger" onClick={onDelete} disabled={disabled} aria-label="장면 삭제">
          ✕
        </button>
      </div>
      <div className="form">
        {FIELDS.map((f) => (
          <label key={f.key}>
            {f.label}
            <textarea rows={f.rows} value={form[f.key]} onChange={(e) => update({ ...form, [f.key]: e.target.value })} />
            {errors[f.key] && <span className="error">{errors[f.key]}</span>}
          </label>
        ))}
        <div className="row">
          <label>
            길이(초)
            <input
              type="number"
              step={0.5}
              min={MIN_SCENE_SEC}
              max={MAX_SCENE_SEC}
              value={Number.isNaN(form.duration_sec) ? "" : form.duration_sec}
              onChange={(e) => update({ ...form, duration_sec: e.target.valueAsNumber })}
            />
            {errors.duration_sec && <span className="error">{errors.duration_sec}</span>}
          </label>
          <div className="save-cell">
            <button onClick={onSave} disabled={saving || !dirty}>
              {saving ? "저장 중…" : "장면 저장"}
            </button>
          </div>
        </div>
        {error && <p className="error">{error}</p>}
      </div>
    </li>
  );
}
