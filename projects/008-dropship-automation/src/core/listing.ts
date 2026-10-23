import { optionExtraPrice, priceFor, type PricingPolicy } from "./pricing.ts";
import { makeSourceKey, type Listing, type SupplierProduct } from "./types.ts";

export interface ProductFilter {
  minCost?: number;
  maxCost?: number;
  /** 전체 재고가 이보다 적으면 건너뜀 */
  minStock: number;
  /** 상품명에 들어 있으면 건너뛸 낱말(브랜드 도용·인증 필요 품목 등) */
  excludeKeywords: string[];
  /** 묶음 수량이 이보다 크면 건너뜀. 위탁판매는 보통 1 */
  maxOrderUnit: number;
}

export interface ListingRules {
  pricing: PricingPolicy;
  filter: ProductFilter;
  /** 판매처에 표시할 재고 상한. 공급처 재고가 갑자기 줄어 초과 판매되는 걸 줄입니다 */
  maxStock: number;
  /** 상품명 앞에 붙일 말(브랜드명 등) */
  titlePrefix: string;
  /** 판매처 상품명 최대 길이 */
  maxTitleLength: number;
}

export type ListingDecision =
  | { ok: true; listing: Listing; profit: number }
  | { ok: false; reason: string };

/** 공급처 상품을 판매처에 올릴 상품으로 바꿉니다. 규칙에 맞지 않으면 이유를 돌려줍니다 */
export function buildListing(p: SupplierProduct, marketCategoryId: string, rules: ListingRules): ListingDecision {
  const f = rules.filter;
  if (p.unsupportedReason) return { ok: false, reason: p.unsupportedReason };
  if (p.adultOnly) return { ok: false, reason: "성인 상품" };
  if (p.orderUnit > f.maxOrderUnit) return { ok: false, reason: `묶음 수량 ${p.orderUnit}개` };
  if (f.minCost != null && p.cost < f.minCost) return { ok: false, reason: `공급가 ${p.cost}원이 최소보다 낮음` };
  if (f.maxCost != null && p.cost > f.maxCost) return { ok: false, reason: `공급가 ${p.cost}원이 최대보다 높음` };
  const hit = f.excludeKeywords.find((k) => k && p.title.includes(k));
  if (hit) return { ok: false, reason: `제외 낱말 "${hit}"` };
  if (p.images.length === 0) return { ok: false, reason: "이미지 없음" };

  const options = p.options
    .filter((o) => o.stock > 0)
    .map((o) => ({
      code: o.code,
      values: o.values,
      extraPrice: optionExtraPrice(o.extraCost, rules.pricing),
      stock: Math.min(o.stock, rules.maxStock),
    }));
  if (p.optionGroups.length > 0 && options.length === 0) return { ok: false, reason: "판매 중인 옵션 없음" };

  const stock = p.optionGroups.length > 0 ? options.reduce((s, o) => s + o.stock, 0) : Math.min(p.stock, rules.maxStock);
  const supplierStock = p.optionGroups.length > 0 ? p.options.reduce((s, o) => s + o.stock, 0) : p.stock;
  if (supplierStock < f.minStock) return { ok: false, reason: `재고 ${supplierStock}개` };

  const price = priceFor(p.cost, p.shippingFee, rules.pricing);
  if (price.profit < rules.pricing.minProfit) return { ok: false, reason: `예상 이익 ${price.profit}원` };

  const title = cleanTitle(`${rules.titlePrefix} ${p.title}`, rules.maxTitleLength);
  return {
    ok: true,
    profit: price.profit,
    listing: {
      sourceKey: makeSourceKey(p.supplier, p.id),
      title,
      salePrice: price.salePrice,
      shippingFee: price.shippingFee,
      extraShippingFee: p.extraShippingFee,
      stock,
      images: p.images,
      detailHtml: p.detailHtml,
      optionGroups: p.optionGroups,
      options: p.optionGroups.length > 0 ? options : [],
      marketCategoryId,
      manufacturer: p.manufacturer,
      model: p.model,
      origin: p.origin,
      brand: p.brand,
      keywords: p.keywords,
      adultOnly: p.adultOnly,
      notice: p.notice,
    },
  };
}

/** 판매처가 거부하는 특수문자를 빼고 길이를 맞춥니다 */
export function cleanTitle(s: string, max: number): string {
  return s
    .replace(/[\\*?"<>]/g, " ")
    .replace(/\s{2,}/g, " ")
    .trim()
    .slice(0, max)
    .trim();
}
