import { describe, expect, it } from "vitest";
import type { PurchaseRequest } from "../../core/types.ts";
import { DomemeError, formatDeliInfo, formatOrderItem, num, parseOptions, parseOrderResult, parseProduct, parseSearch } from "./parse.ts";

// 상품상세정보 API 주문옵션 문서(ver4.5)의 예시: 색상 3 × 크기 2 조합형
const SELECT_OPT = JSON.stringify({
  type: "combination",
  optSort: "DA",
  set: [
    { name: "색상", opts: ["빨강", "노랑", "블랙"], domPrice: [0, 100, 200], changeKey: [0, 1, 2] },
    { name: "크기", opts: ["L", "XL"], domPrice: [0, 0], changeKey: [0, 1] },
  ],
  data: {
    "00_00": { name: "빨강/L", dom: "1", domPrice: 0, sam: "1", sup: "1", samPrice: 0, supPrice: 0, qty: "100", hid: "0" },
    "00_01": { name: "빨강/XL", dom: "1", domPrice: 0, sam: "1", sup: "1", samPrice: 0, supPrice: 0, qty: "200", hid: "0" },
    "01_00": { name: "노랑/L", dom: "1", domPrice: 100, sam: "1", sup: "0", samPrice: 0, supPrice: 0, qty: "100", hid: "0" },
    "01_01": { name: "노랑/XL", dom: "1", domPrice: 100, sam: "1", sup: "1", samPrice: 0, supPrice: 300, qty: "50", hid: "1" },
    "02_00": { name: "블랙/L", dom: "1", domPrice: 200, sam: "1", sup: "1", samPrice: 0, supPrice: 500, qty: "50", hid: "0" },
    "02_01": { name: "블랙/XL", dom: "1", domPrice: 200, sam: "1", sup: "1", samPrice: 0, supPrice: 500, qty: "0", hid: "2" },
  },
});

describe("num", () => {
  it("문자열·수량별 단가를 숫자로", () => {
    expect(num("12,000")).toBe(12000);
    expect(num("1+5000|100+4500")).toBe(5000);
    expect(num(3000)).toBe(3000);
    expect(num(undefined)).toBe(0);
  });
});

describe("parseOptions", () => {
  it("도매매에 보이고 판매 중인 조합만, 옵션값은 set 순서대로", () => {
    const r = parseOptions(SELECT_OPT, 999);
    expect(r.groups).toEqual(["색상", "크기"]);
    expect(r.options).toEqual([
      { code: "00_00", values: ["빨강", "L"], extraCost: 0, stock: 100 },
      { code: "00_01", values: ["빨강", "XL"], extraCost: 0, stock: 200 },
      { code: "02_00", values: ["블랙", "L"], extraCost: 500, stock: 50 },
    ]);
  });

  it("옵션 없으면 빈 목록", () => {
    expect(parseOptions(null, 10)).toEqual({ groups: [], options: [] });
    expect(parseOptions("", 10)).toEqual({ groups: [], options: [] });
  });

  it("조합형이 아니면 지원하지 않음으로 표시", () => {
    const r = parseOptions(JSON.stringify({ type: "independent", data: { "00_00": { sup: 1, hid: 0 } } }), 1);
    expect(r.unsupported).toContain("independent");
  });
});

describe("parseSearch", () => {
  it("상품이 하나뿐이어도 배열로", () => {
    const one = parseSearch({
      domeggook: {
        header: { numberOfItems: 1 },
        list: { item: { no: 123, title: "텀블러", price: "4,500", thumb: "t.jpg", unitQty: 1, adultOnly: false, url: "u" } },
      },
    });
    expect(one).toEqual([{ id: "123", title: "텀블러", cost: 4500, thumb: "t.jpg", orderUnit: 1, adultOnly: false, url: "u" }]);
  });

  it("오류 응답이면 DomemeError", () => {
    expect(() => parseSearch({ errors: { code: 10, message: "올바른 요청이 아닙니다", dcode: "PARAMETER_ERROR", dmessage: "파라미터가 없거나 잘못되었습니다" } })).toThrow(
      DomemeError,
    );
  });
});

