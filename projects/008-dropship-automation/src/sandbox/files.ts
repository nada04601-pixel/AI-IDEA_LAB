// 샌드박스 판매처·도매처의 상태. 사람이 열어 보고 고칠 수 있게 JSON 파일로 둡니다.
// <dataDir>/fake/ 아래 catalog.json(도매처 상품), market.json(판매처 상품·주문), supplier-orders.json(도매처 주문서)

import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import type { Listing, Recipient } from "../core/types.ts";
import { SANDBOX_CATALOG, type CatalogItem } from "./catalog.ts";

export interface SandboxProduct {
  productId: string;
  sourceKey: string;
  title: string;
  salePrice: number;
  shippingFee: number;
  stock: number;
  optionGroups: string[];
  options: Listing["options"];
  registeredAt: string;
}

/**
 * 판매처 주문 줄 상태(스마트스토어를 흉내 냄)
 * - PAYED: 결제 완료, 발주 확인 전
 * - PLACED: 발주 확인함
 * - CANCEL_REQUEST: 고객이 취소 요청
 */
export type SandboxOrderStatus = "PAYED" | "PLACED" | "CANCEL_REQUEST";

export interface SandboxOrder {
  lineId: string;
  orderId: string;
  productId: string;
  sourceKey: string;
  productName: string;
  optionCode: string;
  optionText: string;
  quantity: number;
  paidAmount: number;
  recipient: Recipient;
  paidAt: string;
  status: SandboxOrderStatus;
}

export interface SandboxPurchase {
  supplierOrderNo: string;
  productId: string;
  optionCode: string;
  quantity: number;
  recipient: Recipient;
  storeName: string;
  sellerNote: string;
  orderedAt: string;
}

interface MarketFile {
  products: SandboxProduct[];
  orders: SandboxOrder[];
}

export class SandboxFiles {
  readonly dir: string;

  constructor(dataDir: string) {
    this.dir = join(dataDir, "fake");
  }

  /** 도매처 상품. 파일이 없으면 기본 상품으로 만듭니다 */
  catalog(): CatalogItem[] {
    if (!existsSync(this.path("catalog.json"))) this.saveCatalog(SANDBOX_CATALOG);
    return this.read("catalog.json", []);
  }

  saveCatalog(items: CatalogItem[]): void {
    this.write("catalog.json", items);
  }

  market(): MarketFile {
    return this.read("market.json", { products: [], orders: [] });
  }

  saveMarket(m: MarketFile): void {
    this.write("market.json", m);
  }

  purchases(): SandboxPurchase[] {
    return this.read("supplier-orders.json", []);
  }

  savePurchases(list: SandboxPurchase[]): void {
    this.write("supplier-orders.json", list);
  }

  /** 샌드박스 파일을 모두 지웁니다(다음에 읽을 때 기본 상품으로 다시 시작) */
  reset(): void {
    rmSync(this.dir, { recursive: true, force: true });
  }

  private path(name: string): string {
    return join(this.dir, name);
  }

  private read<T>(name: string, fallback: T): T {
    const p = this.path(name);
    return existsSync(p) ? (JSON.parse(readFileSync(p, "utf8")) as T) : fallback;
  }

  private write(name: string, value: unknown): void {
    mkdirSync(this.dir, { recursive: true });
    writeFileSync(this.path(name), `${JSON.stringify(value, null, 2)}\n`);
  }
}
