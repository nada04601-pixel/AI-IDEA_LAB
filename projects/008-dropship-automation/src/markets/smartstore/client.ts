// 네이버 커머스API(스마트스토어) 판매처 어댑터.
// 커머스API센터에 등록한 "API 호출 IP"에서만 호출됩니다. 고정 IP가 있는 컴퓨터에서 실행하세요.

import bcrypt from "bcryptjs";
import { request } from "../../core/http.ts";
import type { Listing, MarketAdapter, MarketOrderLine, MarketProductRef } from "../../core/types.ts";
import { MARKET_ID, splitWindows, toKstIso, toOrderLine } from "./orders.ts";
import { buildProductBody, type SmartstoreProductDefaults } from "./product.ts";

const API = "https://api.commerce.naver.com/external";

export interface SmartstoreConfig {
  clientId: string;
  clientSecret: string;
  product: SmartstoreProductDefaults;
}

/** 전자서명: bcrypt(client_id + "_" + timestamp, salt = client_secret)를 Base64로 */
export function signature(clientId: string, clientSecret: string, timestamp: number): string {
  const hashed = bcrypt.hashSync(`${clientId}_${timestamp}`, clientSecret);
  return Buffer.from(hashed, "utf8").toString("base64");
}

interface LastChanged {
  data?: { lastChangeStatuses?: { productOrderId: string }[]; more?: { moreFrom: string; moreSequence: string } };
}

export class SmartstoreMarket implements MarketAdapter {
  readonly id = MARKET_ID;
  private cfg: SmartstoreConfig;
  private token: { value: string; until: number } | null = null;

  constructor(cfg: SmartstoreConfig) {
    this.cfg = cfg;
  }

  private async accessToken(): Promise<string> {
    if (this.token && Date.now() < this.token.until) return this.token.value;
    const timestamp = Date.now();
    const res = await request(`${API}/v1/oauth2/token`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        client_id: this.cfg.clientId,
        timestamp: String(timestamp),
        grant_type: "client_credentials",
        client_secret_sign: signature(this.cfg.clientId, this.cfg.clientSecret, timestamp),
        type: "SELF",
      }),
    });
    const j = (await res.json()) as { access_token: string; expires_in: number };
    // 유효 시간은 3시간. 남은 시간이 30분 밑이면 새 토큰이 나오므로 그 전에 다시 받습니다
    this.token = { value: j.access_token, until: Date.now() + Math.max(60, j.expires_in - 1800) * 1000 };
    return j.access_token;
  }

  private async api<T>(method: string, path: string, body?: unknown, opts: { retries?: number } = {}): Promise<T> {
    const res = await request(`${API}${path}`, {
      method,
      headers: {
        Authorization: `Bearer ${await this.accessToken()}`,
        ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
      retries: opts.retries,
    });
    const text = await res.text();
    return (text ? JSON.parse(text) : {}) as T;
  }

  async uploadImages(urls: string[]): Promise<string[]> {
    const out: string[] = [];
    for (let i = 0; i < urls.length; i += 10) {
      const form = new FormData();
      for (const [j, url] of urls.slice(i, i + 10).entries()) {
        const img = await request(url, { timeoutMs: 30_000 });
        const type = img.headers.get("content-type")?.split(";")[0] || "image/jpeg";
        const ext = type.split("/")[1]?.replace("jpeg", "jpg") || "jpg";
        form.append("imageFiles", new Blob([await img.arrayBuffer()], { type }), `image${i + j}.${ext}`);
      }
      const res = await request(`${API}/v1/product-images/upload`, {
        method: "POST",
        headers: { Authorization: `Bearer ${await this.accessToken()}` },
        body: form,
        timeoutMs: 60_000,
      });
      const j = (await res.json()) as { images: { url: string }[] };
      out.push(...j.images.map((x) => x.url));
    }
    return out;
  }

  async registerProduct(listing: Listing): Promise<MarketProductRef> {
    const images = await this.uploadImages(listing.images.slice(0, 10));
    const { body, warnings } = buildProductBody(listing, images, this.cfg.product);
    // 같은 상품이 두 번 등록되지 않도록 재시도하지 않습니다
    const r = await this.api<{ originProductNo: number; smartstoreChannelProductNo?: number }>("POST", "/v2/products", body, { retries: 0 });
    return {
      productId: String(r.originProductNo),
      channelProductId: r.smartstoreChannelProductNo != null ? String(r.smartstoreChannelProductNo) : undefined,
      warnings,
    };
  }

  /** 리프 카테고리 중 이름에 낱말이 들어간 것(상품 등록에 쓸 카테고리 ID 찾기) */
  async searchCategories(keyword: string): Promise<{ id: string; wholeCategoryName: string }[]> {
    const all = await this.api<{ id: string; wholeCategoryName: string }[]>("GET", "/v1/categories?last=true");
    return all.filter((c) => c.wholeCategoryName.includes(keyword));
  }

  async fetchPaidOrders(since: Date, until: Date): Promise<MarketOrderLine[]> {
    const ids = new Set<string>();
    for (const [from, to] of splitWindows(since, until)) {
      let cursor: { from: string; seq?: string } | null = { from: toKstIso(from) };
      while (cursor) {
        const q: URLSearchParams = new URLSearchParams({ lastChangedFrom: cursor.from, lastChangedTo: toKstIso(to), lastChangedType: "PAYED" });
        if (cursor.seq) q.set("moreSequence", cursor.seq);
        const r: LastChanged = await this.api("GET", `/v1/pay-order/seller/product-orders/last-changed-statuses?${q}`);
        for (const s of r.data?.lastChangeStatuses ?? []) ids.add(s.productOrderId);
        const more = r.data?.more;
        cursor = more?.moreFrom ? { from: more.moreFrom, seq: more.moreSequence } : null;
      }
    }
    return this.getOrderLines([...ids]);
  }

  async getOrderLines(productOrderIds: string[]): Promise<MarketOrderLine[]> {
    const lines: MarketOrderLine[] = [];
    for (let i = 0; i < productOrderIds.length; i += 300) {
      const r = await this.api<{ data?: Record<string, unknown>[] }>("POST", "/v1/pay-order/seller/product-orders/query", {
        productOrderIds: productOrderIds.slice(i, i + 300),
        quantityClaimCompatibility: true,
      });
      lines.push(...(r.data ?? []).map(toOrderLine));
    }
    return lines;
  }

  async confirmOrders(lineIds: string[]): Promise<{ ok: string[]; failed: { lineId: string; message: string }[] }> {
    const ok: string[] = [];
    const failed: { lineId: string; message: string }[] = [];
    for (let i = 0; i < lineIds.length; i += 30) {
      const r = await this.api<{
        data?: {
          successProductOrderInfos?: { productOrderId: string }[];
          failProductOrderInfos?: { productOrderId: string; code?: string; message?: string }[];
        };
      }>("POST", "/v1/pay-order/seller/product-orders/confirm", { productOrderIds: lineIds.slice(i, i + 30) });
      ok.push(...(r.data?.successProductOrderInfos ?? []).map((x) => x.productOrderId));
      failed.push(
        ...(r.data?.failProductOrderInfos ?? []).map((x) => ({ lineId: x.productOrderId, message: `${x.code ?? ""} ${x.message ?? ""}`.trim() })),
      );
    }
    return { ok, failed };
  }
}
