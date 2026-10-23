// 메모리 저장소(웹 데모용). SQLite 저장소와 같은 규칙으로 동작하고,
// snapshot()으로 꺼낸 값을 다음에 생성자에 넣어 이어 쓸 수 있습니다(브라우저 저장소에 보관).

import type { ListingRow, NewPurchase, PurchasePatch, PurchaseRow, PurchaseStatus, Repository } from "./types.ts";

export interface MemorySnapshot {
  state: Record<string, string>;
  listings: ListingRow[];
  purchases: PurchaseRow[];
}

export class MemoryStore implements Repository {
  private data: MemorySnapshot;
  /** 바뀔 때마다 부릅니다(저장용) */
  onChange?: () => void;

  constructor(snapshot?: MemorySnapshot) {
    this.data = structuredClone(snapshot ?? { state: {}, listings: [], purchases: [] });
  }

  snapshot(): MemorySnapshot {
    return structuredClone(this.data);
  }

  getState(key: string): string | null {
    return this.data.state[key] ?? null;
  }

  setState(key: string, value: string): void {
    this.data.state[key] = value;
    this.onChange?.();
  }

  getListing(sourceKey: string, market: string): ListingRow | null {
    return copy(this.data.listings.find((l) => l.sourceKey === sourceKey && l.market === market));
  }

  saveListing(l: Omit<ListingRow, "createdAt">): void {
    const i = this.data.listings.findIndex((x) => x.sourceKey === l.sourceKey && x.market === l.market);
    if (i >= 0) this.data.listings[i] = { ...this.data.listings[i], ...l };
    else this.data.listings.push({ ...l, createdAt: now() });
    this.onChange?.();
  }

  findListingByMarketProduct(market: string, ids: string[]): ListingRow | null {
    for (const id of ids) {
      const l = this.data.listings.find((x) => x.market === market && (x.marketProductId === id || x.channelProductId === id));
      if (l) return copy(l);
    }
    return null;
  }

  getPurchase(market: string, lineId: string): PurchaseRow | null {
    return copy(this.find(market, lineId));
  }

  insertPurchase(p: NewPurchase): boolean {
    if (this.find(p.market, p.lineId)) return false;
    const t = now();
    this.data.purchases.push({ ...p, supplierOrderNo: null, createdAt: t, updatedAt: t });
    this.onChange?.();
    return true;
  }

  updatePurchase(market: string, lineId: string, patch: PurchasePatch): void {
    const p = this.find(market, lineId);
    if (!p) return;
    p.status = patch.status;
    p.supplierOrderNo = patch.supplierOrderNo ?? p.supplierOrderNo;
    p.message = patch.message ?? null;
    p.updatedAt = now();
    this.onChange?.();
  }

  listPurchases(status?: PurchaseStatus): PurchaseRow[] {
    return this.data.purchases.filter((p) => !status || p.status === status).map((p) => ({ ...p }));
  }

  private find(market: string, lineId: string): PurchaseRow | undefined {
    return this.data.purchases.find((p) => p.market === market && p.lineId === lineId);
  }
}

const now = () => new Date().toISOString();
const copy = <T extends object>(v: T | undefined): T | null => (v ? { ...v } : null);
