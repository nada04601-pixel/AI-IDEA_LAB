import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import { runFulfillment, type FulfillmentPolicy } from "../core/fulfillment.ts";
import type { ListingRules } from "../core/listing.ts";
import { runSourcing, type SourcingJob } from "../core/sourcing.ts";
import { FakeMarket } from "../markets/fake/client.ts";
import { MemoryStore } from "../store/memory.ts";
import { Store } from "../store/store.ts";
import { FakeSupplier } from "../suppliers/fake/client.ts";
import { memoryBackend, SandboxFiles } from "./files.ts";
import { sandboxFilesIn } from "./node-files.ts";
import { cancelOrder, createOrder } from "./orders.ts";

const rules: ListingRules = {
  pricing: { marginRate: 0.25, feeRate: 0.06, fixedCost: 0, roundTo: 100, shippingMode: "include", minProfit: 1000 },
  filter: { minCost: 3000, maxCost: 50000, minStock: 30, excludeKeywords: ["명품"], maxOrderUnit: 1 },
  maxStock: 50,
  titlePrefix: "",
  maxTitleLength: 100,
};

const policy: FulfillmentPolicy = {
  lookbackHours: 24,
  maxOrdersPerRun: 20,
  maxOrderAmount: 100000,
  costIncreaseTolerance: 0.05,
  holdOnLoss: true,
  storeName: "샌드박스스토어",
};

const job: SourcingJob = { name: "전체", supplier: "fake", query: {}, marketCategoryId: "c", maxNew: 10, maxPages: 1 };

let dir = "";
afterEach(() => {
  if (dir) rmSync(dir, { recursive: true, force: true });
  dir = "";
});

// CLI(폴더 + SQLite)와 웹 데모(메모리 + MemoryStore)가 같은 결과를 내는지 둘 다 돌립니다
const backends = {
  cli: () => {
    dir = mkdtempSync(join(tmpdir(), "dropship-sandbox-"));
    return { files: sandboxFilesIn(dir), store: new Store(":memory:") };
  },
  web: () => ({ files: new SandboxFiles(memoryBackend()), store: new MemoryStore() }),
};

function setup(kind: keyof typeof backends) {
  const { files, store } = backends[kind]();
  const supplier = new FakeSupplier(files);
  const market = new FakeMarket(files);
  const source = (live = true) => runSourcing(job, { supplier, market, store, rules, live, log: () => {} });
  const orders = (live = true) => runFulfillment({ market, suppliers: new Map([["fake", supplier]]), store, policy, live, log: () => {} });
  /** 공급처 상품번호로 판매처 상품번호 찾기 */
  const productOf = (supplierId: string) => files.market().products.find((p) => p.sourceKey === `fake:${supplierId}`)!.productId;
  return { files, store, source, orders, productOf };
}

describe.each(Object.keys(backends) as (keyof typeof backends)[])("샌드박스 처음부터 끝까지 (%s)", (kind) => {
  it("규칙에 맞는 상품만 등록하고, 다시 돌려도 중복 등록하지 않음", async () => {
    const t = setup(kind);
    const preview = await t.source(false);
    expect(preview.wouldRegister.map((x) => x.id)).toEqual(["F1001", "F1002", "F1005", "F1006", "F1008"]);
    expect(t.files.market().products).toHaveLength(0);

    const r = await t.source();
    expect(r.registered.map((x) => x.id)).toEqual(["F1001", "F1002", "F1005", "F1006", "F1008"]);
    expect(Object.fromEntries(r.skipped.map((x) => [x.id, x.reason]))).toEqual({
      F1003: "공급가 2500원이 최소보다 낮음",
      F1004: '제외 낱말 "명품"',
      F1007: "재고 10개",
    });
    // 재고 없는 옵션(민트)은 판매처에 올리지 않음
    expect(t.files.market().products[0].options.map((o) => o.code)).toEqual(["00", "01"]);

    expect((await t.source()).registered).toHaveLength(0);
    expect(t.files.market().products).toHaveLength(5);
  });

  it("주문 → 발주(고객 배송지) → 발주 확인, 재고 차감, 두 번 발주하지 않음", async () => {
    const t = setup(kind);
    await t.source();
    const o = createOrder(t.files, { productId: t.productOf("F1001"), optionCode: "01", quantity: 2 });

    const preview = await t.orders(false);
    expect(preview.wouldOrder.map((x) => x.lineId)).toEqual([o.lineId]);
    expect(t.files.purchases()).toHaveLength(0);

    const r = await t.orders();
    expect(r.ordered).toEqual([{ lineId: o.lineId, supplierOrderNo: "F000001" }]);
    expect(r.confirmed).toEqual([o.lineId]);
    expect(t.files.purchases()[0]).toMatchObject({ productId: "F1001", optionCode: "01", quantity: 2, storeName: "샌드박스스토어" });
    expect(t.files.purchases()[0].recipient.name).toBe("홍길동");
    expect(t.files.market().orders[0].status).toBe("PLACED");
    expect(t.files.catalog().find((c) => c.id === "F1001")!.options!.find((x) => x.code === "01")!.stock).toBe(78);

    await t.orders();
    expect(t.files.purchases()).toHaveLength(1);
  });

  it("거절은 failed, 응답 없음은 unknown(주문서는 생김), 역마진은 held, 취소 요청은 건너뜀", async () => {
    const t = setup(kind);
    await t.source();
    const reject = createOrder(t.files, { productId: t.productOf("F1005") });
    const timeout = createOrder(t.files, { productId: t.productOf("F1006") });
    const loss = createOrder(t.files, { productId: t.productOf("F1008"), paidAmount: 3000 });
    const cancel = createOrder(t.files, { productId: t.productOf("F1002") });
    cancelOrder(t.files, cancel.lineId);

    const r = await t.orders();
    expect(r.failed.map((x) => x.lineId)).toEqual([reject.lineId]);
    expect(r.unknown.map((x) => x.lineId)).toEqual([timeout.lineId]);
    expect(r.held.map((x) => x.lineId)).toEqual([loss.lineId]);
    expect(r.skipped.map((x) => x.lineId)).toEqual([cancel.lineId]);
    expect(t.files.purchases().map((p) => p.productId)).toEqual(["F1006"]);

    // 다음 실행에서도 unknown은 자동으로 다시 보내지 않음
    await t.orders();
    expect(t.files.purchases()).toHaveLength(1);
  });

  it("등록 뒤 공급가가 오르면 보류, 승인하면 발주", async () => {
    const t = setup(kind);
    await t.source();
    const catalog = t.files.catalog();
    catalog.find((c) => c.id === "F1002")!.cost = 11000;
    t.files.saveCatalog(catalog);
    const o = createOrder(t.files, { productId: t.productOf("F1002") });

    const r = await t.orders();
    expect(r.held[0].reason).toContain("공급가");
    t.store.updatePurchase("fake", o.lineId, { status: "approved" });
    const r2 = await t.orders();
    expect(r2.ordered.map((x) => x.lineId)).toEqual([o.lineId]);
  });
});