describe("parseProduct", () => {
  const body = {
    domeggook: {
      basis: { no: "9583416", title: "스텐 텀블러 500ml", adult: "false", keywords: { kw: ["텀블러", "보온병"] } },
      price: { dome: "4000", supply: "5200" },
      qty: { inventory: "350", supplyUnit: "1" },
      deli: { pay: "P", supply: { pay: "P", fee: "3000" }, feeExtra: { jeju: "3000", islands: "5000" }, fromOversea: "false" },
      channel: { dome: "true", supply: "true" },
      thumb: { original: "https://cdn.example/o.jpg", large: "https://cdn.example/l.jpg" },
      desc: { contents: { item: "<p>상세</p>" } },
      selectOpt: SELECT_OPT,
      detail: { country: "중국", manufacturer: "샘플 제조사", model: "TB-500", infoDuty: { item: [{ name: "제품명", desc: "상세정보 별도표기" }] } },
      category: { parents: { elem: [{ name: "생활" }, { name: "주방" }] }, current: { name: "텀블러", code: "01_02_03_00_00" } },
    },
  };

  it("공통 상품으로", () => {
    const p = parseProduct(body);
    expect(p).toMatchObject({
      supplier: "domeme",
      id: "9583416",
      cost: 5200,
      shippingFee: 3000,
      shippingPayType: "P",
      extraShippingFee: { jeju: 3000, islands: 5000 },
      orderUnit: 1,
      stock: 350,
      images: ["https://cdn.example/o.jpg"],
      optionGroups: ["색상", "크기"],
      keywords: ["텀블러", "보온병"],
      origin: "중국",
      adultOnly: false,
      category: { code: "01_02_03_00_00", name: "텀블러", path: ["생활", "주방", "텀블러"] },
      notice: [{ name: "제품명", value: "상세정보 별도표기" }],
    });
    expect(p.unsupportedReason).toBeUndefined();
  });

  it("무료배송이면 배송비 0, 착불이면 지원 안 함", () => {
    const free = parseProduct({ domeggook: { ...body.domeggook, deli: { supply: { pay: "S", fee: "3000" } } } });
    expect(free.shippingFee).toBe(0);
    expect(free.shippingPayType).toBe("S");
    const cod = parseProduct({ domeggook: { ...body.domeggook, deli: { supply: { pay: "B", fee: "3000" } } } });
    expect(cod.unsupportedReason).toContain("착불");
  });
});

const req = (over: Partial<PurchaseRequest> = {}): PurchaseRequest => ({
  productId: "6579919",
  optionCode: "",
  quantity: 2,
  shippingPayType: "P",
  storeName: "앗싸독수리",
  sellerNote: "smartstore 2026102312345",
  recipient: {
    name: "홍길동",
    zipCode: "07328",
    address1: "서울특별시 영등포구 국제금융로6길 30",
    address2: "1층",
    phone: "01000000000",
    phone2: "0200000000",
    memo: "문 앞에 놔주세요 🙏",
    customsCode: "",
  },
  ...over,
});

describe("주문서 문자열", () => {
  it("item[]: 연동 가이드 예시 형식(옵션 없는 상품은 00)", () => {
    expect(formatOrderItem(req())).toBe("supply||P||00|2||smartstore 2026102312345||문 앞에 놔주세요");
    expect(formatOrderItem(req({ optionCode: "01_03", quantity: 4 }))).toBe("supply||P||01_03|4||smartstore 2026102312345||문 앞에 놔주세요");
  });

  it("deliinfo: 9칸, 전화번호 하이픈", () => {
    expect(formatDeliInfo(req())).toBe("홍길동||07328|서울특별시 영등포구 국제금융로6길 30|1층|010-0000-0000|02-0000-0000|앗싸독수리|");
  });

  it("휴대전화가 tel2에 있으면 바꿔 넣음, 안심번호도 휴대전화로", () => {
    const r = formatDeliInfo(req({ recipient: { ...req().recipient, phone: "0212345678", phone2: "050412345678" } }));
    expect(r.split("|")[5]).toBe("0504-1234-5678");
    expect(r.split("|")[6]).toBe("02-1234-5678");
  });

  it("구분자는 지우고, EUC-KR로 못 쓰는 이름은 오류", () => {
    expect(formatDeliInfo(req({ recipient: { ...req().recipient, address2: "101동|202호" } })).split("|")[4]).toBe("101동 202호");
    expect(() => formatDeliInfo(req({ recipient: { ...req().recipient, name: "김똠" } }))).toThrow(/EUC-KR/);
  });

  it("휴대전화가 없거나 우편번호가 이상하면 오류", () => {
    expect(() => formatDeliInfo(req({ recipient: { ...req().recipient, phone: "0212345678", phone2: "" } }))).toThrow(/휴대전화/);
    expect(() => formatDeliInfo(req({ recipient: { ...req().recipient, zipCode: "123" } }))).toThrow(/우편번호/);
  });
});

describe("parseOrderResult", () => {
  it("주문번호", () => {
    const body = { domeggook: { result: "SUCCESS", order: [{ orderNo: 14207678, itemNo: 9583416 }, { orderNo: 14207679, itemNo: 7105488 }] } };
    expect(parseOrderResult(body, "7105488")).toBe("14207679");
  });

  it("DB 오류는 주문서가 생겼을 수도 있음", () => {
    try {
      parseOrderResult({ errors: { dcode: "DB_INSERT_ERROR", dmessage: "주문서 생성 중에 데이터베이스 오류가 발생했습니다" } }, "1");
      expect.unreachable();
    } catch (e) {
      expect((e as DomemeError).orderMayExist).toBe(true);
    }
    try {
      parseOrderResult({ errors: { dcode: "SOLD_OUT_ERROR", dmessage: "상품의 재고수량이 부족합니다" } }, "1");
    } catch (e) {
      expect((e as DomemeError).orderMayExist).toBe(false);
    }
  });
});
