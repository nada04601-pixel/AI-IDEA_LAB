// 위탁판매 자동화 웹 데모. CLI와 같은 소싱·주문 처리 로직(src/core)을 가짜 판매처·도매처로 돌리고,
// 상태는 이 브라우저의 저장소에만 둡니다(서버 없음, 실제 등록·주문·결제 없음).

import sandboxConfig from "../config.sandbox.json";
import { runFulfillment, type FulfillmentPolicy, type FulfillmentReport } from "../src/core/fulfillment.ts";
import { buildListing, type ListingRules } from "../src/core/listing.ts";
import { runSourcing, type SourcingReport } from "../src/core/sourcing.ts";
import { FAKE_MARKET_ID, FakeMarket } from "../src/markets/fake/client.ts";
import { toSupplierProduct, type CatalogItem } from "../src/sandbox/catalog.ts";
import { memoryBackend, SandboxFiles, type SandboxOrderStatus } from "../src/sandbox/files.ts";
import { cancelOrder, createOrder } from "../src/sandbox/orders.ts";
import { MemoryStore, type MemorySnapshot } from "../src/store/memory.ts";
import type { PurchaseStatus } from "../src/store/types.ts";
import { FakeSupplier } from "../src/suppliers/fake/client.ts";

// ── 저장 ─────────────────────────────────────────────

const KEY = "dropship-demo.v1";

function load<T>(name: string, fallback: T): T {
  try {
    const t = localStorage.getItem(`${KEY}.${name}`);
    return t ? (JSON.parse(t) as T) : fallback;
  } catch {
    return fallback;
  }
}

function save(name: string, value: unknown): void {
  try {
    localStorage.setItem(`${KEY}.${name}`, JSON.stringify(value));
  } catch {
    // 저장소를 못 쓰는 환경(사생활 보호 창 등)에서는 이 탭이 열려 있는 동안만 유지
  }
}

function clearSaved(): void {
  try {
    for (const name of ["files", "store", "settings"]) localStorage.removeItem(`${KEY}.${name}`);
  } catch {
    // 무시
  }
}

interface Settings {
  rules: ListingRules;
  policy: FulfillmentPolicy;
}

const defaultSettings = (): Settings => ({
  rules: structuredClone(sandboxConfig.listing) as ListingRules,
  policy: structuredClone(sandboxConfig.fulfillment),
});

// ── 상태 ─────────────────────────────────────────────

let settings: Settings;
let files: SandboxFiles;
let store: MemoryStore;
let supplier: FakeSupplier;
let market: FakeMarket;

type Tab = "source" | "products" | "orders" | "purchases" | "settings";

const ui = {
  tab: "source" as Tab,
  keyword: "",
  sourcing: null as { live: boolean; report: SourcingReport } | null,
  fulfillment: null as { live: boolean; report: FulfillmentReport } | null,
  log: [] as { at: Date; text: string }[],
};

function init(): void {
  settings = load("settings", defaultSettings());
  files = new SandboxFiles(memoryBackend(load<Record<string, string>>("files", {}), (all) => save("files", all)));
  store = new MemoryStore(load<MemorySnapshot | undefined>("store", undefined));
  store.onChange = () => save("store", store.snapshot());
  supplier = new FakeSupplier(files);
  market = new FakeMarket(files);
}

const log = (text: string) => {
  ui.log.unshift({ at: new Date(), text });
  ui.log.length = Math.min(ui.log.length, 100);
};

// ── 동작 ─────────────────────────────────────────────

async function source(live: boolean): Promise<void> {
  const job = { name: "데모", supplier: supplier.id, query: { keyword: ui.keyword || undefined, size: 100 }, marketCategoryId: "demo", maxNew: 100, maxPages: 1 };
  const report = await runSourcing(job, { supplier, market, store, rules: settings.rules, live, log });
  ui.sourcing = { live, report };
  if (!live) log(`소싱 미리 보기: 등록 예정 ${report.wouldRegister.length}개, 건너뜀 ${report.skipped.length}개`);
}

