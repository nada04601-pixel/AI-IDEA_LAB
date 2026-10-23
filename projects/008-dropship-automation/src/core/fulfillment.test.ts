import { describe, expect, it } from "vitest";
import { Store } from "../store/store.ts";
import { SupplierError } from "./errors.ts";
import { runFulfillment, type FulfillmentPolicy } from "./fulfillment.ts";
import type { MarketAdapter, MarketOrderLine, PurchaseRequest, SupplierAdapter, SupplierProduct } from "./types.ts";

const policy: FulfillmentPolicy = {
  lookbackHours: 24,
  maxOrdersPerRun: 10,
  maxOrderAmount: 100000,
  costIncreaseTolerance: 0.05,
  holdOnLoss: true,
  storeName: "테스트스토어",
};

const product: SupplierProduct = {
  supplier: "fake",
  id: "100",
  title: "텀블러",
  cost: 5000,
  shippingFee: 3000,
  shippingPayType: "P",
  extraShippingFee: { jeju: 0, islands: 0 },
  orderUnit: 1,
  stock: 100,
  images: [],
  detailHtml: "",
  optionGroups: ["색상"],
  options: [{ code: "01", values: ["파랑"], extraCost: 500, stock: 10 }],
  keywords: [],
  manufacturer: "",
  model: "",
  origin: "",
  brand: "",
  adultOnly: false,
  category: { code: "", name: "", path: [] },
  url: "",
  notice: [],
};

const line = (id: string, over: Partial<MarketOrderLine> = {}): MarketOrderLine => ({
  market: "fakemarket",
  lineId: id,
  orderId: `O${id}`,
  productName: "텀블러",
  optionText: "색상: 파랑",
  sourceKey: "fake:100",
  marketProductIds: [],
  optionCode: "01",
  quantity: 1,
  paidAmount: 12000,
  recipient: { name: "홍길동", zipCode: "07328", address1: "서울", address2: "1층", phone: "010-0000-0000", phone2: "", memo: "", customsCode: "" },
  ...over,
});

function setup(
  lines: MarketOrderLine[],
  opts: { product?: SupplierProduct; policy?: FulfillmentPolicy; purchase?: (r: PurchaseRequest) => Promise<{ supplierOrderNo: string }> } = {},
) {
  const store = new Store(":memory:");
  const purchases: PurchaseRequest[] = [];
  const confirmed: string[] = [];
  const supplier: SupplierAdapter = {
    id: "fake",
    search: async () => [],
    getProduct: async () => opts.product ?? product,
    purchase: async (r) => {
      purchases.push(r);
      return opts.purchase ? opts.purchase(r) : { supplierOrderNo: `S${purchases.length}` };
    },
  };
  const market: MarketAdapter = {
    id: "fakemarket",
    uploadImages: async (u) => u,
    registerProduct: async () => ({ productId: "1" }),
    fetchPaidOrders: async () => lines,
    getOrderLines: async (ids) => lines.filter((l) => ids.includes(l.lineId)),
    confirmOrders: async (ids) => {
      confirmed.push(...ids);
      return { ok: ids, failed: [] };
    },
  };
  const run = (live = true) =>
    runFulfillment({ market, suppliers: new Map([["fake", supplier]]), store, policy: opts.policy ?? policy, live, log: () => {}, now: new Date("2026-10-23T00:00:00Z") });
  return { store, purchases, confirmed, run };
}

describe("runFulfillment", () => {
  it("발주하고 발주 확인, 같은 줄은 두 번 발주하지 않음", async () => {
    const t = setup([line("1")]);
    const r = await t.run();
    expect(r.ordered).toEqual([{ lineId: "1", supplierOrderNo: "S1" }]);
    expect(t.purchases[0]).toMatchObject({ productId: "100", optionCode: "01", quantity: 1, storeName: "테스트스토어", sellerNote: "fakemarket O1" });
    expect(t.confirmed).toEqual(["1"]);
    expect(t.store.getPurchase("fakemarket", "1")?.status).toBe("confirmed");

    await t.run();
    expect(t.purchases).toHaveLength(1);
  });

  it("미리 보기는 아무것도 바꾸지 않음", async () => {
    const t = setup([line("1")]);
    const r = await t.run(false);
    expect(r.wouldOrder).toHaveLength(1);
    expect(t.purchases).toHaveLength(0);
    expect(t.store.getPurchase("fakemarket", "1")).toBeNull();
    expect(t.store.getState("fakemarket.orders.cursor")).toBeNull();
  });

  it("안전장치: 역마진·공급가 상승·옵션 없음·재고 부족은 보류", async () => {
    const t = setup([
      line("loss", { paidAmount: 5000 }),
      line("noopt", { optionCode: "99" }),
      line("stock", { quantity: 20, paidAmount: 999999 }),
    ]);
    const r = await t.run();
    expect(r.held.map((h) => h.lineId).sort()).toEqual(["loss", "noopt", "stock"]);
    expect(t.purchases).toHaveLength(0);

    const t2 = setup([line("up")], { product: { ...product, cost: 6000 } });
    t2.store.saveListing({ sourceKey: "fake:100", market: "fakemarket", marketProductId: "1", channelProductId: null, cost: 5000, salePrice: 12000, title: "" });
    const r2 = await t2.run();
    expect(r2.held[0].reason).toContain("공급가");
  });

  it("승인하면 안전장치 없이 발주", async () => {
    const t = setup([line("loss", { paidAmount: 5000 })]);
    await t.run();
    expect(t.store.getPurchase("fakemarket", "loss")?.status).toBe("held");
    t.store.updatePurchase("fakemarket", "loss", { status: "approved" });
    const r = await t.run();
    expect(r.ordered).toHaveLength(1);
  });

  it("공급처가 거절하면 failed, 응답이 불분명하면 unknown", async () => {
    const t = setup([line("a"), line("b")], {
      purchase: async () => {
        if (t.purchases.length === 1) throw new SupplierError("SOLD_OUT_ERROR", "품절");
        throw new Error("timeout");
      },
    });
    const r = await t.run();
    expect(r.failed.map((x) => x.lineId)).toEqual(["a"]);
    expect(r.unknown.map((x) => x.lineId)).toEqual(["b"]);
    expect(t.store.getPurchase("fakemarket", "b")?.status).toBe("unknown");
    await t.run();
    expect(t.purchases).toHaveLength(2);
  });

  it("응답 전에 멈춘 줄(ordering)은 다시 보내지 않고 unknown으로", async () => {
    const t = setup([line("1")]);
    t.store.insertPurchase({ market: "fakemarket", lineId: "1", orderId: "O1", sourceKey: "fake:100", optionCode: "01", quantity: 1, status: "ordering", message: null });
    const r = await t.run();
    expect(r.unknown.map((x) => x.lineId)).toEqual(["1"]);
    expect(t.purchases).toHaveLength(0);
  });

  it("실행당 한도를 넘은 줄은 pending으로 남겨 다음 실행에 처리", async () => {
    const t = setup([line("1"), line("2")], { policy: { ...policy, maxOrdersPerRun: 1 } });
    const r1 = await t.run();
    expect(r1.ordered.map((x) => x.lineId)).toEqual(["1"]);
    expect(t.store.getPurchase("fakemarket", "2")?.status).toBe("pending");
    const r2 = await t.run();
    expect(r2.ordered.map((x) => x.lineId)).toEqual(["2"]);
    expect(t.purchases).toHaveLength(2);
  });
});
