import { describe, expect, it } from "vitest";
import { buildListing, type ListingRules } from "./listing.ts";
import { optionExtraPrice, priceFor } from "./pricing.ts";
import { formatPhone, nonEucKrChars, stripNonEucKr } from "./text.ts";
import { parseSourceKey, type SupplierProduct } from "./types.ts";

const rules: ListingRules = {
  pricing: { marginRate: 0.25, feeRate: 0.06, fixedCost: 0, roundTo: 100, shippingMode: "include", minProfit: 500 },
  filter: { minCost: 1000, maxCost: 50000, minStock: 10, excludeKeywords: ["정품"], maxOrderUnit: 1 },
  maxStock: 50,
  titlePrefix: "",
  maxTitleLength: 100,
};

const product: SupplierProduct = {
  supplier: "domeme",
  id: "1",
  title: "스텐 텀블러",
  cost: 5000,
  shippingFee: 3000,
  shippingPayType: "P",
  extraShippingFee: { jeju: 0, islands: 0 },
  orderUnit: 1,
  stock: 300,
  images: ["a.jpg"],
  detailHtml: "",
  optionGroups: [],
  options: [],
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

describe("priceFor", () => {
  it("배송비 포함 무료배송: (5000 + 3000) × 1.25 ÷ 0.94 → 100원 단위 올림", () => {
    const p = priceFor(5000, 3000, rules.pricing);
    expect(p.salePrice).toBe(10700);
    expect(p.shippingFee).toBe(0);
    expect(p.profit).toBe(Math.floor(10700 * 0.94 - 8000));
  });

  it("배송비 따로 받기", () => {
    const p = priceFor(5000, 3000, { ...rules.pricing, shippingMode: "charge" });
    expect(p.salePrice).toBe(6700);
    expect(p.shippingFee).toBe(3000);
  });

  it("옵션 추가금도 같은 비율", () => {
    expect(optionExtraPrice(500, rules.pricing)).toBe(700);
    expect(optionExtraPrice(-500, rules.pricing)).toBe(-700);
    expect(optionExtraPrice(0, rules.pricing)).toBe(0);
  });
});

describe("buildListing", () => {
  it("규칙에 맞으면 판매처 상품, 재고는 상한까지", () => {
    const d = buildListing(product, "50000000", rules);
    expect(d.ok).toBe(true);
    if (d.ok) {
      expect(d.listing.sourceKey).toBe("domeme:1");
      expect(d.listing.stock).toBe(50);
      expect(d.listing.salePrice).toBe(10700);
    }
  });

  it("거르는 규칙", () => {
    expect(buildListing({ ...product, title: "정품 텀블러" }, "c", rules)).toEqual({ ok: false, reason: '제외 낱말 "정품"' });
    expect(buildListing({ ...product, orderUnit: 10 }, "c", rules).ok).toBe(false);
    expect(buildListing({ ...product, stock: 3 }, "c", rules).ok).toBe(false);
    expect(buildListing({ ...product, adultOnly: true }, "c", rules).ok).toBe(false);
    expect(buildListing({ ...product, unsupportedReason: "착불 배송 상품" }, "c", rules)).toEqual({ ok: false, reason: "착불 배송 상품" });
  });

  it("품절 옵션은 빼고, 판매 중인 옵션이 없으면 거름", () => {
    const withOpts = {
      ...product,
      optionGroups: ["색상"],
      options: [
        { code: "00", values: ["빨강"], extraCost: 0, stock: 0 },
        { code: "01", values: ["파랑"], extraCost: 500, stock: 100 },
      ],
    };
    const d = buildListing(withOpts, "c", rules);
    expect(d.ok && d.listing.options).toEqual([{ code: "01", values: ["파랑"], extraPrice: 700, stock: 50 }]);
    expect(buildListing({ ...withOpts, options: [withOpts.options[0]] }, "c", rules).ok).toBe(false);
  });
});

describe("text", () => {
  it("전화번호 하이픈", () => {
    expect(formatPhone("01012345678")).toBe("010-1234-5678");
    expect(formatPhone("010-123-4567")).toBe("010-123-4567");
    expect(formatPhone("0212345678")).toBe("02-1234-5678");
    expect(formatPhone("031-123-4567")).toBe("031-123-4567");
    expect(formatPhone("050412345678")).toBe("0504-1234-5678");
    expect(formatPhone("+82 10-1234-5678")).toBe("010-1234-5678");
    expect(formatPhone("15881234")).toBe("1588-1234");
  });

  it("EUC-KR로 못 쓰는 글자", () => {
    expect(nonEucKrChars("홍길동 Hong 123")).toEqual([]);
    expect(nonEucKrChars("똠방각하")).toEqual(["똠"]);
    expect(stripNonEucKr("빨리 와주세요 🙏 감사")).toBe("빨리 와주세요 감사");
  });

  it("판매자 관리 코드", () => {
    expect(parseSourceKey("domeme:9583416")).toEqual({ supplier: "domeme", productId: "9583416" });
    expect(parseSourceKey("아무거나")).toBeNull();
  });
});