function placeOrder(productId: string): void {
  const val = (id: string) => (document.getElementById(id) as HTMLInputElement | HTMLSelectElement | null)?.value ?? "";
  const qty = Number(val(`qty-${productId}`)) || 1;
  const paid = val(`paid-${productId}`);
  const o = createOrder(files, {
    productId,
    optionCode: val(`opt-${productId}`) || undefined,
    quantity: qty,
    paidAmount: paid ? Number(paid) : undefined,
  });
  log(`고객 주문 ${o.lineId}: ${o.productName} [${o.optionText || "옵션 없음"}] ×${o.quantity}, 결제 ${won(o.paidAmount)}`);
}

async function fulfill(live: boolean): Promise<void> {
  const report = await runFulfillment({ market, suppliers: new Map([[supplier.id, supplier]]), store, policy: settings.policy, live, log });
  ui.fulfillment = { live, report };
  const attention = report.held.length + report.failed.length + report.unknown.length + report.confirmFailed.length;
  log(live ? `주문 처리: 발주 ${report.ordered.length}, 사람 확인 필요 ${attention}` : `주문 처리 미리 보기: 발주 예정 ${report.wouldOrder.length}, 보류 ${report.held.length}`);
}

function approve(lineId: string): void {
  const p = store.getPurchase(FAKE_MARKET_ID, lineId);
  if (!p) return;
  if (p.status === "unknown" && !confirm("응답이 없었던 주문입니다. 도매처 주문서 탭에서 이 주문이 없는 걸 확인했나요?\n이미 있는데 승인하면 중복 발주됩니다.")) return;
  store.updatePurchase(FAKE_MARKET_ID, lineId, { status: "approved", message: `승인 ${new Date().toLocaleString("ko-KR")}` });
  log(`${lineId} 승인: 다음 주문 처리 때 안전장치 없이 발주`);
}

function cancel(lineId: string): void {
  cancelOrder(files, lineId);
  log(`${lineId} 고객 취소 요청`);
}

function reset(): void {
  if (!confirm("데모를 처음 상태로 되돌릴까요? 등록 상품·주문·설정이 모두 지워집니다.")) return;
  clearSaved();
  init();
  ui.sourcing = null;
  ui.fulfillment = null;
  ui.log = [];
  ui.tab = "source";
  log("데모를 처음 상태로 되돌림");
}

/** 도매처 상품 값 고치기(공급가·재고·테스트 동작). 판정 칸만 다시 그려 입력 중인 포커스를 지킵니다 */
function editCatalog(el: HTMLInputElement | HTMLSelectElement): void {
  const { id, field, opt } = el.dataset;
  const catalog = files.catalog();
  const item = catalog.find((c) => c.id === id);
  if (!item) return;
  if (field === "cost") item.cost = Math.max(0, Number(el.value) || 0);
  else if (field === "stock") item.stock = Math.max(0, Number(el.value) || 0);
  else if (field === "optstock" && item.options) item.options[Number(opt)].stock = Math.max(0, Number(el.value) || 0);
  else if (field === "fail") item.fail = (el.value || undefined) as CatalogItem["fail"];
  files.saveCatalog(catalog);
  const cell = document.getElementById(`verdict-${id}`);
  if (cell) cell.innerHTML = verdict(item);
}

function saveSettings(form: HTMLFormElement): void {
  const f = new FormData(form);
  const n = (k: string) => Number(f.get(k)) || 0;
  const r = settings.rules;
  r.pricing.marginRate = n("marginRate") / 100;
  r.pricing.feeRate = n("feeRate") / 100;
  r.pricing.minProfit = n("minProfit");
  r.filter.minCost = n("minCost");
  r.filter.maxCost = n("maxCost");
  r.filter.minStock = n("minStock");
  r.filter.excludeKeywords = String(f.get("excludeKeywords") ?? "").split(",").map((s) => s.trim()).filter(Boolean);
  const p = settings.policy;
  p.maxOrderAmount = n("maxOrderAmount");
  p.costIncreaseTolerance = n("costIncreaseTolerance") / 100;
  p.maxOrdersPerRun = Math.max(1, n("maxOrdersPerRun"));
  p.holdOnLoss = f.get("holdOnLoss") === "on";
  p.storeName = String(f.get("storeName") ?? "").trim() || "데모스토어";
  save("settings", settings);
  log("설정 저장");
}

// ── 화면 ─────────────────────────────────────────────

const app = document.getElementById("app")!;

