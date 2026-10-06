import { RATES } from "@/data/rates/2026";

export type DealType = "sale" | "jeonse" | "monthly";

export type BrokerageResult = {
  dealAmount: number; // 중개보수 계산 기준 거래금액
  rate: number;
  limit?: number;
  fee: number; // 상한 중개보수(부가세 별도)
  vat: number;
};

export function calcBrokerage(type: DealType, price: number, deposit: number, monthlyRent: number): BrokerageResult {
  let dealAmount: number;
  if (type === "monthly") {
    // 보증금 + 월세 × 100, 결과가 5천만 원 미만이면 월세 × 70으로 다시 계산
    dealAmount = deposit + monthlyRent * 100;
    if (dealAmount < 50_000_000) dealAmount = deposit + monthlyRent * 70;
  } else {
    dealAmount = price;
  }

  const table = RATES.brokerage[type === "sale" ? "sale" : "lease"];
  const tier = table.find((t) => dealAmount < t.under)!;
  const raw = Math.floor(dealAmount * tier.rate);
  const fee = tier.limit ? Math.min(raw, tier.limit) : raw;
  return { dealAmount, rate: tier.rate, limit: tier.limit, fee, vat: Math.floor(fee * 0.1) };
}
