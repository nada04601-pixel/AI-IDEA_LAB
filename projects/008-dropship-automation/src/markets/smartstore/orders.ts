// 네이버 커머스API 주문 응답 → 공통 주문 줄. 순수 함수.

import type { MarketOrderLine } from "../../core/types.ts";

export const MARKET_ID = "smartstore";

type Json = Record<string, any>;
const str = (v: unknown) => (v == null ? "" : String(v)).trim();

/** 커머스API 날짜 형식(한국 시간): 2026-10-23T09:00:00.000+09:00 */
export function toKstIso(d: Date): string {
  const k = new Date(d.getTime() + 9 * 3600_000);
  return k.toISOString().replace("Z", "+09:00");
}

/**
 * 조회 기간을 24시간 이하 구간으로 나눕니다(변경 상품 주문 내역 API는 한 번에 24시간까지).
 */
export function splitWindows(since: Date, until: Date, maxMs = 24 * 3600_000): [Date, Date][] {
  const out: [Date, Date][] = [];
  for (let t = since.getTime(); t < until.getTime(); t += maxMs) {
    out.push([new Date(t), new Date(Math.min(t + maxMs, until.getTime()))]);
  }
  return out;
}

/** 상품 주문 상세 내역(POST /v1/pay-order/seller/product-orders/query) 한 건 → 주문 줄 */
export function toOrderLine(item: Json): MarketOrderLine {
  const order = item.order ?? {};
  const po = item.productOrder ?? {};
  const addr = po.shippingAddress ?? {};

  let skipReason: string | undefined;
  if (str(po.productOrderStatus) !== "PAYED") skipReason = `주문 상태 ${str(po.productOrderStatus)}`;
  else if (str(po.placeOrderStatus) && str(po.placeOrderStatus) !== "NOT_YET") skipReason = `발주 상태 ${str(po.placeOrderStatus)}`;
  else if (str(po.claimType)) skipReason = `클레임 ${str(po.claimType)} ${str(po.claimStatus)}`;
  else if (str(addr.addressType) === "FOREIGN") skipReason = "해외 배송지";
  else if (!str(addr.baseAddress)) skipReason = "배송지 없음(선물 수락 대기 등)";

  return {
    market: MARKET_ID,
    lineId: str(po.productOrderId),
    orderId: str(order.orderId),
    productName: str(po.productName),
    optionText: str(po.productOption),
    sourceKey: str(po.sellerProductCode),
    marketProductIds: [str(po.originalProductId), str(po.productId)].filter(Boolean),
    optionCode: str(po.optionManageCode),
    quantity: Number(po.remainQuantity ?? po.quantity) || 0,
    paidAmount: Number(po.remainPaymentAmount ?? po.totalPaymentAmount ?? 0),
    recipient: {
      name: str(addr.name),
      zipCode: str(addr.zipCode),
      address1: str(addr.baseAddress),
      address2: str(addr.detailedAddress),
      phone: str(addr.tel1),
      phone2: str(addr.tel2),
      memo: str(po.shippingMemo),
      customsCode: str(po.individualCustomUniqueCode),
    },
    skipReason,
  };
}