function render(): void {
  const m = files.market();
  const purchases = store.listPurchases();
  const tabs: [Tab, string, number | null][] = [
    ["source", "① 상품 소싱", null],
    ["products", "② 판매 상품", m.products.length],
    ["orders", "③ 주문 처리", m.orders.length],
    ["purchases", "④ 도매처 주문서", files.purchases().length],
    ["settings", "설정·연동", null],
  ];
  const steps: [string, boolean][] = [
    ["상품 소싱에서 <b>미리 보기</b>로 어떤 상품이 등록될지 보기", ui.sourcing != null || m.products.length > 0],
    ["<b>등록 실행</b>으로 판매처에 올리기", m.products.length > 0],
    ["판매 상품에서 고객 대신 <b>주문 넣기</b>", m.orders.length > 0],
    ["주문 처리에서 <b>발주 실행</b> → 도매처 주문서 확인", purchases.some((p) => p.status === "confirmed")],
  ];

  app.innerHTML = `
  <div class="wrap">
    <header class="top">
      <h1>위탁판매 자동화 <span class="badge">데모</span></h1>
      <span class="spacer"></span>
      <button class="btn small danger" data-action="reset">처음부터 다시</button>
    </header>
    <div class="notice">가짜 도매처·판매처로 동작하는 데모입니다. 실제 상품 등록·주문·결제는 일어나지 않고, 데이터는 이 브라우저에만 저장됩니다.</div>
    <div class="card">
      <h2>도매처 상품을 찾아 판매처에 올리고, 주문이 오면 도매처에 고객 배송지로 자동 발주합니다</h2>
      <p class="sub">이렇게 해 보세요</p>
      <ol class="steps">${steps.map(([t, done]) => `<li class="${done ? "done" : ""}">${t}</li>`).join("")}</ol>
    </div>
    <nav class="tabs">${tabs
      .map(([id, label, count]) => `<button class="${ui.tab === id ? "on" : ""}" data-tab="${id}">${label}${count != null ? `<span class="count">${count}</span>` : ""}</button>`)
      .join("")}</nav>
    ${{ source: sourceTab, products: productsTab, orders: ordersTab, purchases: purchasesTab, settings: settingsTab }[ui.tab]()}
    <div class="card">
      <h2>실행 기록</h2>
      ${ui.log.length ? `<ul class="log">${ui.log.map((l) => `<li><time>${l.at.toLocaleTimeString("ko-KR")}</time>${esc(l.text)}</li>`).join("")}</ul>` : `<div class="empty">아직 실행한 것이 없습니다</div>`}
    </div>
    <footer>AI-IDEA_LAB 008 · <a href="https://github.com/nada04601-pixel/AI-IDEA_LAB/tree/main/projects/008-dropship-automation">코드</a> · <a href="https://github.com/nada04601-pixel/AI-IDEA_LAB/blob/main/ideas/008-dropship-automation/idea.md">설계 문서</a></footer>
  </div>`;
}

function sourceTab(): string {
  const catalog = files.catalog();
  const r = ui.sourcing;
  return `
  <div class="card">
    <h2>도매처 상품</h2>
    <p class="sub">가격·재고·제외 낱말 규칙(설정 탭)으로 등록할 상품을 고르고 판매가를 계산합니다. 공급가·재고·테스트 동작을 바꿔 여러 상황을 만들어 보세요.</p>
    <div class="toolbar">
      <input class="grow" id="keyword" placeholder="검색어(비우면 전체)" value="${esc(ui.keyword)}" />
      <button class="btn" data-action="source-preview">미리 보기</button>
      <button class="btn primary" data-action="source-run">등록 실행</button>
    </div>
    ${r ? sourcingResult(r.live, r.report) : ""}
    <div class="table"><table>
      <thead><tr><th>상품번호</th><th>상품명</th><th class="num">공급가</th><th>재고</th><th>발주할 때</th><th>판정</th></tr></thead>
      <tbody>${catalog
        .map(
          (c) => `<tr>
          <td>${esc(c.id)}</td>
          <td>${esc(c.title)}<div class="muted">배송비 ${won(c.shippingFee ?? 0)}</div></td>
          <td class="num"><input type="number" min="0" step="100" value="${c.cost}" data-id="${esc(c.id)}" data-field="cost" aria-label="공급가" /></td>
          <td class="opts">${
            c.options?.length
              ? c.options
                  .map((o, i) => `<label>${esc(o.values.join("/"))}<input class="narrow" type="number" min="0" value="${o.stock}" data-id="${esc(c.id)}" data-field="optstock" data-opt="${i}" aria-label="${esc(o.values.join("/"))} 재고" /></label>`)
                  .join("")
              : `<input class="narrow" type="number" min="0" value="${c.stock}" data-id="${esc(c.id)}" data-field="stock" aria-label="재고" />`
          }</td>
          <td><select data-id="${esc(c.id)}" data-field="fail" aria-label="발주할 때 동작">
            ${[["", "정상"], ["reject", "거절(품절)"], ["timeout", "응답 없음"]].map(([v, l]) => `<option value="${v}" ${(c.fail ?? "") === v ? "selected" : ""}>${l}</option>`).join("")}
          </select></td>
          <td id="verdict-${esc(c.id)}">${verdict(c)}</td>
        </tr>`,
        )
        .join("")}</tbody>
    </table></div>
  </div>`;
}

