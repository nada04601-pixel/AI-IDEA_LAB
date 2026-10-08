export type AudioStatus = "ready" | "none" | "stale" | "no_text";

export interface SceneCheck {
  id: number;
  scene_number: number;
  status: string;
  duration_sec: number;
  visual: "image" | "video" | null;
  visual_asset_id: number | null;
  audio: AudioStatus;
  audio_asset_id: number | null;
}

export interface RenderCheck {
  ffmpeg: { available: boolean; path: string | null; version: string | null };
  ready: boolean;
  problems: string[];
  audio_problems: string[];
  total_duration: number;
  scenes: SceneCheck[];
}

export interface Cue {
  index: number;
  start: number;
  end: number;
  text: string;
  scene_number: number;
}

export interface Subtitles {
  cues: Cue[];
  srt: string;
}

export const AUDIO_STATUS_LABELS: Record<AudioStatus, string> = {
  ready: "준비됨",
  none: "없음",
  stale: "대사 바뀜",
  no_text: "대사 없음 (무음)",
};

/** 초를 "0:03.5" 형식으로. */
export function formatTime(seconds: number): string {
  const tenths = Math.round(seconds * 10) / 10; // 0.1초 단위로 반올림 (6.03 → 0:06)
  const m = Math.floor(tenths / 60);
  const s = Math.round((tenths - m * 60) * 10) / 10;
  const text = Number.isInteger(s) ? String(s) : s.toFixed(1);
  return `${m}:${s < 10 ? "0" : ""}${text}`;
}

/** 음성을 새로 만들어야 하는 장면 수. */
export function scenesNeedingAudio(scenes: Pick<SceneCheck, "audio">[]): number {
  return scenes.filter((s) => s.audio === "none" || s.audio === "stale").length;
}
