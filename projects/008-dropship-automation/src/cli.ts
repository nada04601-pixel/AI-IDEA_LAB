// 사용법은 README.md. 모든 명령은 기본이 "미리 보기"이고, --live를 붙여야 실제로 등록·발주합니다.

import { join } from "node:path";
import { parseArgs } from "node:util";
import { loadConfig } from "./config.ts";
import { runFulfillment } from "./core/fulfillment.ts";
import { buildListing } from "./core/listing.ts";
import { priceFor } from "./core/pricing.ts";
import { registerOne, runSourcing, type SourcingReport } from "./core/sourcing.ts";
import { SmartstoreMarket } from "./markets/smartstore/client.ts";
import { makeAllSuppliers, makeMarket, makeSupplier } from "./registry.ts";
import { Store, type PurchaseStatus } from "./store/store.ts";

const HELP = `사용법: npm run cli -- <명령> [옵션]

  search <검색어>                 도매매 상품 검색(예상 판매가 함께 표시)
  inspect <상품번호> [--category ID]  도매매 상품 상세와 등록 가능 여부
  categories <낱말>               스마트스토어 카테고리 ID 찾기
  register <상품번호> --category ID   상품 하나 등록
  source [--job 이름]             config.json의 jobs대로 검색해서 등록
  orders                          새 주문을 도매매에 발주하고 스마트스토어에 발주 확인
  status [--all]                  사람이 확인할 주문(보류·실패·불명) 보기
  approve <상품주문번호>          보류·실패·불명 주문을 확인했으니 다음 실행 때 발주하라고 표시

  --live      실제로 등록·발주(없으면 미리 보기만)
  --config    설정 파일 경로(기본 ./config.json)
  --page N    검색 쪽 번호`;

const { values: opt, positionals } = parseArgs({
  allowPositionals: true,
  options: {
    live: { type: "boolean", default: false },
    config: { type: "string", default: "config.json" },
    category: { type: "string" },
    job: { type: "string" },
    page: { type: "string" },
    all: { type: "boolean", default: false },
    help: { type: "boolean", short: "h", default: false },
  },
});

const [cmd, arg] = positionals;
const log = (m: string) => console.log(`[${new Date().toLocaleString("ko-KR")}] ${m}`);