function verdict(c: CatalogItem): string {
  const listed = store.getListing(`${supplier.id}:${c.id}`, market.id);
  if (listed) return `${pill("ok", "등록됨")}<div class="muted">판매가 ${won(listed.salePrice)}</div>`;
  const d = buildListing(toSupplierProduct(c), "demo", settings.rules);
  return d.ok
    ? `${pill("info", "등록 가능")}<div class="muted">판매가 ${won(d.listing.salePrice)} · 이익 ${won(d.profit)}</div>`
    : `${pill("warn", "건너뜀")}<div class="muted">${esc(d.reason)}</div>`;
}

function sourcingResult(live: boolean, r: SourcingReport): string {
  const items = live
    ? [...r.registered.map((x) => `등록 ${x.id} → 판매처 상품 ${x.marketProductId}: ${x.title} ${won(x.salePrice)}`)]
    : [...r.wouldRegister.map((x) => `등록 예정 ${x.id}: ${x.title} | 공급가 ${won(x.cost)} → 판매가 ${won(x.salePrice)} (이익 ${won(x.profit)})`)];
  items.push(...r.skipped.map((x) => `건너뜀 ${x.id}: ${x.reason}`), ...r.errors.map((x) => `오류 ${x.id}: ${x.message}`));
  const head = live ? `등록 실행: ${r.registered.length}개 등록` : `미리 보기: ${r.wouldRegister.length}개 등록 예정 (아직 등록하지 않음)`;
  return `<div class="result"><b>${head}</b>${items.length ? `<ul>${items.map((t) => `<li>${esc(t)}</li>`).join("")}</ul>` : `<div class="muted">새로 등록할 상품이 없습니다</div>`}</div>`;
}

function productsTab(): string {
  const { products } = files.market();
  return `
  <div class="card">
    <h2>판매처에 등록된 상품</h2>
    <p class="sub">고객 대신 결제 완료 주문을 넣어 보세요. 결제 금액을 비우면 판매가대로, 공급가보다 낮게 넣으면 역마진 보류를 볼 수 있습니다.</p>
    ${
      products.length
        ? `<div class="table"><table>
      <thead><tr><th>상품번호</th><th>상품명</th><th class="num">판매가</th><th>옵션</th><th>수량</th><th>결제 금액</th><th></th></tr></thead>
      <tbody>${products
        .map(
          (p) => `<tr>
          <td>${esc(p.productId)}</td>
          <td>${esc(p.title)}<div class="muted">${esc(p.sourceKey)}</div></td>
          <td class="num">${won(p.salePrice)}</td>
          <td>${
            p.options.length
              ? `<select id="opt-${esc(p.productId)}" aria-label="옵션">${p.options
                  .map((o) => `<option value="${esc(o.code)}">${esc(o.values.join("/"))}${o.extraPrice ? ` (+${won(o.extraPrice)})` : ""}</option>`)
                  .join("")}</select>`
              : `<span class="muted">옵션 없음</span>`
          }</td>
          <td><input class="narrow" type="number" min="1" value="1" id="qty-${esc(p.productId)}" aria-label="수량" /></td>
          <td><input type="number" min="0" step="100" placeholder="자동" id="paid-${esc(p.productId)}" aria-label="결제 금액" /></td>
          <td><button class="btn small primary" data-action="order" data-id="${esc(p.productId)}">주문 넣기</button></td>
        </tr>`,
        )
        .join("")}</tbody>
    </table></div>`
        : `<div class="empty">아직 등록한 상품이 없습니다. ① 상품 소싱에서 <b>등록 실행</b>을 눌러 주세요.</div>`
    }
  </div>`;
}

