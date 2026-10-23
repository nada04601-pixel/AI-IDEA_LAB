// 저장소 모델과 인터페이스. 노드(SQLite)와 브라우저(웹 데모) 저장소가 같은 모양을 따릅니다.

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

/** 소싱·주문 처리 흐름이 쓰는 저장소 */
export interface Repository {
  getState(key: string): string | null;
  setState(key: string, value: string): void;
  getListing(sourceKey: string, market: string): ListingRow | null;
  saveListing(l: Omit<ListingRow, "createdAt">): void;
  /** 판매처 상품번호로 등록 기록 찾기(주문에 판매자 관리 코드가 비어 있을 때) */
  findListingByMarketProduct(market: string, ids: string[]): ListingRow | null;
  getPurchase(market: string, lineId: string): PurchaseRow | null;
  /** 새 발주 줄을 만듭니다. 이미 있으면 false(다른 실행이 먼저 잡음) */
  insertPurchase(p: NewPurchase): boolean;
  updatePurchase(market: string, lineId: string, patch: PurchasePatch): void;
  listPurchases(status?: PurchaseStatus): PurchaseRow[];
}

export type NewPurchase = Pick<PurchaseRow, "market" | "lineId" | "orderId" | "sourceKey" | "optionCode" | "quantity" | "status" | "message">;
export type PurchasePatch = { status: PurchaseStatus; supplierOrderNo?: string; message?: string | null };
