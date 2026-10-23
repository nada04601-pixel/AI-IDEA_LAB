export interface PricingPolicy {
  /** 원가 대비 남길 이익률. 0.25 = 원가의 25% */
  marginRate: number;
  /** 판매처 수수료율(판매가 기준). 스마트스토어 결제·연동 수수료 합 등 */
  feeRate: number;
  /** 원가에 더할 고정 비용(포장·인건비 등) */
  fixedCost: number;
  /** 이 단위로 올림. 100이면 12,345 → 12,400 */
  roundTo: number;
  /**
   * include: 공급처 배송비를 판매가에 넣고 무료배송으로 판매
   * charge: 공급처 배송비를 그대로 고객에게 받음
   */
  shippingMode: "include" | "charge";
  /** 이익이 이 금액보다 적으면 등록하지 않음 */
  minProfit: number;
}

export interface PriceResult {
  salePrice: number;
  shippingFee: number;
  /** 수수료를 뺀 뒤 남는 예상 이익(옵션 추가금 없는 기본 상품 1개 기준) */
  profit: number;
}

function roundUp(n: number, unit: number): number {
  return unit > 0 ? Math.ceil(n / unit) * unit : Math.ceil(n);
}

/** 판매가 = (원가 + 고정비 [+ 배송비]) × (1 + 이익률) ÷ (1 − 수수료율), 올림 */
export function priceFor(cost: number, supplierShipping: number, p: PricingPolicy): PriceResult {
  const shippingInPrice = p.shippingMode === "include" ? supplierShipping : 0;
  const base = cost + p.fixedCost + shippingInPrice;
  const salePrice = roundUp((base * (1 + p.marginRate)) / (1 - p.feeRate), p.roundTo);
  const shippingFee = p.shippingMode === "include" ? 0 : supplierShipping;
  return { salePrice, shippingFee, profit: profitFor(salePrice, shippingFee, cost, supplierShipping, p) };
}

/** 고객이 낸 금액(상품가 + 배송비)에서 수수료·원가·배송비·고정비를 뺀 이익 */
export function profitFor(
  salePrice: number,
  shippingFee: number,
  cost: number,
  supplierShipping: number,
  p: Pick<PricingPolicy, "feeRate" | "fixedCost">,
): number {
  const revenue = salePrice + shippingFee;
  return Math.floor(revenue * (1 - p.feeRate) - cost - supplierShipping - p.fixedCost);
}

/** 옵션 추가 원가를 같은 비율로 판매가 추가금으로 바꿉니다 */
export function optionExtraPrice(extraCost: number, p: PricingPolicy): number {
  if (extraCost === 0) return 0;
  const v = (extraCost * (1 + p.marginRate)) / (1 - p.feeRate);
  return extraCost > 0 ? roundUp(v, p.roundTo) : -roundUp(-v, p.roundTo);
}
