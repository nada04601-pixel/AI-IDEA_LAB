import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import { ACTIVE_SCENE_STATUSES, isJobActive, type Asset, type Job, type ProviderInfo } from "./generation";
import type { Project } from "./project";
import type { Scene } from "./scene";

export interface ProjectMedia {
  project: Project;
  scenes: Scene[];
  jobs: Job[];
  assets: Asset[];
  providers: ProviderInfo[];
}

const POLL_MS = 1500;

/** 프로젝트의 장면·작업·자산을 불러오고, 진행 중인 작업이 있으면 끝날 때까지 주기적으로 새로 고친다. */
export function useProjectMedia(projectId: number) {
  const [data, setData] = useState<ProjectMedia | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const load = useCallback(async () => {
    try {
      const [project, scenes, jobs, assets, providers] = await Promise.all([
        api.getProject(projectId),
        api.listScenes(projectId),
        api.listJobs(projectId),
        api.listAssets(projectId),
        api.listProviders(),
      ]);
      setData({ project, scenes, jobs, assets, providers });
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }, [projectId]);

  useEffect(() => {
    load();
  }, [load]);

  const active = !!data && (data.jobs.some(isJobActive) || data.scenes.some((s) => ACTIVE_SCENE_STATUSES.includes(s.status)));
  useEffect(() => {
    if (!active) return;
    timer.current = setTimeout(load, POLL_MS);
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, [active, data, load]);

  return { data, error, reload: load, active };
}

/** 유료 공급자면 예상 비용을 보여주고 확인을 받는다. 무료면 바로 true. */
export function confirmCost(providers: ProviderInfo[], kind: string): { ok: boolean; confirmPaid: boolean } {
  const p = providers.find((x) => x.kind === kind);
  if (!p || !p.is_paid) return { ok: true, confirmPaid: false };
  const ok = window.confirm(
    `유료 작업입니다.\n공급자: ${p.name}\n예상 비용: 약 ${p.estimated_cost_per_job} ${p.currency} (1건)\n\n진행할까요?`,
  );
  return { ok, confirmPaid: ok };
}