const MARKET_STATUS: Record<SandboxOrderStatus, [string, string]> = {
  PAYED: ["plain", "결제 완료"],
  PLACED: ["ok", "발주 확인됨"],
  CANCEL_REQUEST: ["warn", "취소 요청"],
};

const PURCHASE_STATUS: Record<PurchaseStatus, [string, string]> = {
  ordering: ["info", "발주 중"],
  ordered: ["info", "발주함(확인 전)"],
  confirmed: ["ok", "발주 완료"],
  held: ["warn", "보류"],
  failed: ["bad", "실패"],
  unknown: ["bad", "확인 필요"],
  pending: ["plain", "다음 실행 대기"],
  approved: ["info", "승인됨"],
};

function ordersTab(): string {
  const { orders } = files.market();
  const f = ui.fulfillment;
  return `
  <div class="card">
    <h2>주문 처리</h2>
    <p class="sub">결제 완료 주문을 안전장치(중복·역마진·공급가 상승·금액 한도·재고)로 확인한 뒤 도매처에 고객 배송지로 발주하고, 판매처에 발주 확인을 보냅니다. 실제 서비스에서는 15분마다 자동으로 돕니다.</p>
    <div class="toolbar">
      <button class="btn" data-action="fulfill-preview">미리 보기</button>
      <button class="btn primary" data-action="fulfill-run">발주 실행</button>
    </div>
    ${f ? fulfillmentResult(f.live, f.report) : ""}
    ${
      orders.length
        ? `<div class="table"><table>
      <thead><tr><th>주문 줄</th><th>상품</th><th class="num">결제</th><th>판매처</th><th>자동 발주</th><th></th></tr></thead>
      <tbody>${orders
        .slice()
        .reverse()
        .map((o) => {
          const p = store.getPurchase(FAKE_MARKET_ID, o.lineId);
          const [mc, ml] = MARKET_STATUS[o.status];
          const [pc, pl] = p ? PURCHASE_STATUS[p.status] : ["plain", "새 주문"];
          const actions = [
            p && ["held", "failed", "unknown"].includes(p.status) ? `<button class="btn small" data-action="approve" data-id="${esc(o.lineId)}">승인</button>` : "",
            o.status === "PAYED" && (!p || !["ordered", "confirmed", "ordering"].includes(p.status)) ? `<button class="btn small danger" data-action="cancel" data-id="${esc(o.lineId)}">취소 요청</button>` : "",
          ].join(" ");
          return `<tr>
            <td>${esc(o.lineId)}</td>
            <td>${esc(o.productName)} <span class="muted">[${esc(o.optionText || "옵션 없음")}] ×${o.quantity}</span></td>
            <td class="num">${won(o.paidAmount)}</td>
            <td>${pill(mc, ml)}</td>
            <td>${pill(pc, pl)}${p?.supplierOrderNo ? `<div class="muted">도매처 주문 ${esc(p.supplierOrderNo)}</div>` : ""}${p?.message ? `<div class="muted">${esc(p.message)}</div>` : ""}</td>
            <td>${actions}</td>
          </tr>`;
        })
        .join("")}</tbody>
    </table></div>`
        : `<div class="empty">아직 주문이 없습니다. ② 판매 상품에서 <b>주문 넣기</b>를 눌러 주세요.</div>`
    }
  </div>`;
}

