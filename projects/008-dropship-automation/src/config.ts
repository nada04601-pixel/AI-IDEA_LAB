import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import type { FulfillmentPolicy } from "./core/fulfillment.ts";
import type { ListingRules } from "./core/listing.ts";
import type { SourcingJob } from "./core/sourcing.ts";
import type { SmartstoreProductDefaults } from "./markets/smartstore/product.ts";

export interface AppConfig {
  /** 판매처. smartstore와 샌드박스용 fake가 있고, 쿠팡 등은 registry.ts에 어댑터를 더하면 됩니다 */
  market: string;
  /** 주문 처리에 쓸 공급처. 첫 번째는 search·inspect·register의 기본 공급처. 기본 ["domeme"] */
  suppliers: string[];
  dataDir: string;
  listing: ListingRules;
  fulfillment: FulfillmentPolicy;
  smartstore: SmartstoreProductDefaults;
  jobs: SourcingJob[];
}

/** 비밀값은 .env(환경 변수), 나머지 설정은 config.json */
export function loadConfig(path: string): AppConfig {
  const file = resolve(path);
  if (!existsSync(file)) throw new Error(`설정 파일이 없습니다: ${file} (config.example.json을 복사해 만드세요)`);
  const envFile = resolve(file, "..", ".env");
  if (existsSync(envFile)) process.loadEnvFile(envFile);
  const cfg = JSON.parse(readFileSync(file, "utf8")) as AppConfig;
  cfg.market ??= "smartstore";
  cfg.suppliers ??= ["domeme"];
  cfg.dataDir = resolve(file, "..", cfg.dataDir ?? "data");
  cfg.jobs ??= [];
  return cfg;
}

export function env(name: string): string {
  const v = process.env[name]?.trim();
  if (!v) throw new Error(`환경 변수 ${name}이(가) 비어 있습니다(.env 확인)`);
  return v;
}
