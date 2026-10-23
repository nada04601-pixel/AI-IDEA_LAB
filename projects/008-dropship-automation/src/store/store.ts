import { mkdirSync } from "node:fs";
import { dirname } from "node:path";
import { DatabaseSync } from "node:sqlite";

/**
 * 발주 상태
 * - ordering: 공급처에 발주를 보내기 직전에 기록. 이 상태로 남아 있으면 응답 전에 멈춘 것이라 unknown으로 봅니다
 * - ordered: 공급처 발주 완료, 판매처 발주 확인 전(다음 실행 때 발주 확인을 다시 시도)
 * - confirmed: 판매처 발주 확인까지 끝
 * - held: 안전장치에 걸려 발주하지 않음(공급가 상승, 역마진, 매핑 실패, 주소 문제 등)
 * - failed: 공급처가 거절해 발주되지 않음(재고 없음 등)
 * - unknown: 공급처에 주문서가 만들어졌는지 알 수 없음. 도매매 사이트에서 확인해야 함
 * - pending: 일시적인 이유(실행당 발주 한도, 공급처 조회 실패)로 미룸. 다음 실행 때 자동으로 다시 처리
 * - approved: 사람이 held/failed/unknown을 확인하고 다시 진행하라고 한 줄. 다음 실행 때 안전장치 없이 발주
 */
export type PurchaseStatus = "ordering" | "ordered" | "confirmed" | "held" | "failed" | "unknown" | "pending" | "approved";

export interface PurchaseRow {
  market: string;
  lineId: string;
  orderId: string;
  sourceKey: string;
  optionCode: string;
  quantity: number;
  status: PurchaseStatus;
  supplierOrderNo: string | null;
  message: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface ListingRow {
  sourceKey: string;
  market: string;
  marketProductId: string;
  channelProductId: string | null;
  cost: number;
  salePrice: number;
  title: string;
  createdAt: string;
}

export class Store {
  private db: DatabaseSync;

  constructor(path: string) {
    if (path !== ":memory:") mkdirSync(dirname(path), { recursive: true });
    this.db = new DatabaseSync(path);
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS listings (
        source_key TEXT NOT NULL, market TEXT NOT NULL,
        market_product_id TEXT NOT NULL, channel_product_id TEXT,
        cost INTEGER NOT NULL, sale_price INTEGER NOT NULL, title TEXT NOT NULL,
        created_at TEXT NOT NULL,
        PRIMARY KEY (source_key, market)
      );
      CREATE TABLE IF NOT EXISTS purchases (
        market TEXT NOT NULL, line_id TEXT NOT NULL, order_id TEXT NOT NULL,
        source_key TEXT NOT NULL, option_code TEXT NOT NULL, quantity INTEGER NOT NULL,
        status TEXT NOT NULL, supplier_order_no TEXT, message TEXT,
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
        PRIMARY KEY (market, line_id)
      );
      CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT NOT NULL);
    `);
  }

  close(): void {
    this.db.close();
  }

  getState(key: string): string | null {
    const row = this.db.prepare("SELECT value FROM state WHERE key = ?").get(key) as { value: string } | undefined;
    return row?.value ?? null;
  }

  setState(key: string, value: string): void {
    this.db.prepare("INSERT INTO state (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value").run(key, value);
  }

  getListing(sourceKey: string, market: string): ListingRow | null {
    const r = this.db.prepare("SELECT * FROM listings WHERE source_key = ? AND market = ?").get(sourceKey, market) as
      | Record<string, unknown>
      | undefined;
    return r ? toListing(r) : null;
  }

  saveListing(l: Omit<ListingRow, "createdAt">): void {
    this.db
      .prepare(
        `INSERT INTO listings (source_key, market, market_product_id, channel_product_id, cost, sale_price, title, created_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?)
         ON CONFLICT(source_key, market) DO UPDATE SET market_product_id = excluded.market_product_id,
           channel_product_id = excluded.channel_product_id, cost = excluded.cost,
           sale_price = excluded.sale_price, title = excluded.title`,
      )
      .run(l.sourceKey, l.market, l.marketProductId, l.channelProductId, l.cost, l.salePrice, l.title, now());
  }

  /** 판매처 상품번호로 등록 기록 찾기(주문에 판매자 관리 코드가 비어 있을 때) */
  findListingByMarketProduct(market: string, ids: string[]): ListingRow | null {
    for (const id of ids) {
      const r = this.db
        .prepare("SELECT * FROM listings WHERE market = ? AND (market_product_id = ? OR channel_product_id = ?)")
        .get(market, id, id) as Record<string, unknown> | undefined;
      if (r) return toListing(r);
    }
    return null;
  }

  getPurchase(market: string, lineId: string): PurchaseRow | null {
    const r = this.db.prepare("SELECT * FROM purchases WHERE market = ? AND line_id = ?").get(market, lineId) as
      | Record<string, unknown>
      | undefined;
    return r ? toPurchase(r) : null;
  }

  /** 새 발주 줄을 만듭니다. 이미 있으면 false(다른 실행이 먼저 잡음) */
  insertPurchase(p: Pick<PurchaseRow, "market" | "lineId" | "orderId" | "sourceKey" | "optionCode" | "quantity" | "status" | "message">): boolean {
    const t = now();
    const res = this.db
      .prepare(
        `INSERT OR IGNORE INTO purchases (market, line_id, order_id, source_key, option_code, quantity, status, message, created_at, updated_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      )
      .run(p.market, p.lineId, p.orderId, p.sourceKey, p.optionCode, p.quantity, p.status, p.message, t, t);
    return Number(res.changes) > 0;
  }

  updatePurchase(market: string, lineId: string, patch: { status: PurchaseStatus; supplierOrderNo?: string; message?: string | null }): void {
    this.db
      .prepare(
        `UPDATE purchases SET status = ?, supplier_order_no = COALESCE(?, supplier_order_no), message = ?, updated_at = ?
         WHERE market = ? AND line_id = ?`,
      )
      .run(patch.status, patch.supplierOrderNo ?? null, patch.message ?? null, now(), market, lineId);
  }

  listPurchases(status?: PurchaseStatus): PurchaseRow[] {
    const rows = (status
      ? this.db.prepare("SELECT * FROM purchases WHERE status = ? ORDER BY created_at").all(status)
      : this.db.prepare("SELECT * FROM purchases ORDER BY created_at").all()) as Record<string, unknown>[];
    return rows.map(toPurchase);
  }
}

const now = () => new Date().toISOString();

function toListing(r: Record<string, unknown>): ListingRow {
  return {
    sourceKey: String(r.source_key),
    market: String(r.market),
    marketProductId: String(r.market_product_id),
    channelProductId: r.channel_product_id == null ? null : String(r.channel_product_id),
    cost: Number(r.cost),
    salePrice: Number(r.sale_price),
    title: String(r.title),
    createdAt: String(r.created_at),
  };
}

function toPurchase(r: Record<string, unknown>): PurchaseRow {
  return {
    market: String(r.market),
    lineId: String(r.line_id),
    orderId: String(r.order_id),
    sourceKey: String(r.source_key),
    optionCode: String(r.option_code),
    quantity: Number(r.quantity),
    status: r.status as PurchaseStatus,
    supplierOrderNo: r.supplier_order_no == null ? null : String(r.supplier_order_no),
    message: r.message == null ? null : String(r.message),
    createdAt: String(r.created_at),
    updatedAt: String(r.updated_at),
  };
}
