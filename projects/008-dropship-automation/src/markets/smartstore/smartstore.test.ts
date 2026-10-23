import { describe, expect, it } from "vitest";
import type { Listing } from "../../core/types.ts";
import { signature } from "./client.ts";
import { splitWindows, toKstIso, toOrderLine } from "./orders.ts";
import { buildProductBody, optionPriceRange, originArea, type SmartstoreProductDefaults } from "./product.ts";

describe("signature", () => {
  it("커머스API 문서의 예시 값과 같음", () => {
    expect(signature("aaaabbbbcccc", "$2a$10$abcdefghijklmnopqrstuv", 1643961623299)).toBe(
      "JDJhJDEwJGFiY2RlZmdoaWprbG1ub3BxcnN0dXVCVldZSk42T0VPdEx1OFY0cDQxa2IuTnpVaUEzbmsy",
    );
  });
});

describe("날짜", () => {
  it("한국 시간 ISO", () => {
    expect(toKstIso(new Date("2026-10-23T00:00:00Z"))).toBe("2026-10-23T09:00:00.000+09:00");
  });

  it("24시간씩 나눔", () => {
    const w = splitWindows(new Date("2026-10-20T00:00:00Z"), new Date("2026-10-22T06:00:00Z"));
    expect(w.map(([a, b]) => [a.toISOString(), b.toISOString()])).toEqual([
      ["2026-10-20T00:00:00.000Z", "2026-10-21T00:00:00.000Z"],
      ["2026-10-21T00:00:00.000Z", "2026-10-22T00:00:00.000Z"],
      ["2026-10-22T00:00:00.000Z", "2026-10-22T06:00:00.000Z"],
    ]);
  });
});

const defaults: SmartstoreProductDefaults = {
  deliveryCompany: "CJGLS",
  returnDeliveryFee: 5000,
  exchangeDeliveryFee: 10000,
  afterServiceTelephoneNumber: "010-0000-0000",
  afterServiceGuideContent: "톡톡 문의",
  naverShoppingRegistration: true,
};

const listing: Listing = {
  sourceKey: "domeme:9583416",
  title: "스텐 텀블러 500ml",
  salePrice: 12000,
  shippingFee: 0,
  extraShippingFee: { jeju: 3000, islands: 5000 },
  stock: 0,
  images: ["https://cdn.example/o.jpg"],
  detailHtml: "<p>상세</p>",
  optionGroups: ["색상", "크기"],
  options: [
    { code: "00_00", values: ["빨강", "L"], extraPrice: 0, stock: 50 },
    { code: "02_00", values: ["블랙", "L"], extraPrice: 800, stock: 20 },
    { code: "02_01", values: ["블랙", "XL"], extraPrice: 7000, stock: 20 },
  ],
  marketCategoryId: "50000000",
  manufacturer: "샘플 제조사",
  model: "TB-500",
  origin: "중국",
  brand: "",
  keywords: [],
  adultOnly: false,
  notice: [],
};

