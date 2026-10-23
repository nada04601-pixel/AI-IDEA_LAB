// 판매처 주문 → 공급처 발주(배송지 입력) → 판매처 발주 확인.
// 판매처·공급처 종류와 상관없이 같은 흐름으로 돕니다.

import type { PurchaseRow, Store } from "../store/store.ts";
import { SupplierError } from "./errors.ts";
import { parseSourceKey, type MarketAdapter, type MarketOrderLine, type SupplierAdapter } from "./types.ts";

export interface FulfillmentPolicy {
  /** 처음 실행할 때 몇 시간 전 주문부터 볼지 */
  lookbackHours: number;
  /** 한 번 실행에 발주할 최대 줄 수(폭주 방지) */
  maxOrdersPerRun: number;
  /** 한 줄 발주 금액(공급가 × 수량 + 배송비)이 이보다 크면 보류 */
  maxOrderAmount: number;
  /** 등록 때보다 공급가가 이 비율 넘게 오르면 보류. 0.05 = 5% */
  costIncreaseTolerance: number;
  /** 고객 결제 금액보다 공급처 발주 금액이 크면 보류 */
  holdOnLoss: boolean;
  /** 송장·박스에 찍힐 쇼핑몰 이름 */
  storeName: string;
}

export interface FulfillmentDeps {
  market: MarketAdapter;
  suppliers: Map<string, SupplierAdapter>;
  store: Store;
  policy: FulfillmentPolicy;
  /** false면 아무것도 바꾸지 않고 무엇을 할지 보여 주기만 합니다 */
  live: boolean;
  log: (msg: string) => void;
  now?: Date;
}

export interface FulfillmentReport {
  ordered: { lineId: string; supplierOrderNo: string }[];
  wouldOrder: { lineId: string; summary: string }[];
  held: { lineId: string; reason: string }[];
  failed: { lineId: string; reason: string }[];
  unknown: { lineId: string; reason: string }[];
  confirmed: string[];
  confirmFailed: { lineId: string; reason: string }[];
  skipped: { lineId: string; reason: string }[];
}

/** 커서를 이만큼 겹쳐 읽어 경계에서 빠지는 주문이 없게 합니다(중복은 저장소가 걸러 냄) */
const OVERLAP_MS = 10 * 60_000;