function fulfillmentResult(live: boolean, r: FulfillmentReport): string {
  const stats: [number, string][] = live
    ? [
        [r.ordered.length, "발주"],
        [r.confirmed.length, "발주 확인"],
        [r.held.length, "보류"],
        [r.failed.length, "실패"],
        [r.unknown.length, "확인 필요"],
        [r.skipped.length, "건너뜀"],
      ]
    : [
        [r.wouldOrder.length, "발주 예정"],
        [r.held.length, "보류"],
        [r.unknown.length, "확인 필요"],
        [r.skipped.length, "건너뜀"],
      ];
  const lines = [
    ...r.wouldOrder.map((x) => `발주 예정 ${x.lineId}: ${x.summary}`),
    ...r.ordered.map((x) => `발주 ${x.lineId} → 도매처 주문 ${x.supplierOrderNo}`),
    ...r.held.map((x) => `보류 ${x.lineId}: ${x.reason}`),
    ...r.failed.map((x) => `실패 ${x.lineId}: ${x.reason}`),
    ...r.unknown.map((x) => `확인 필요 ${x.lineId}: ${x.reason}`),
    ...r.confirmFailed.map((x) => `발주 확인 실패 ${x.lineId}: ${x.reason}`),
    ...r.skipped.map((x) => `건너뜀 ${x.lineId}: ${x.reason}`),
  ];
  return `<div class="result"><b>${live ? "발주 실행 결과" : "미리 보기 (아직 발주하지 않음)"}</b>
    <div class="stats" style="margin-top:8px">${stats.map(([n, l]) => `<div class="stat"><b>${n}</b><span>${l}</span></div>`).join("")}</div>
    ${lines.length ? `<ul>${lines.map((t) => `<li>${esc(t)}</li>`).join("")}</ul>` : `<div class="muted">처리할 새 주문이 없습니다</div>`}
  </div>`;
}

function purchasesTab(): string {
  const list = files.purchases();
  const titles = new Map(files.catalog().map((c) => [c.id, c.title]));
  return `
  <div class="card">
    <h2>도매처에 들어간 주문서</h2>
    <p class="sub">도매처는 받는 사람(고객) 주소로 바로 배송합니다. "응답 없음" 상품은 주문서가 만들어졌는데 응답이 안 온 경우라, 자동으로 다시 보내지 않고 사람이 여기서 확인합니다.</p>
    ${
      list.length
        ? `<div class="table"><table>
      <thead><tr><th>도매처 주문</th><th>상품</th><th>받는 사람</th><th>메모</th><th>시각</th></tr></thead>
      <tbody>${list
        .slice()
        .reverse()
        .map(
          (p) => `<tr>
          <td>${esc(p.supplierOrderNo)}</td>
          <td>${esc(titles.get(p.productId) ?? p.productId)} <span class="muted">[${esc(p.optionCode || "-")}] ×${p.quantity}</span></td>
          <td>${esc(p.recipient.name)}<div class="muted">${esc(p.recipient.address1)} ${esc(p.recipient.address2)}</div></td>
          <td class="muted">${esc(p.sellerNote)} · ${esc(p.storeName)}</td>
          <td class="muted">${new Date(p.orderedAt).toLocaleString("ko-KR")}</td>
        </tr>`,
        )
        .join("")}</tbody>
    </table></div>`
        : `<div class="empty">아직 도매처 주문서가 없습니다</div>`
    }
  </div>`;
}

