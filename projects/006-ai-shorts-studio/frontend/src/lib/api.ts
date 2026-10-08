import type { Project, ProjectForm, ProjectStatus } from "./project";
import type { Asset, Job, MediaKind, ProviderInfo } from "./generation";
import type { Scene, SceneForm } from "./scene";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    throw new ApiError(`백엔드(${API_BASE})에 연결할 수 없습니다. 서버가 실행 중인지 확인하세요.`, 0);
  }
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const detail = typeof body?.detail === "string" ? body.detail : `요청 실패 (${res.status})`;
    throw new ApiError(detail, res.status);
  }
  return (res.status === 204 ? undefined : await res.json()) as T;
}

/** 백엔드가 돌려준 상대 경로(/api/...)를 전체 주소로 바꾼다. */
export const apiUrl = (path: string) => `${API_BASE}${path}`;

const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

export const api = {
  listProjects: () => request<Project[]>("/api/projects"),
  getProject: (id: number) => request<Project>(`/api/projects/${id}`),
  createProject: (body: ProjectForm) => post<Project>("/api/projects", body),
  updateProject: (id: number, body: Partial<ProjectForm> & { script?: string; status?: ProjectStatus }) =>
    request<Project>(`/api/projects/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteProject: (id: number) => request<void>(`/api/projects/${id}`, { method: "DELETE" }),

  generateScript: (id: number, overwrite: boolean) =>
    post<Project>(`/api/projects/${id}/generate-script`, { overwrite }),
  generateStoryboard: (id: number, replace: boolean) =>
    post<Scene[]>(`/api/projects/${id}/storyboard`, { replace }),

  listScenes: (projectId: number) => request<Scene[]>(`/api/projects/${projectId}/scenes`),
  createScene: (projectId: number, body: Partial<SceneForm> = {}) =>
    post<Scene>(`/api/projects/${projectId}/scenes`, body),
  updateScene: (sceneId: number, body: Partial<SceneForm>) =>
    request<Scene>(`/api/scenes/${sceneId}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteScene: (sceneId: number) => request<void>(`/api/scenes/${sceneId}`, { method: "DELETE" }),
  reorderScenes: (projectId: number, sceneIds: number[]) =>
    post<Scene[]>(`/api/projects/${projectId}/scenes/reorder`, { scene_ids: sceneIds }),

  listProviders: () => request<ProviderInfo[]>("/api/providers"),
  generateMedia: (sceneId: number, kind: MediaKind, confirmPaid: boolean) =>
    post<Job>(`/api/scenes/${sceneId}/generate-${kind}`, { confirm_paid: confirmPaid }),
  approveScene: (sceneId: number) => post<Scene>(`/api/scenes/${sceneId}/approve`),
  rejectScene: (sceneId: number, reason: string) => post<Scene>(`/api/scenes/${sceneId}/reject`, { reason }),
  listJobs: (projectId: number) => request<Job[]>(`/api/projects/${projectId}/jobs`),
  retryJob: (jobId: number, confirmPaid: boolean) => post<Job>(`/api/jobs/${jobId}/retry`, { confirm_paid: confirmPaid }),
  listAssets: (projectId: number) => request<Asset[]>(`/api/projects/${projectId}/assets`),
};
