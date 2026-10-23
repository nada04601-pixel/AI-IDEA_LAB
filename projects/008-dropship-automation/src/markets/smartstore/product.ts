// 공통 Listing → 네이버 커머스API 상품 등록(POST /v2/products) 요청 본문. 순수 함수.

import type { Listing } from "../../core/types.ts";

export interface SmartstoreProductDefaults {
  /** 택배사 코드. 예: CJGLS(CJ대한통운), HANJIN, HYUNDAI(롯데), KGB(로젠), EPOST(우체국) */
  deliveryCompany: string;
  returnDeliveryFee: number;
  exchangeDeliveryFee: number;
  afterServiceTelephoneNumber: string;
  afterServiceGuideContent: string;
  /** 판매자센터 주소록 번호. 비우면 기본 출고지·반품지 */
  shippingAddressId?: number;
  returnAddressId?: number;
  /** 네이버쇼핑 노출(네이버쇼핑 광고주만 true가 반영됨) */
  naverShoppingRegistration: boolean;
  /** detailAttribute에 그대로 덧붙일 값. 카테고리별 인증·속성 등 */
  detailAttributeExtra?: Record<string, unknown>;
}

/**
 * 판매가 대비 옵션가 허용 범위(스마트스토어 판매자센터 기준).
 * 판매가 2,000원 미만: 0~+100%, 2,000원~10,000원 미만: -50%~+100%, 10,000원 이상: -50%~+50%
 */
export function optionPriceRange(salePrice: number): [number, number] {
  if (salePrice < 2000) return [0, salePrice];
  if (salePrice < 10000) return [-Math.floor(salePrice / 2), salePrice];
  return [-Math.floor(salePrice / 2), Math.floor(salePrice / 2)];
}

/** 원산지 코드: 00 국산, 03 기타(상세 설명에 표시). 수입산(02)은 수입사가 필수라 상세 설명 표시로 둡니다 */
export function originArea(origin: string): { originAreaCode: string; content?: string } {
  if (/^(국산|국내|한국|대한민국|korea)/i.test(origin.trim())) return { originAreaCode: "00" };
  return { originAreaCode: "03" };
}

export interface BuiltProduct {
  body: Record<string, unknown>;
  /** 범위를 벗어나 뺀 옵션 등 알림 */
  warnings: string[];
}

export function buildProductBody(l: Listing, imageUrls: string[], d: SmartstoreProductDefaults): BuiltProduct {
  const warnings: string[] = [];
  if (imageUrls.length === 0) throw new Error("대표 이미지가 없습니다");
  if (l.optionGroups.length > 3) throw new Error(`옵션 그룹이 ${l.optionGroups.length}개(스마트스토어 조합형은 최대 3개)`);

  const [lo, hi] = optionPriceRange(l.salePrice);
  const options = l.options.filter((o) => {
    const ok = o.extraPrice >= lo && o.extraPrice <= hi;
    if (!ok) warnings.push(`옵션 ${o.values.join("/")} 추가금 ${o.extraPrice}원이 허용 범위(${lo}~${hi}원)를 벗어나 뺐습니다`);
    return ok;
  });
  if (l.options.length > 0 && options.length === 0) throw new Error("등록할 수 있는 옵션이 없습니다");

  const optionInfo =
    options.length > 0
      ? {
          optionCombinationSortType: "CREATE",
          optionCombinationGroupNames: Object.fromEntries(
            l.optionGroups.map((g, i) => [`optionGroupName${i + 1}`, optionText(g)]),
          ),
          optionCombinations: options.map((o) => ({
            ...Object.fromEntries(o.values.map((v, i) => [`optionName${i + 1}`, optionText(v)])),
            stockQuantity: o.stock,
            price: o.extraPrice,
            // 주문이 들어오면 optionManageCode로 돌아와 공급처 옵션 코드로 쓰입니다
            sellerManagerCode: o.code,
            usable: true,
          })),
          useStockManagement: true,
        }
      : undefined;

  const stock = options.length > 0 ? options.reduce((s, o) => s + o.stock, 0) : l.stock;

  const deliveryFee: Record<string, unknown> =
    l.shippingFee > 0
      ? { deliveryFeeType: "PAID", baseFee: l.shippingFee, deliveryFeePayType: "PREPAID" }
      : { deliveryFeeType: "FREE" };
  if (l.extraShippingFee.jeju > 0 || l.extraShippingFee.islands > 0) {
    deliveryFee.deliveryFeeByArea = {
      deliveryAreaType: "AREA_3",
      area2extraFee: l.extraShippingFee.jeju,
      area3extraFee: l.extraShippingFee.islands || l.extraShippingFee.jeju,
    };
  }

  const detailAttribute: Record<string, unknown> = {
    naverShoppingSearchInfo: {
      ...(l.model ? { modelName: l.model } : {}),
      ...(l.manufacturer ? { manufacturerName: l.manufacturer } : {}),
      ...(l.brand ? { brandName: l.brand } : {}),
    },
    afterServiceInfo: {
      afterServiceTelephoneNumber: d.afterServiceTelephoneNumber,
      afterServiceGuideContent: d.afterServiceGuideContent,
    },
    originAreaInfo: originArea(l.origin),
    sellerCodeInfo: { sellerManagementCode: l.sourceKey },
    ...(optionInfo ? { optionInfo } : {}),
    minorPurchasable: !l.adultOnly,
    productInfoProvidedNotice: {
      productInfoProvidedNoticeType: "ETC",
      etc: {
        itemName: l.title.slice(0, 100),
        modelName: l.model || "상품상세참조",
        manufacturer: l.manufacturer || "상품상세참조",
        afterServiceDirector: d.afterServiceTelephoneNumber,
      },
    },
    // 판매자 태그(seoInfo.sellerTags)는 등록 불가 태그가 하나라도 있으면 상품 등록 전체가 실패해 넣지 않습니다
    ...d.detailAttributeExtra,
  };

  const body = {
    originProduct: {
      statusType: "SALE",
      saleType: "NEW",
      leafCategoryId: l.marketCategoryId,
      name: l.title,
      detailContent: l.detailHtml || `<p>${escapeHtml(l.title)}</p>`,
      images: {
        representativeImage: { url: imageUrls[0] },
        ...(imageUrls.length > 1 ? { optionalImages: imageUrls.slice(1, 10).map((url) => ({ url })) } : {}),
      },
      salePrice: l.salePrice,
      stockQuantity: stock,
      deliveryInfo: {
        deliveryType: "DELIVERY",
        deliveryAttributeType: "NORMAL",
        deliveryCompany: d.deliveryCompany,
        deliveryFee,
        claimDeliveryInfo: {
          returnDeliveryFee: d.returnDeliveryFee,
          exchangeDeliveryFee: d.exchangeDeliveryFee,
          ...(d.shippingAddressId ? { shippingAddressId: d.shippingAddressId } : {}),
          ...(d.returnAddressId ? { returnAddressId: d.returnAddressId } : {}),
        },
      },
      detailAttribute,
    },
    smartstoreChannelProduct: {
      naverShoppingRegistration: d.naverShoppingRegistration,
      channelProductDisplayStatusType: "ON",
    },
  };
  return { body, warnings };
}

/** 옵션명·값: 스마트스토어가 받지 않는 문자를 빼고 25자로 */
function optionText(s: string): string {
  return s.replace(/[\\*?"<>,]/g, " ").replace(/\s{2,}/g, " ").trim().slice(0, 25) || "-";
}

function escapeHtml(s: string): string {
  return s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!);
}
