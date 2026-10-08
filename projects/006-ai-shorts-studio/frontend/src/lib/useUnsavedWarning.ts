import { useEffect, useId } from "react";

// 화면 곳곳의 "저장 안 됨" 상태를 모아 둔다. 탭 이동 같은 앱 안 이동에서도 확인할 수 있게 한다.
const dirtySources = new Set<string>();

export function hasUnsavedChanges(): boolean {
  return dirtySources.size > 0;
}

/** 저장하지 않은 변경이 있으면 이동해도 되는지 묻는다. 이동해도 되면 true. */
export function confirmLeave(): boolean {
  if (!hasUnsavedChanges()) return true;
  const ok = window.confirm("저장하지 않은 변경이 있습니다. 저장하지 않고 이동할까요?");
  if (ok) dirtySources.clear();
  return ok;
}

/** 저장하지 않은 변경이 있을 때 새로고침·창 닫기와 앱 안 탭 이동 전에 경고한다. */
export function useUnsavedWarning(dirty: boolean) {
  const id = useId();
  useEffect(() => {
    if (!dirty) return;
    dirtySources.add(id);
    const handler = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", handler);
    return () => {
      dirtySources.delete(id);
      window.removeEventListener("beforeunload", handler);
    };
  }, [dirty, id]);
}
