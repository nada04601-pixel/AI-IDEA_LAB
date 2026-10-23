// 샌드박스 판매처·도매처의 상태. 사람이 열어 보고 고칠 수 있게 JSON으로 둡니다.
// catalog.json(도매처 상품), market.json(판매처 상품·주문), supplier-orders.json(도매처 주문서)
// 어디에 둘지는 FileBackend가 정합니다: CLI는 <dataDir>/fake/ 폴더(node-files.ts), 웹 데모는 브라우저 저장소.

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

/** 이름 붙은 JSON 문서를 읽고 쓰는 곳 */
export interface FileBackend {
  /** 사람에게 보여 줄 위치(폴더 경로 등) */
  readonly location: string;
  read(name: string): string | null;
  write(name: string, text: string): void;
  clear(): void;
}

export class SandboxFiles {
  private backend: FileBackend;

  constructor(backend: FileBackend) {
    this.backend = backend;
  }

  get location(): string {
    return this.backend.location;
  }

  /** 도매처 상품. 없으면 기본 상품으로 만듭니다 */
  catalog(): CatalogItem[] {
    if (this.backend.read("catalog.json") == null) this.saveCatalog(SANDBOX_CATALOG);
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

  /** 샌드박스 상태를 모두 지웁니다(다음에 읽을 때 기본 상품으로 다시 시작) */
  reset(): void {
    this.backend.clear();
  }

  private read<T>(name: string, fallback: T): T {
    const text = this.backend.read(name);
    return text == null ? fallback : (JSON.parse(text) as T);
  }

  private write(name: string, value: unknown): void {
    this.backend.write(name, `${JSON.stringify(value, null, 2)}\n`);
  }
}

/** 메모리에만 두는 곳. save를 주면 바뀔 때마다 전체를 넘깁니다(웹 데모는 브라우저 저장소에 보관) */
export function memoryBackend(initial: Record<string, string> = {}, save?: (all: Record<string, string>) => void): FileBackend {
  let docs = { ...initial };
  return {
    location: "브라우저 저장소",
    read: (name) => docs[name] ?? null,
    write: (name, text) => {
      docs[name] = text;
      save?.({ ...docs });
    },
    clear: () => {
      docs = {};
      save?.({});
    },
  };
}