async function main(): Promise<void> {
  if (!cmd || opt.help) {
    console.log(HELP);
    return;
  }
  const cfg = loadConfig(opt.config!);
  const store = new Store(join(cfg.dataDir, "dropship.db"));
  const live = opt.live!;
  if (!live && ["register", "source", "orders"].includes(cmd)) log("미리 보기 모드입니다. 실제로 하려면 --live를 붙이세요.");

  try {
    switch (cmd) {
      case "search": {
        need(arg, "검색어");
        const items = await makeSupplier("domeme", cfg, store).search({ keyword: arg, page: Number(opt.page ?? 1) });
        for (const it of items) {
          const p = priceFor(it.cost, 0, cfg.listing.pricing);
          console.log(`${it.id}\t공급가 ${won(it.cost)}\t→ 판매가 ${won(p.salePrice)}(배송비 제외)\t${it.title}`);
        }
        console.log(`${items.length}개`);
        break;
      }
      case "inspect": {
        need(arg, "상품번호");
        const p = await makeSupplier("domeme", cfg, store).getProduct(arg);
        console.log(JSON.stringify({ ...p, detailHtml: `${p.detailHtml.slice(0, 200)}…` }, null, 2));
        const d = buildListing(p, opt.category ?? "(카테고리 미지정)", cfg.listing);
        console.log(d.ok ? `등록 가능: 판매가 ${won(d.listing.salePrice)}, 배송비 ${won(d.listing.shippingFee)}, 예상 이익 ${won(d.profit)}` : `등록 안 함: ${d.reason}`);
        break;
      }
      case "categories": {
        need(arg, "낱말");
        const market = makeMarket(cfg);
        if (!(market instanceof SmartstoreMarket)) throw new Error("카테고리 찾기는 스마트스토어만 지원합니다");
        for (const c of await market.searchCategories(arg)) console.log(`${c.id}\t${c.wholeCategoryName}`);
        break;
      }
      case "register": {
        need(arg, "상품번호");
        need(opt.category, "--category");
        const report: SourcingReport = { registered: [], wouldRegister: [], skipped: [], errors: [] };
        await registerOne(arg, opt.category!, { supplier: makeSupplier("domeme", cfg, store), market: makeMarket(cfg), store, rules: cfg.listing, live, log }, report);
        printSourcing(report);
        break;
      }
      case "source": {
        const jobs = cfg.jobs.filter((j) => !opt.job || j.name === opt.job);
        if (jobs.length === 0) throw new Error("실행할 job이 없습니다(config.json의 jobs 확인)");
        const market = makeMarket(cfg);
        for (const job of jobs) {
          log(`job "${job.name}" 시작`);
          printSourcing(await runSourcing(job, { supplier: makeSupplier(job.supplier, cfg, store), market, store, rules: cfg.listing, live, log }));
        }
        break;
      }
      case "orders": {
        const r = await runFulfillment({ market: makeMarket(cfg), suppliers: makeAllSuppliers(cfg, store), store, policy: cfg.fulfillment, live, log });
        for (const x of r.wouldOrder) console.log(`발주 예정 ${x.lineId}: ${x.summary}`);
        for (const x of r.ordered) console.log(`발주 ${x.lineId} → 도매매 주문 ${x.supplierOrderNo}`);
        for (const x of r.confirmed) console.log(`발주 확인 ${x}`);
        for (const [label, list] of [["보류", r.held], ["실패", r.failed], ["확인 필요", r.unknown], ["발주 확인 실패", r.confirmFailed], ["건너뜀", r.skipped]] as const) {
          for (const x of list) console.log(`${label} ${x.lineId}: ${x.reason}`);
        }
        const attention = r.held.length + r.failed.length + r.unknown.length + r.confirmFailed.length;
        log(`끝: 발주 ${r.ordered.length}, 예정 ${r.wouldOrder.length}, 사람 확인 필요 ${attention}`);
        if (attention > 0) process.exitCode = 2;
        break;
      }
      case "status": {
        const watch: PurchaseStatus[] = ["held", "failed", "unknown", "ordered", "pending", "approved"];
        const rows = store.listPurchases().filter((p) => opt.all || watch.includes(p.status));
        for (const p of rows) {
          console.log(`${p.status}\t${p.lineId}\t주문 ${p.orderId}\t${p.sourceKey} [${p.optionCode || "-"}] ×${p.quantity}\t${p.supplierOrderNo ?? ""}\t${p.message ?? ""}`);
        }
        console.log(`${rows.length}건`);
        break;
      }
      case "approve": {
        need(arg, "상품주문번호");
        const p = store.getPurchase(cfg.market, arg);
        if (!p) throw new Error(`기록이 없습니다: ${arg}`);
        if (!["held", "failed", "unknown"].includes(p.status)) throw new Error(`${p.status} 상태는 승인할 수 없습니다`);
        if (p.status === "unknown") console.log("주의: 도매매 사이트에서 이 주문이 없는 걸 확인한 경우에만 승인하세요(중복 발주 위험).");
        store.updatePurchase(cfg.market, arg, { status: "approved", message: `승인 ${new Date().toISOString()}` });
        console.log("승인했습니다. 다음 orders --live 실행 때 안전장치 없이 발주합니다.");
        break;
      }
      default:
        console.log(HELP);
        process.exitCode = 1;
    }
  } finally {
    store.close();
  }
}

function printSourcing(r: SourcingReport): void {
  for (const x of r.wouldRegister) console.log(`등록 예정 ${x.id}: ${x.title} | 공급가 ${won(x.cost)} → 판매가 ${won(x.salePrice)} (이익 ${won(x.profit)})`);
  for (const x of r.registered) {
    console.log(`등록 ${x.id} → 상품 ${x.marketProductId}: ${x.title} ${won(x.salePrice)}`);
    for (const w of x.warnings) console.log(`  알림: ${w}`);
  }
  for (const x of r.skipped) console.log(`건너뜀 ${x.id}: ${x.reason}`);
  for (const x of r.errors) console.log(`오류 ${x.id}: ${x.message}`);
}

function need(v: unknown, name: string): void {
  if (!v) throw new Error(`${name}을(를) 입력하세요. --help 참고`);
}

const won = (n: number) => `${n.toLocaleString("ko-KR")}원`;

main().catch((e) => {
  console.error(`오류: ${(e as Error).message}`);
  process.exitCode = 1;
});