function settingsTab(): string {
  const { pricing, filter } = settings.rules;
  const p = settings.policy;
  const num = (name: string, label: string, value: number, hint: string, step = 1) =>
    `<label>${label}<input type="number" name="${name}" value="${value}" step="${step}" min="0" /><small>${hint}</small></label>`;
  return `
  <form class="card" id="settings">
    <h2>등록 규칙</h2>
    <p class="sub">판매가 = (공급가 + 배송비) × (1 + 이익률) ÷ (1 − 수수료율), 100원 단위 올림</p>
    <div class="form">
      ${num("marginRate", "이익률 (%)", round(pricing.marginRate * 100), "공급가 대비 남길 이익")}
      ${num("feeRate", "판매처 수수료율 (%)", round(pricing.feeRate * 100), "판매가 기준", 0.1)}
      ${num("minProfit", "최소 이익 (원)", pricing.minProfit, "이보다 적으면 등록 안 함", 100)}
      ${num("minCost", "최소 공급가 (원)", filter.minCost ?? 0, "", 100)}
      ${num("maxCost", "최대 공급가 (원)", filter.maxCost ?? 0, "", 100)}
      ${num("minStock", "최소 재고", filter.minStock, "도매처 재고가 이보다 적으면 건너뜀")}
      <label>제외 낱말<input type="text" name="excludeKeywords" value="${esc(filter.excludeKeywords.join(", "))}" /><small>쉼표로 구분. 상품명에 있으면 건너뜀(브랜드·인증 품목)</small></label>
    </div>
    <h2 style="margin-top:18px">주문 처리 안전장치</h2>
    <p class="sub">걸리면 발주하지 않고 보류해서 사람이 확인합니다</p>
    <div class="form">
      ${num("maxOrderAmount", "발주 금액 한도 (원)", p.maxOrderAmount, "한 줄 발주 금액이 넘으면 보류", 1000)}
      ${num("costIncreaseTolerance", "공급가 상승 허용 (%)", round(p.costIncreaseTolerance * 100), "등록 때보다 이만큼 넘게 오르면 보류")}
      ${num("maxOrdersPerRun", "실행당 최대 발주", p.maxOrdersPerRun, "넘는 주문은 다음 실행으로")}
      <label>쇼핑몰 이름<input type="text" name="storeName" value="${esc(p.storeName)}" /><small>송장·박스에 찍힐 이름</small></label>
      <label class="check"><input type="checkbox" name="holdOnLoss" ${p.holdOnLoss ? "checked" : ""} /> 역마진(발주 금액 &gt; 고객 결제)이면 보류</label>
    </div>
    <div class="toolbar" style="margin-top:14px;margin-bottom:0"><button class="btn primary" type="submit">저장</button></div>
  </form>
  <div class="card">
    <h2>연동</h2>
    <p class="sub">정식 서비스(SaaS)에서는 판매자가 자기 판매처·도매처 계정을 연결합니다. 지금은 데모용 가짜 계정만 연결되어 있습니다.</p>
    <div class="connect">
      <div><b>샌드박스 판매처</b>${pill("ok", "연결됨")} <span class="muted">데모</span></div>
      <div><b>샌드박스 도매처</b>${pill("ok", "연결됨")} <span class="muted">데모</span></div>
      <div><b>네이버 스마트스토어</b>${pill("plain", "준비 중")}<div class="muted">커머스API(상품 등록·주문·발주 확인)</div></div>
      <div><b>도매매</b>${pill("plain", "준비 중")}<div class="muted">OpenAPI·주문 API(사업자 회원)</div></div>
      <div><b>쿠팡</b>${pill("plain", "예정")}<div class="muted">WING Open API</div></div>
    </div>
  </div>`;
}

// ── 이벤트 ───────────────────────────────────────────

app.addEventListener("click", async (e) => {
  const el = (e.target as HTMLElement).closest<HTMLElement>("[data-action], [data-tab]");
  if (!el) return;
  if (el.dataset.tab) {
    ui.tab = el.dataset.tab as Tab;
    render();
    return;
  }
  const id = el.dataset.id ?? "";
  try {
    switch (el.dataset.action) {
      case "source-preview":
      case "source-run":
        ui.keyword = (document.getElementById("keyword") as HTMLInputElement).value.trim();
        await source(el.dataset.action === "source-run");
        break;
      case "order":
        placeOrder(id);
        break;
      case "fulfill-preview":
      case "fulfill-run":
        await fulfill(el.dataset.action === "fulfill-run");
        break;
      case "approve":
        approve(id);
        break;
      case "cancel":
        cancel(id);
        break;
      case "reset":
        reset();
        break;
    }
  } catch (err) {
    log(`오류: ${(err as Error).message}`);
  }
  render();
});

app.addEventListener("change", (e) => {
  const el = e.target as HTMLInputElement | HTMLSelectElement;
  if (el.dataset.field) editCatalog(el);
});

app.addEventListener("submit", (e) => {
  e.preventDefault();
  saveSettings(e.target as HTMLFormElement);
  render();
});

app.addEventListener("keydown", (e) => {
  if ((e.target as HTMLElement).id === "keyword" && e.key === "Enter") (app.querySelector('[data-action="source-preview"]') as HTMLElement).click();
});

// ── 도우미 ───────────────────────────────────────────

function esc(s: string): string {
  return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);
}

const won = (n: number) => `${n.toLocaleString("ko-KR")}원`;
const pill = (kind: string, text: string) => `<span class="pill ${kind}">${esc(text)}</span> `;
const round = (n: number) => Math.round(n * 10) / 10;

init();
render();
