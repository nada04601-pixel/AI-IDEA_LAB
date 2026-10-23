// 공급처 검색 → 규칙으로 고르기 → 판매처 등록.

import type { Store } from "../store/store.ts";
import { buildListing, type ListingRules } from "./listing.ts";
import { makeSourceKey, type MarketAdapter, type SupplierAdapter, type SupplierSearchQuery } from "./types.ts";

export interface SourcingJob {
  name: string;
  supplier: string;
  query: SupplierSearchQuery;
  /** 판매처 카테고리 ID(스마트스토어 리프 카테고리) */
  marketCategoryId: string;
  /** 한 번 실행에 새로 등록할 최대 상품 수 */
  maxNew: number;
  /** 검색 결과를 몇 쪽까지 볼지 */
  maxPages: number;
}

export interface SourcingDeps {
  supplier: SupplierAdapter;
  market: MarketAdapter;
  store: Store;
  rules: ListingRules;
  live: boolean;
  log: (msg: string) => void;
}

export interface SourcingReport {
  registered: { id: string; marketProductId: string; title: string; salePrice: number; warnings: string[] }[];
  wouldRegister: { id: string; title: string; cost: number; salePrice: number; profit: number }[];
  skipped: { id: string; reason: string }[];
  errors: { id: string; message: string }[];
}

export async function runSourcing(job: SourcingJob, deps: SourcingDeps): Promise<SourcingReport> {
  const report: SourcingReport = { registered: [], wouldRegister: [], skipped: [], errors: [] };
  const done = () => report.registered.length + report.wouldRegister.length >= job.maxNew;

  for (let page = 1; page <= job.maxPages && !done(); page++) {
    const items = await deps.supplier.search({ ...job.query, page });
    if (items.length === 0) break;
    for (const item of items) {
      if (done()) break;
      if (deps.store.getListing(makeSourceKey(deps.supplier.id, item.id), deps.market.id)) continue;
      if (item.adultOnly) {
        report.skipped.push({ id: item.id, reason: "성인 상품" });
        continue;
      }
      if (item.orderUnit > deps.rules.filter.maxOrderUnit) {
        report.skipped.push({ id: item.id, reason: `묶음 수량 ${item.orderUnit}개` });
        continue;
      }
      await registerOne(item.id, job.marketCategoryId, deps, report);
    }
  }
  return report;
}

/** 공급처 상품 하나를 판매처에 등록합니다(이미 등록한 상품은 건너뜀) */
export async function registerOne(
  productId: string,
  marketCategoryId: string,
  deps: SourcingDeps,
  report: SourcingReport,
): Promise<void> {
  const { supplier, market, store, rules, live, log } = deps;
  if (store.getListing(makeSourceKey(supplier.id, productId), market.id)) {
    report.skipped.push({ id: productId, reason: "이미 등록함" });
    return;
  }
  try {
    const product = await supplier.getProduct(productId);
    const d = buildListing(product, marketCategoryId, rules);
    if (!d.ok) {
      report.skipped.push({ id: productId, reason: d.reason });
      return;
    }
    if (!live) {
      report.wouldRegister.push({ id: productId, title: d.listing.title, cost: product.cost, salePrice: d.listing.salePrice, profit: d.profit });
      return;
    }
    const ref = await market.registerProduct(d.listing);
    store.saveListing({
      sourceKey: d.listing.sourceKey,
      market: market.id,
      marketProductId: ref.productId,
      channelProductId: ref.channelProductId ?? null,
      cost: product.cost,
      salePrice: d.listing.salePrice,
      title: d.listing.title,
    });
    report.registered.push({ id: productId, marketProductId: ref.productId, title: d.listing.title, salePrice: d.listing.salePrice, warnings: ref.warnings ?? [] });
    log(`등록 완료 ${productId} → ${market.id} ${ref.productId} ${d.listing.title} ${d.listing.salePrice}원`);
  } catch (e) {
    report.errors.push({ id: productId, message: (e as Error).message });
  }
}