describe("buildProductBody", () => {
  it("옵션 관리 코드에 공급처 옵션 코드, 판매자 관리 코드에 공급처 상품", () => {
    const { body, warnings } = buildProductBody(listing, ["https://shop-phinf.pstatic.net/a.jpg"], defaults);
    const o = body.originProduct as any;
    expect(o.leafCategoryId).toBe("50000000");
    expect(o.images.representativeImage.url).toBe("https://shop-phinf.pstatic.net/a.jpg");
    expect(o.detailAttribute.sellerCodeInfo.sellerManagementCode).toBe("domeme:9583416");
    expect(o.detailAttribute.optionInfo.optionCombinationGroupNames).toEqual({ optionGroupName1: "색상", optionGroupName2: "크기" });
    expect(o.detailAttribute.optionInfo.optionCombinations.map((c: any) => [c.optionName1, c.optionName2, c.price, c.sellerManagerCode])).toEqual([
      ["빨강", "L", 0, "00_00"],
      ["블랙", "L", 800, "02_00"],
    ]);
    // 판매가 12,000원이면 옵션가는 +6,000원까지
    expect(warnings).toHaveLength(1);
    expect(o.stockQuantity).toBe(70);
    expect(o.deliveryInfo.deliveryFee).toEqual({
      deliveryFeeType: "FREE",
      deliveryFeeByArea: { deliveryAreaType: "AREA_3", area2extraFee: 3000, area3extraFee: 5000 },
    });
    expect(o.detailAttribute.originAreaInfo).toEqual({ originAreaCode: "03" });
    expect(o.detailAttribute.productInfoProvidedNotice.productInfoProvidedNoticeType).toBe("ETC");
  });

  it("옵션 없는 상품, 유료 배송", () => {
    const { body } = buildProductBody({ ...listing, optionGroups: [], options: [], stock: 30, shippingFee: 3000, extraShippingFee: { jeju: 0, islands: 0 } }, ["u"], defaults);
    const o = body.originProduct as any;
    expect(o.detailAttribute.optionInfo).toBeUndefined();
    expect(o.stockQuantity).toBe(30);
    expect(o.deliveryInfo.deliveryFee).toEqual({ deliveryFeeType: "PAID", baseFee: 3000, deliveryFeePayType: "PREPAID" });
  });

  it("옵션 그룹 4개 이상은 거절", () => {
    expect(() => buildProductBody({ ...listing, optionGroups: ["a", "b", "c", "d"] }, ["u"], defaults)).toThrow(/최대 3개/);
  });

  it("옵션가 범위·원산지", () => {
    expect(optionPriceRange(1500)).toEqual([0, 1500]);
    expect(optionPriceRange(5000)).toEqual([-2500, 5000]);
    expect(optionPriceRange(20000)).toEqual([-10000, 10000]);
    expect(originArea("국산").originAreaCode).toBe("00");
    expect(originArea("대한민국").originAreaCode).toBe("00");
    expect(originArea("상세정보별도표기").originAreaCode).toBe("03");
  });
});

describe("toOrderLine", () => {
  const item = {
    order: { orderId: "2026102300001", ordererName: "주문자" },
    productOrder: {
      productOrderId: "2026102300001001",
      productOrderStatus: "PAYED",
      placeOrderStatus: "NOT_YET",
      productName: "스텐 텀블러 500ml",
      productOption: "색상: 블랙 / 크기: L",
      sellerProductCode: "domeme:9583416",
      optionManageCode: "02_00",
      originalProductId: "111",
      productId: "222",
      quantity: 2,
      remainQuantity: 2,
      totalPaymentAmount: 25600,
      remainPaymentAmount: 25600,
      shippingMemo: "부재 시 경비실",
      shippingAddress: {
        addressType: "DOMESTIC",
        name: "홍길동",
        zipCode: "07328",
        baseAddress: "서울특별시 영등포구 국제금융로6길 30",
        detailedAddress: "1층",
        tel1: "010-0000-0000",
        tel2: "",
      },
    },
  };

  it("배송지와 매핑 정보", () => {
    expect(toOrderLine(item)).toEqual({
      market: "smartstore",
      lineId: "2026102300001001",
      orderId: "2026102300001",
      productName: "스텐 텀블러 500ml",
      optionText: "색상: 블랙 / 크기: L",
      sourceKey: "domeme:9583416",
      marketProductIds: ["111", "222"],
      optionCode: "02_00",
      quantity: 2,
      paidAmount: 25600,
      recipient: {
        name: "홍길동",
        zipCode: "07328",
        address1: "서울특별시 영등포구 국제금융로6길 30",
        address2: "1층",
        phone: "010-0000-0000",
        phone2: "",
        memo: "부재 시 경비실",
        customsCode: "",
      },
      skipReason: undefined,
    });
  });

  it("이미 발주 확인했거나 클레임이 있으면 건너뜀", () => {
    expect(toOrderLine({ ...item, productOrder: { ...item.productOrder, placeOrderStatus: "OK" } }).skipReason).toContain("발주 상태");
    expect(toOrderLine({ ...item, productOrder: { ...item.productOrder, claimType: "CANCEL", claimStatus: "CANCEL_REQUEST" } }).skipReason).toContain("클레임");
    expect(toOrderLine({ ...item, productOrder: { ...item.productOrder, productOrderStatus: "DELIVERING" } }).skipReason).toContain("DELIVERING");
  });
});
