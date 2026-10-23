// 공급처·판매처 어댑터를 만드는 곳. 새 도매처나 판매처(쿠팡 등)를 붙일 때는
// src/suppliers/<이름>/ 또는 src/markets/<이름>/에 어댑터를 만들고 여기에 한 줄 더합니다.

import { env, type AppConfig } from "./config.ts";
import type { MarketAdapter, SupplierAdapter } from "./core/types.ts";
import { FakeMarket } from "./markets/fake/client.ts";
import { SmartstoreMarket } from "./markets/smartstore/client.ts";
import { SandboxFiles } from "./sandbox/files.ts";
import type { Store } from "./store/store.ts";
import { DomemeSupplier } from "./suppliers/domeme/client.ts";
import { FakeSupplier } from "./suppliers/fake/client.ts";

const supplierFactories: Record<string, (cfg: AppConfig, store: Store) => SupplierAdapter> = {
  domeme: (cfg, store) =>
    new DomemeSupplier(
      {
        apiKey: env("DOMEME_API_KEY"),
        userId: process.env.DOMEME_USER_ID ?? "",
        password: process.env.DOMEME_PASSWORD ?? "",
        clientIp: process.env.DOMEME_CLIENT_IP ?? "",
        alliance: process.env.DOMEME_ALLIANCE || "Dropship Automation",
        cashReceipt: process.env.DOMEME_CASH_RECEIPT !== "0",
      },
      store,
    ),
  // 샌드박스(키 없이 로컬에서 흐름 확인): config.sandbox.json
  fake: (cfg) => new FakeSupplier(new SandboxFiles(cfg.dataDir)),
};

const marketFactories: Record<string, (cfg: AppConfig) => MarketAdapter> = {
  smartstore: (cfg) =>
    new SmartstoreMarket({
      clientId: env("NAVER_COMMERCE_CLIENT_ID"),
      clientSecret: env("NAVER_COMMERCE_CLIENT_SECRET"),
      product: cfg.smartstore,
    }),
  fake: (cfg) => new FakeMarket(new SandboxFiles(cfg.dataDir)),
};

export function makeSupplier(id: string, cfg: AppConfig, store: Store): SupplierAdapter {
  const f = supplierFactories[id];
  if (!f) throw new Error(`알 수 없는 공급처 "${id}" (지원: ${Object.keys(supplierFactories).join(", ")})`);
  return f(cfg, store);
}

/** 주문 처리용: 설정 파일에 나온 공급처 전부(주문의 판매자 관리 코드로 골라 씀) */
export function makeAllSuppliers(cfg: AppConfig, store: Store): Map<string, SupplierAdapter> {
  const ids = new Set([...cfg.suppliers, ...cfg.jobs.map((j) => j.supplier)]);
  return new Map([...ids].map((id) => [id, makeSupplier(id, cfg, store)]));
}

export function makeMarket(cfg: AppConfig): MarketAdapter {
  const f = marketFactories[cfg.market];
  if (!f) throw new Error(`알 수 없는 판매처 "${cfg.market}" (지원: ${Object.keys(marketFactories).join(", ")})`);
  return f(cfg);
}
