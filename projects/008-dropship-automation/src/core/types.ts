// 공급처(도매매 등)와 판매처(스마트스토어·쿠팡 등)를 잇는 공통 모델.
// 새 공급처·판매처는 아래 인터페이스만 구현하면 소싱·등록·주문 처리 흐름을 그대로 씁니다.

/** 공급처 상품의 주문 옵션 하나(조합이 끝난 최종 선택지) */
export interface SupplierOption {
  /** 공급처에 발주할 때 쓰는 옵션 코드. 옵션 없는 상품은 공급처 규칙에 맞는 기본값(도매매는 "00") */
  code: string;
  /** 그룹 순서대로의 옵션값. 예: ["빨강", "L"] */
  values: string[];
  /** 기본 공급가에 더해지는 금액 */
  extraCost: number;
  stock: number;
}

export interface SupplierProduct {
  supplier: string;
  id: string;
  title: string;
  /** 1개 공급가(원) */
  cost: number;
  /** 소비자에게 받는 걸로 가정한 배송비(원). 무료배송이면 0 */
  shippingFee: number;
  /** 공급처 배송비 부담 방식. 발주할 때 그대로 돌려줍니다 */
  shippingPayType: string;
  /** 제주·도서산간 추가 배송비(모르면 0) */
  extraShippingFee: { jeju: number; islands: number };
  /** 한 번에 주문해야 하는 묶음 수량 */
  orderUnit: number;
  stock: number;
  images: string[];
  detailHtml: string;
  /** 옵션 그룹 이름. 옵션이 없으면 빈 배열 */
  optionGroups: string[];
  options: SupplierOption[];
  keywords: string[];
  manufacturer: string;
  model: string;
  /** 원산지(공급처 표기 그대로) */
  origin: string;
  brand: string;
  adultOnly: boolean;
  category: { code: string; name: string; path: string[] };
  url: string;
  /** 상품정보제공고시 등 공급처가 준 추가 정보 */
  notice: { name: string; value: string }[];
  /** 자동 위탁판매로 다룰 수 없는 상품이면 그 이유(착불 배송, 지원하지 않는 옵션 형식 등) */
  unsupportedReason?: string;
}

export interface SupplierSearchQuery {
  keyword?: string;
  category?: string;
  minPrice?: number;
  maxPrice?: number;
  page?: number;
  size?: number;
  sort?: string;
}

export interface SupplierSearchItem {
  id: string;
  title: string;
  cost: number;
  thumb: string;
  orderUnit: number;
  adultOnly: boolean;
  url: string;
}

export interface Recipient {
  name: string;
  zipCode: string;
  address1: string;
  address2: string;
  phone: string;
  phone2: string;
  memo: string;
  /** 해외직배송 상품 통관고유부호 */
  customsCode: string;
}

export interface PurchaseRequest {
  productId: string;
  optionCode: string;
  quantity: number;
  shippingPayType: string;
  recipient: Recipient;
  /** 송장·박스에 찍힐 쇼핑몰 이름 */
  storeName: string;
  /** 공급사에 남길 메모(판매처 주문번호 등) */
  sellerNote: string;
}

export interface PurchaseResult {
  supplierOrderNo: string;
}

export interface SupplierAdapter {
  readonly id: string;
  search(query: SupplierSearchQuery): Promise<SupplierSearchItem[]>;
  getProduct(id: string): Promise<SupplierProduct>;
  purchase(req: PurchaseRequest): Promise<PurchaseResult>;
}

/** 판매처에 올릴 상품. 공급처 상품에 판매가·카테고리를 정한 결과 */
export interface Listing {
  /** 판매처 상품의 판매자 관리 코드에 넣어, 주문이 들어왔을 때 공급처 상품을 찾는 열쇠 */
  sourceKey: string;
  title: string;
  salePrice: number;
  shippingFee: number;
  extraShippingFee: { jeju: number; islands: number };
  stock: number;
  images: string[];
  detailHtml: string;
  optionGroups: string[];
  options: { code: string; values: string[]; extraPrice: number; stock: number }[];
  marketCategoryId: string;
  manufacturer: string;
  model: string;
  origin: string;
  brand: string;
  keywords: string[];
  adultOnly: boolean;
  notice: { name: string; value: string }[];
}

export interface MarketProductRef {
  productId: string;
  /** 판매처가 따로 주는 번호(스마트스토어 채널 상품번호 등) */
  channelProductId?: string;
  /** 등록은 됐지만 알려야 할 것(범위를 벗어나 뺀 옵션 등) */
  warnings?: string[];
}

/** 판매처 주문의 상품 한 줄(스마트스토어의 상품주문 1건) */
export interface MarketOrderLine {
  market: string;
  /** 판매처에서 이 줄을 가리키는 번호. 중복 발주를 막는 기준 */
  lineId: string;
  orderId: string;
  productName: string;
  optionText: string;
  /** 판매자 관리 코드. 비어 있으면 marketProductIds로 저장소에서 찾습니다 */
  sourceKey: string;
  marketProductIds: string[];
  optionCode: string;
  quantity: number;
  /** 고객이 낸 상품 금액 합계(할인 후) */
  paidAmount: number;
  recipient: Recipient;
  /** 이미 발주 확인 등을 해서 자동 처리 대상이 아닐 때의 이유 */
  skipReason?: string;
}

export interface MarketAdapter {
  readonly id: string;
  /** 상품 이미지를 판매처 서버로 올리고 판매처에서 쓸 주소를 돌려받습니다 */
  uploadImages(urls: string[]): Promise<string[]>;
  registerProduct(listing: Listing): Promise<MarketProductRef>;
  /** since~until 사이에 결제 완료된 주문 줄 */
  fetchPaidOrders(since: Date, until: Date): Promise<MarketOrderLine[]>;
  /** 주문 줄 번호로 다시 읽기(보류했다가 승인한 줄 처리용) */
  getOrderLines(lineIds: string[]): Promise<MarketOrderLine[]>;
  /** 공급처 발주를 마친 주문을 판매처에 "발주 확인"으로 알립니다 */
  confirmOrders(lineIds: string[]): Promise<{ ok: string[]; failed: { lineId: string; message: string }[] }>;
}

/** 판매자 관리 코드 형식: "<공급처>:<상품번호>" */
export function makeSourceKey(supplier: string, productId: string): string {
  return `${supplier}:${productId}`;
}

export function parseSourceKey(key: string): { supplier: string; productId: string } | null {
  const m = /^([a-z0-9_-]+):(.+)$/.exec(key.trim());
  return m ? { supplier: m[1], productId: m[2] } : null;
}
