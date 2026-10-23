// 샌드박스 도매처. 실제 키 없이 소싱·발주 흐름을 끝까지 돌려 보기 위한 가짜 공급처입니다.
// 상품은 <dataDir>/fake/catalog.json, 발주한 주문서는 supplier-orders.json에 쌓입니다.

import { SupplierError } from "../../core/errors.ts";
import type { PurchaseRequest, PurchaseResult, SupplierAdapter, SupplierProduct, SupplierSearchItem, SupplierSearchQuery } from "../../core/types.ts";
import { FAKE_SUPPLIER_ID, toSupplierProduct } from "../../sandbox/catalog.ts";
import type { SandboxFiles } from "../../sandbox/files.ts";

export class FakeSupplier implements SupplierAdapter {
  readonly id = FAKE_SUPPLIER_ID;
  private files: SandboxFiles;

  constructor(files: SandboxFiles) {
    this.files = files;
  }

  async search(q: SupplierSearchQuery): Promise<SupplierSearchItem[]> {
    const size = q.size ?? 50;
    const page = q.page ?? 1;
    return this.files
      .catalog()
      .map(toSupplierProduct)
      .filter((p) => !q.keyword || p.title.includes(q.keyword))
      .filter((p) => (q.minPrice == null || p.cost >= q.minPrice) && (q.maxPrice == null || p.cost <= q.maxPrice))
      .slice((page - 1) * size, page * size)
      .map((p) => ({ id: p.id, title: p.title, cost: p.cost, thumb: p.images[0] ?? "", orderUnit: p.orderUnit, adultOnly: p.adultOnly, url: p.url }));
  }

  async getProduct(id: string): Promise<SupplierProduct> {
    const item = this.files.catalog().find((c) => c.id === id);
    if (!item) throw new Error(`샌드박스 도매처에 상품 ${id}이(가) 없음`);
    return toSupplierProduct(item);
  }

  /** 주문서를 기록하고 재고를 줄입니다. 상품의 fail 값에 따라 일부러 실패합니다 */
  async purchase(req: PurchaseRequest): Promise<PurchaseResult> {
    const catalog = this.files.catalog();
    const item = catalog.find((c) => c.id === req.productId);
    if (!item) throw new SupplierError("NO_ITEM", `상품 ${req.productId} 없음`);
    if (item.fail === "reject") throw new SupplierError("SOLD_OUT_ERROR", "품절된 상품입니다(샌드박스 fail: reject)");

    const option = item.options?.find((o) => o.code === req.optionCode);
    if (item.options?.length && !option) throw new SupplierError("NO_OPTION", `옵션 ${req.optionCode} 없음`);
    const stock = option ? option.stock : item.stock;
    if (stock < req.quantity) throw new SupplierError("SOLD_OUT_ERROR", `재고 ${stock}개 < 주문 ${req.quantity}개`);
    if (option) option.stock -= req.quantity;
    else item.stock -= req.quantity;
    this.files.saveCatalog(catalog);

    const purchases = this.files.purchases();
    const supplierOrderNo = `F${String(purchases.length + 1).padStart(6, "0")}`;
    purchases.push({ supplierOrderNo, ...pick(req), orderedAt: new Date().toISOString() });
    this.files.savePurchases(purchases);

    // 주문서는 만들어졌는데 응답을 못 받은 상황: 자동으로 다시 보내면 중복 발주가 됩니다
    if (item.fail === "timeout") throw new Error("응답 시간 초과(샌드박스 fail: timeout)");
    return { supplierOrderNo };
  }
}

function pick(r: PurchaseRequest) {
  return { productId: r.productId, optionCode: r.optionCode, quantity: r.quantity, recipient: r.recipient, storeName: r.storeName, sellerNote: r.sellerNote };
}
