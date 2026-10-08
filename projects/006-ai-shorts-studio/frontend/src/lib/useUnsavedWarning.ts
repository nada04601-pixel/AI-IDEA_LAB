import { useEffect } from "react";

/** 저장하지 않은 변경이 있을 때 새로고침·창 닫기 전에 브라우저 경고를 띄운다. */
export function useUnsavedWarning(dirty: boolean) {
  useEffect(() => {
    if (!dirty) return;
    const handler = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [dirty]);
}