export async function runFulfillment(deps: FulfillmentDeps): Promise<FulfillmentReport> {
  const { market, store, policy, live, log } = deps;
  const now = deps.now ?? new Date();
  const report: FulfillmentReport = {
    ordered: [], wouldOrder: [], held: [], failed: [], unknown: [], confirmed: [], confirmFailed: [], skipped: [],
  };

  // 지난 실행이 공급처 응답 전에 멈춘 줄: 주문서가 생겼을 수 있으니 사람이 확인
  for (const p of store.listPurchases("ordering")) {
    const reason = "지난 실행이 공급처 응답 전에 멈춤. 공급처에서 주문 여부를 확인하세요";
    if (live) store.updatePurchase(p.market, p.lineId, { status: "unknown", message: reason });
    report.unknown.push({ lineId: p.lineId, reason });
  }

  const cursorKey = `${market.id}.orders.cursor`;
  const saved = store.getState(cursorKey);
  const since = saved ? new Date(new Date(saved).getTime() - OVERLAP_MS) : new Date(now.getTime() - policy.lookbackHours * 3600_000);
  log(`주문 조회: ${since.toISOString()} ~ ${now.toISOString()}`);
  const lines = await market.fetchPaidOrders(since, now);

  // 지난번에 미룬 줄(pending)과 사람이 승인한 줄(approved)은 주문 내역을 다시 읽어 처리합니다
  const carried = [...store.listPurchases("pending"), ...store.listPurchases("approved")].filter((p) => p.market === market.id);
  const approvedIds = new Set(carried.filter((p) => p.status === "approved").map((p) => p.lineId));
  const extra = carried.length > 0 ? await market.getOrderLines(carried.map((p) => p.lineId)) : [];
  const byId = new Map<string, MarketOrderLine>();
  for (const l of [...lines, ...extra]) byId.set(l.lineId, l);

  const toConfirm = store
    .listPurchases("ordered")
    .filter((p) => p.market === market.id)
    .map((p) => p.lineId);
  let orderedThisRun = 0;

  for (const line of byId.values()) {
    const existing = store.getPurchase(market.id, line.lineId);
    const isApproved = approvedIds.has(line.lineId);
    if (existing && existing.status !== "pending" && !isApproved) continue;
    if (line.skipReason) {
      report.skipped.push({ lineId: line.lineId, reason: line.skipReason });
      if (existing && live) store.updatePurchase(market.id, line.lineId, { status: "held", message: line.skipReason });
      continue;
    }
    const record = (status: PurchaseRow["status"], message: string | null, sourceKey = line.sourceKey) => {
      if (!live) return;
      if (existing) store.updatePurchase(market.id, line.lineId, { status, message });
      else store.insertPurchase({ market: market.id, lineId: line.lineId, orderId: line.orderId, sourceKey, optionCode: line.optionCode, quantity: line.quantity, status, message });
    };
    const hold = (reason: string) => {
      record("held", reason);
      report.held.push({ lineId: line.lineId, reason });
    };
    /** 일시적인 문제: 다음 실행에서 자동으로 다시 시도 */
    const postpone = (reason: string) => {
      record("pending", reason);
      report.skipped.push({ lineId: line.lineId, reason });
    };

    if (orderedThisRun >= policy.maxOrdersPerRun) {
      postpone("이번 실행 발주 한도 도달(다음 실행에 처리)");
      continue;
    }

    const listing = line.sourceKey
      ? store.getListing(line.sourceKey, market.id)
      : store.findListingByMarketProduct(market.id, line.marketProductIds);
    const sourceKey = line.sourceKey || listing?.sourceKey || "";
    const src = parseSourceKey(sourceKey);
    const supplier = src ? deps.suppliers.get(src.supplier) : undefined;
    if (!src || !supplier) {
      hold(`공급처 상품을 찾을 수 없음(판매자 관리 코드 "${sourceKey}")`);
      continue;
    }
    if (line.quantity < 1) {
      hold(`수량 ${line.quantity}`);
      continue;
    }

    let product;
    try {
      product = await supplier.getProduct(src.productId);
    } catch (e) {
      postpone(`공급처 상품 조회 실패: ${(e as Error).message}`);
      continue;
    }
    const option = product.options.find((o) => o.code === line.optionCode);
    if (product.options.length > 0 && !option) {
      hold(`공급처에 옵션 "${line.optionCode}"(${line.optionText})이 없음`);
      continue;
    }
    const unitCost = product.cost + (option?.extraCost ?? 0);
    const stock = option ? option.stock : product.stock;
    // 공급처가 묶음 단위로만 판다면 그 배수로 올려 주문합니다
    const quantity = Math.ceil(line.quantity / product.orderUnit) * product.orderUnit;
    const amount = unitCost * quantity + product.shippingFee;

    if (!isApproved) {
      if (stock < quantity) {
        hold(`공급처 재고 ${stock}개 < 주문 ${quantity}개`);
        continue;
      }
      if (listing && product.cost > listing.cost * (1 + policy.costIncreaseTolerance)) {
        hold(`공급가가 ${listing.cost}원 → ${product.cost}원으로 오름`);
        continue;
      }
      if (amount > policy.maxOrderAmount) {
        hold(`발주 금액 ${amount}원이 한도 ${policy.maxOrderAmount}원 초과`);
        continue;
      }
      if (policy.holdOnLoss && line.paidAmount > 0 && amount > line.paidAmount) {
        hold(`역마진: 발주 ${amount}원 > 고객 결제 ${line.paidAmount}원`);
        continue;
      }
    }

    const req = {
      productId: src.productId,
      optionCode: line.optionCode,
      quantity,
      shippingPayType: product.shippingPayType,
      recipient: line.recipient,
      storeName: policy.storeName,
      sellerNote: `${market.id} ${line.orderId}`,
    };
    const summary = `${product.title} [${line.optionText || "옵션 없음"}] × ${req.quantity} → ${line.recipient.name} ${line.recipient.address1} (발주 약 ${amount}원)`;
    if (!live) {
      report.wouldOrder.push({ lineId: line.lineId, summary });
      continue;
    }

    record("ordering", null, sourceKey);
    orderedThisRun++;
    try {
      const r = await supplier.purchase(req);
      store.updatePurchase(market.id, line.lineId, { status: "ordered", supplierOrderNo: r.supplierOrderNo });
      report.ordered.push({ lineId: line.lineId, supplierOrderNo: r.supplierOrderNo });
      toConfirm.push(line.lineId);
      log(`발주 완료 ${line.lineId} → 공급처 주문 ${r.supplierOrderNo}: ${summary}`);
    } catch (e) {
      const msg = (e as Error).message;
      if (e instanceof SupplierError && !e.orderMayExist) {
        store.updatePurchase(market.id, line.lineId, { status: "failed", message: msg });
        report.failed.push({ lineId: line.lineId, reason: msg });
      } else {
        const reason = `응답 불명(${msg}). 공급처에서 주문 여부를 확인하세요`;
        store.updatePurchase(market.id, line.lineId, { status: "unknown", message: reason });
        report.unknown.push({ lineId: line.lineId, reason });
      }
    }
  }

  if (live && toConfirm.length > 0) {
    try {
      const r = await market.confirmOrders(toConfirm);
      for (const id of r.ok) store.updatePurchase(market.id, id, { status: "confirmed" });
      for (const f of r.failed) store.updatePurchase(market.id, f.lineId, { status: "ordered", message: `발주 확인 실패: ${f.message}` });
      report.confirmed.push(...r.ok);
      report.confirmFailed.push(...r.failed.map((f) => ({ lineId: f.lineId, reason: f.message })));
    } catch (e) {
      // 다음 실행 때 ordered 줄을 다시 확인합니다
      report.confirmFailed.push(...toConfirm.map((lineId) => ({ lineId, reason: (e as Error).message })));
    }
  }

  if (live) store.setState(cursorKey, now.toISOString());
  return report;
}
