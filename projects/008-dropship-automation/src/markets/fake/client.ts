// 샌드박스 판매처. 등록한 상품과 주문은 <dataDir>/fake/market.json에 있고,
// 주문은 `fake order` 명령으로 만듭니다(고객 대신 결제 완료 주문을 넣음).

import type { Listing, MarketAdapter, MarketOrderLine, MarketProductRef } from "../../core/types.ts";
import type { SandboxFiles, SandboxOrder } from "../../sandbox/files.ts";

export const FAKE_MARKET_ID = "fake";

export class FakeMarket implements MarketAdapter {
  readonly id = FAKE_MARKET_ID;
  private files: SandboxFiles;

  constructor(files: SandboxFiles) {
    this.files = files;
  }

  async uploadImages(urls: string[]): Promise<string[]> {
    return urls;
  }

  async registerProduct(listing: Listing): Promise<MarketProductRef> {
    const m = this.files.market();
    const productId = String(9_000_001 + m.products.length);
    m.products.push({
      productId,
      sourceKey: listing.sourceKey,
      title: listing.title,
      salePrice: listing.salePrice,
      shippingFee: listing.shippingFee,
      stock: listing.stock,
      optionGroups: listing.optionGroups,
      options: listing.options,
      registeredAt: new Date().toISOString(),
    });
    this.files.saveMarket(m);
    return { productId };
  }

  async fetchPaidOrders(since: Date, until: Date): Promise<MarketOrderLine[]> {
    return this.files
      .market()
      .orders.filter((o) => {
        const t = new Date(o.paidAt).getTime();
        // 끝 시각도 포함: 주문을 넣자마자 돌려도 빠지지 않게(겹쳐 읽은 줄은 저장소가 걸러 냄)
        return t >= since.getTime() && t <= until.getTime();
      })
      .map(toOrderLine);
  }

  async getOrderLines(lineIds: string[]): Promise<MarketOrderLine[]> {
    return this.files
      .market()
      .orders.filter((o) => lineIds.includes(o.lineId))
      .map(toOrderLine);
  }

  async confirmOrders(lineIds: string[]): Promise<{ ok: string[]; failed: { lineId: string; message: string }[] }> {
    const m = this.files.market();
    const ok: string[] = [];
    const failed: { lineId: string; message: string }[] = [];
    for (const id of lineIds) {
      const o = m.orders.find((x) => x.lineId === id);
      if (!o) failed.push({ lineId: id, message: "주문 없음" });
      else if (o.status === "CANCEL_REQUEST") failed.push({ lineId: id, message: "취소 요청된 주문" });
      else {
        o.status = "PLACED";
        ok.push(id);
      }
    }
    this.files.saveMarket(m);
    return { ok, failed };
  }
}

/** 스마트스토어 어댑터와 같은 기준으로 자동 처리 대상이 아닌 줄을 표시합니다 */
function toOrderLine(o: SandboxOrder): MarketOrderLine {
  let skipReason: string | undefined;
  if (o.status === "PLACED") skipReason = "발주 상태 PLACED";
  else if (o.status === "CANCEL_REQUEST") skipReason = "클레임 CANCEL REQUEST";
  return {
    market: FAKE_MARKET_ID,
    lineId: o.lineId,
    orderId: o.orderId,
    productName: o.productName,
    optionText: o.optionText,
    sourceKey: o.sourceKey,
    marketProductIds: [o.productId],
    optionCode: o.optionCode,
    quantity: o.quantity,
    paidAmount: o.paidAmount,
    recipient: o.recipient,
    skipReason,
  };
}
