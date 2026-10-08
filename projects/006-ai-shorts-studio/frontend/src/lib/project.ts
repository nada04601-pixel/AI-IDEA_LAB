export type AspectRatio = "9:16" | "16:9" | "1:1";
export type ProjectStatus = "draft" | "in_progress" | "rendering" | "done";

export interface Project {
  id: number;
  title: string;
  topic: string;
  target_duration_sec: number;
  aspect_ratio: AspectRatio;
  visual_style: string;
  status: ProjectStatus;
  created_at: string;
  updated_at: string;
}

export interface ProjectForm {
  title: string;
  topic: string;
  target_duration_sec: number;
  aspect_ratio: AspectRatio;
  visual_style: string;
}

export const ASPECT_RATIOS: AspectRatio[] = ["9:16", "16:9", "1:1"];

export const STATUS_LABELS: Record<ProjectStatus, string> = {
  draft: "초안",
  in_progress: "제작 중",
  rendering: "렌더링 중",
  done: "완료",
};

export const EMPTY_FORM: ProjectForm = {
  title: "",
  topic: "",
  target_duration_sec: 30,
  aspect_ratio: "9:16",
  visual_style: "",
};

export const MIN_DURATION = 5;
export const MAX_DURATION = 180;

/** 백엔드와 같은 규칙으로 입력을 검사한다. 문제가 없으면 빈 객체를 돌려준다. */
export function validateProjectForm(form: ProjectForm): Partial<Record<keyof ProjectForm, string>> {
  const errors: Partial<Record<keyof ProjectForm, string>> = {};
  if (!form.title.trim()) errors.title = "제목을 입력하세요.";
  else if (form.title.length > 200) errors.title = "제목은 200자 이하로 입력하세요.";
  if (form.topic.length > 2000) errors.topic = "주제는 2000자 이하로 입력하세요.";
  const d = form.target_duration_sec;
  if (!Number.isInteger(d) || d < MIN_DURATION || d > MAX_DURATION) {
    errors.target_duration_sec = `길이는 ${MIN_DURATION}~${MAX_DURATION}초 사이 정수로 입력하세요.`;
  }
  if (!ASPECT_RATIOS.includes(form.aspect_ratio)) errors.aspect_ratio = "지원하지 않는 화면 비율입니다.";
  if (form.visual_style.length > 200) errors.visual_style = "스타일은 200자 이하로 입력하세요.";
  return errors;
}

export function toForm(p: Project): ProjectForm {
  return {
    title: p.title,
    topic: p.topic,
    target_duration_sec: p.target_duration_sec,
    aspect_ratio: p.aspect_ratio,
    visual_style: p.visual_style,
  };
}
