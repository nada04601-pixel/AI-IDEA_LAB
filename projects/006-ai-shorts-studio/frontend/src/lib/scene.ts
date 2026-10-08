export interface Scene {
  id: number;
  project_id: number;
  scene_number: number;
  dialogue: string;
  visual_description: string;
  image_prompt: string;
  video_prompt: string;
  duration_sec: number;
  status: string;
  rejection_reason: string | null;
  approved_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface SceneForm {
  dialogue: string;
  visual_description: string;
  image_prompt: string;
  video_prompt: string;
  duration_sec: number;
}

export const MIN_SCENE_SEC = 0.5;
export const MAX_SCENE_SEC = 60;

export const SCENE_STATUS_LABELS: Record<string, string> = {
  draft: "초안",
  queued: "생성 대기",
  generating: "생성 중",
  review_required: "검토 필요",
  approved: "승인",
  rejected: "반려",
  failed: "실패",
};

export function toSceneForm(s: Scene): SceneForm {
  return {
    dialogue: s.dialogue,
    visual_description: s.visual_description,
    image_prompt: s.image_prompt,
    video_prompt: s.video_prompt,
    duration_sec: s.duration_sec,
  };
}

export function isSceneFormDirty(form: SceneForm, scene: Scene): boolean {
  const saved = toSceneForm(scene);
  return (Object.keys(saved) as (keyof SceneForm)[]).some((k) => form[k] !== saved[k]);
}

export function validateSceneForm(form: SceneForm): Partial<Record<keyof SceneForm, string>> {
  const errors: Partial<Record<keyof SceneForm, string>> = {};
  if (form.dialogue.length > 2000) errors.dialogue = "대사는 2000자 이하로 입력하세요.";
  if (form.visual_description.length > 2000) errors.visual_description = "화면 설명은 2000자 이하로 입력하세요.";
  if (form.image_prompt.length > 4000) errors.image_prompt = "이미지 프롬프트는 4000자 이하로 입력하세요.";
  if (form.video_prompt.length > 4000) errors.video_prompt = "영상 프롬프트는 4000자 이하로 입력하세요.";
  const d = form.duration_sec;
  if (!Number.isFinite(d) || d < MIN_SCENE_SEC || d > MAX_SCENE_SEC) {
    errors.duration_sec = `길이는 ${MIN_SCENE_SEC}~${MAX_SCENE_SEC}초 사이로 입력하세요.`;
  }
  return errors;
}

/** index 위치의 항목을 한 칸 옮긴 새 배열. 범위를 벗어나면 원래 배열을 그대로 돌려준다. */
export function moveItem<T>(items: T[], index: number, direction: -1 | 1): T[] {
  const target = index + direction;
  if (index < 0 || index >= items.length || target < 0 || target >= items.length) return items;
  const next = [...items];
  [next[index], next[target]] = [next[target], next[index]];
  return next;
}

export function totalDuration(scenes: Pick<Scene, "duration_sec">[]): number {
  return Math.round(scenes.reduce((sum, s) => sum + s.duration_sec, 0) * 10) / 10;
}
