// 샌드박스 판매처에 고객 대신 주문을 넣고 취소하는 도구(cli의 fake 명령).

import type { Recipient } from "../core/types.ts";
import type { SandboxFiles, SandboxOrder } from "./files.ts";

export const SAMPLE_RECIPIENT: Recipient = {
  name: "홍길동",
  zipCode: "06236",
  address1: "서울특별시 강남구 테헤란로 123",
  address2: "4층 401호",
  phone: "010-1234-5678",
  phone2: "",
  memo: "문 앞에 놓아 주세요",
  customsCode: "",
};

export interface NewOrder {
  /** 샌드박스 판매처 상품번호 */
  productId: string;
  /** 옵션 관리 코드. 옵션 상품인데 비우면 첫 옵션 */
  optionCode?: string;
  quantity?: number;
  /** 고객 결제 금액. 비우면 (판매가 + 옵션가) × 수량 + 배송비. 역마진을 만들어 보려면 작게 */
  paidAmount?: number;
  recipient?: Partial<Recipient>;
}

/** 결제 완료 주문 한 줄을 만듭니다 */
export function createOrder(files: SandboxFiles, req: NewOrder): SandboxOrder {
  const m = files.market();
  const product = m.products.find((p) => p.productId === req.productId);
  if (!product) throw new Error(`샌드박스 판매처에 상품 ${req.productId}이(가) 없음(먼저 source --live로 등록하세요)`);
  const option = req.optionCode != null ? product.options.find((o) => o.code === req.optionCode) : product.options[0];
  if (product.options.length > 0 && !option) {
    throw new Error(`옵션 "${req.optionCode}" 없음(있는 옵션: ${product.options.map((o) => o.code).join(", ")})`);
  }
  const quantity = req.quantity ?? 1;
  const n = m.orders.length + 1;
  const order: SandboxOrder = {
    lineId: `L${String(n).padStart(6, "0")}`,
    orderId: `O${String(n).padStart(6, "0")}`,
    productId: product.productId,
    sourceKey: product.sourceKey,
    productName: product.title,
    optionCode: option?.code ?? "",
    optionText: option ? product.optionGroups.map((g, i) => `${g}: ${option.values[i]}`).join(" / ") : "",
    quantity,
    paidAmount: req.paidAmount ?? (product.salePrice + (option?.extraPrice ?? 0)) * quantity + product.shippingFee,
    recipient: { ...SAMPLE_RECIPIENT, ...req.recipient },
    paidAt: new Date().toISOString(),
    status: "PAYED",
  };
  m.orders.push(order);
  files.saveMarket(m);
  return order;
}

/** 고객 취소 요청을 흉내 냅니다(발주 전이면 자동 발주에서 빠짐) */
export function cancelOrder(files: SandboxFiles, lineId: string): SandboxOrder {
  const m = files.market();
  const order = m.orders.find((o) => o.lineId === lineId);
  if (!order) throw new Error(`주문 ${lineId} 없음`);
  order.status = "CANCEL_REQUEST";
  files.saveMarket(m);
  return order;
}
