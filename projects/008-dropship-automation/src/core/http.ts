export class HttpError extends Error {
  readonly status: number;
  readonly body: string;
  constructor(status: number, body: string, url: string) {
    super(`HTTP ${status} ${url}: ${body.slice(0, 500)}`);
    this.status = status;
    this.body = body;
  }
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/**
 * fetch + 시간 제한 + 재시도. 429와 5xx, 네트워크 오류만 다시 시도합니다.
 * 주문 생성처럼 두 번 실행되면 안 되는 요청은 retries: 0으로 부릅니다.
 */
export async function request(
  url: string,
  init: RequestInit & { timeoutMs?: number; retries?: number } = {},
): Promise<Response> {
  const { timeoutMs = 20_000, retries = 2, ...rest } = init;
  for (let attempt = 0; ; attempt++) {
    try {
      const res = await fetch(url, { ...rest, signal: AbortSignal.timeout(timeoutMs) });
      if ((res.status === 429 || res.status >= 500) && attempt < retries) {
        const wait = Number(res.headers.get("retry-after")) * 1000 || 1000 * 2 ** attempt;
        await sleep(wait);
        continue;
      }
      if (!res.ok) throw new HttpError(res.status, await res.text(), url.split("?")[0]);
      return res;
    } catch (e) {
      if (e instanceof HttpError || attempt >= retries) throw e;
      await sleep(1000 * 2 ** attempt);
    }
  }
}
