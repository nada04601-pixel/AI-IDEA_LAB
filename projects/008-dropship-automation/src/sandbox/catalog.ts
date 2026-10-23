// 샌드박스 도매처가 처음에 갖는 상품. data/sandbox/fake/catalog.json으로 복사되므로
// 그 파일에서 공급가·재고를 바꾸거나 fail을 넣어 여러 상황을 만들어 볼 수 있습니다.

import type { SupplierProduct } from "../core/types.ts";

/**
 * 샌드박스 상품. 빈 칸은 toSupplierProduct가 채웁니다.
 * fail: 발주할 때 일부러 낼 오류
 * - reject: 도매처가 거절(품절 등) → failed
 * - timeout: 주문서는 만들어졌는데 응답이 안 옴 → unknown
 */
export type CatalogItem = Pick<SupplierProduct, "id" | "title" | "cost" | "stock"> &
  Partial<Omit<SupplierProduct, "supplier">> & { fail?: "reject" | "timeout" };

const img = (id: string) => [`https://example.com/sandbox/${id}/1.jpg`, `https://example.com/sandbox/${id}/2.jpg`];

export const SANDBOX_CATALOG: CatalogItem[] = [
  {
    id: "F1001",
    title: "스테인리스 텀블러 500ml",
    cost: 6500,
    shippingFee: 3000,
    stock: 0,
    optionGroups: ["색상"],
    options: [
      { code: "00", values: ["화이트"], extraCost: 0, stock: 120 },
      { code: "01", values: ["블랙"], extraCost: 0, stock: 80 },
      { code: "02", values: ["민트"], extraCost: 500, stock: 0 },
    ],
  },
  { id: "F1002", title: "진공 텀블러 900ml 대용량", cost: 9800, shippingFee: 3000, stock: 120 },
  { id: "F1003", title: "실리콘 텀블러 뚜껑 3개입", cost: 2500, shippingFee: 3000, stock: 500 },
  { id: "F1004", title: "명품 스타일 골드 텀블러", cost: 8000, shippingFee: 3000, stock: 100 },
  { id: "F1005", title: "캠핑 텀블러 4개 세트", cost: 15000, shippingFee: 3500, stock: 80, fail: "reject" },
  { id: "F1006", title: "차량용 텀블러 컵홀더형", cost: 7200, shippingFee: 3000, stock: 60, fail: "timeout" },
  { id: "F1007", title: "미니 텀블러 250ml", cost: 4500, shippingFee: 3000, stock: 10 },
  {
    id: "F1008",
    title: "접이식 수납 바구니",
    cost: 4900,
    shippingFee: 3000,
    stock: 0,
    optionGroups: ["크기"],
    options: [
      { code: "00", values: ["S"], extraCost: 0, stock: 100 },
      { code: "01", values: ["M"], extraCost: 1000, stock: 100 },
      { code: "02", values: ["L"], extraCost: 2000, stock: 100 },
    ],
  },
];

export const FAKE_SUPPLIER_ID = "fake";

export function toSupplierProduct(c: CatalogItem): SupplierProduct {
  const { fail: _fail, ...rest } = c;
  return {
    supplier: FAKE_SUPPLIER_ID,
    shippingFee: 0,
    shippingPayType: "P",
    extraShippingFee: { jeju: 3000, islands: 5000 },
    orderUnit: 1,
    images: img(c.id),
    detailHtml: `<p>${c.title} 상세 설명(샌드박스)</p>`,
    optionGroups: [],
    options: [],
    keywords: [],
    manufacturer: "샌드박스 제조사",
    model: c.id,
    origin: "국산",
    brand: "",
    adultOnly: false,
    category: { code: "S01", name: "생활용품", path: ["생활용품"] },
    url: `https://example.com/sandbox/${c.id}`,
    notice: [],
    ...rest,
  };
}
