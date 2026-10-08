"use client";

import { ASPECT_RATIOS, MAX_DURATION, MIN_DURATION, type AspectRatio, type ProjectForm } from "@/lib/project";

interface Props {
  form: ProjectForm;
  errors: Partial<Record<keyof ProjectForm, string>>;
  onChange: (form: ProjectForm) => void;
}

export default function ProjectFields({ form, errors, onChange }: Props) {
  const set = <K extends keyof ProjectForm>(key: K, value: ProjectForm[K]) => onChange({ ...form, [key]: value });

  return (
    <>
      <label>
        제목
        <input value={form.title} onChange={(e) => set("title", e.target.value)} placeholder="예: 고양이가 상자를 좋아하는 이유" />
        {errors.title && <span className="error">{errors.title}</span>}
      </label>
      <label>
        주제
        <textarea rows={3} value={form.topic} onChange={(e) => set("topic", e.target.value)} placeholder="쇼츠로 다룰 내용을 적어 주세요" />
        {errors.topic && <span className="error">{errors.topic}</span>}
      </label>
      <div className="row">
        <label>
          목표 길이(초)
          <input
            type="number"
            min={MIN_DURATION}
            max={MAX_DURATION}
            value={Number.isNaN(form.target_duration_sec) ? "" : form.target_duration_sec}
            onChange={(e) => set("target_duration_sec", e.target.valueAsNumber)}
          />
          {errors.target_duration_sec && <span className="error">{errors.target_duration_sec}</span>}
        </label>
        <label>
          화면 비율
          <select value={form.aspect_ratio} onChange={(e) => set("aspect_ratio", e.target.value as AspectRatio)}>
            {ASPECT_RATIOS.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
        </label>
      </div>
      <label>
        분위기/스타일
        <input value={form.visual_style} onChange={(e) => set("visual_style", e.target.value)} placeholder="예: 따뜻한 수채화, 빠른 컷 편집" />
        {errors.visual_style && <span className="error">{errors.visual_style}</span>}
      </label>
    </>
  );
}
