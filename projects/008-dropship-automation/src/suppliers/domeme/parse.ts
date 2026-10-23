// 도매꾹/도매매 Open API 응답을 공통 모델로 바꾸는 순수 함수들.
// 문서: https://openapi.domeggook.com (상품리스트 v4.1, 상품상세정보 v4.6, 주문서 생성 v4.3)

import { SupplierError } from "../../core/errors.ts";
import { cleanField, formatPhone, isMobileLike, nonEucKrChars, stripNonEucKr } from "../../core/text.ts";
import type { PurchaseRequest, SupplierOption, SupplierProduct, SupplierSearchItem } from "../../core/types.ts";

export const SUPPLIER_ID = "domeme";
/** 옵션이 없는 상품을 주문할 때 쓰는 옵션 코드 */
export const SINGLE_OPTION_CODE = "00";

type Json = Record<string, any>;

/** 주문서가 만들어졌을 수도 있는 오류(연동 가이드: DB_INSERT_ERROR는 일부만 주문됐을 수 있음) */
const MAY_EXIST = new Set(["DB_INSERT_ERROR", "UNKNOWN_RESULT", "NO_ORDER_NO"]);

export class DomemeError extends SupplierError {
  constructor(dcode: string, message: string) {
    super(dcode, `도매매 ${dcode}: ${message}`, MAY_EXIST.has(dcode));
  }
}

/** 하나만 있으면 객체, 여럿이면 배열로 오는 값을 배열로 맞춥니다 */
export function arr<T = Json>(v: unknown): T[] {
  if (v == null || v === "") return [];
  return (Array.isArray(v) ? v : [v]) as T[];
}

/** "12,000", "1+12000|10+11000"(수량별 단가) 같은 값을 숫자로. 수량별 단가는 첫 구간 */
export function num(v: unknown): number {
  if (typeof v === "number") return v;
  if (typeof v !== "string") return 0;
  const first = v.split("|")[0];
  const price = first.includes("+") ? first.split("+")[1] : first;
  const n = Number(price.replace(/[^\d.-]/g, ""));
  return Number.isFinite(n) ? n : 0;
}

const bool = (v: unknown) => v === true || v === "true" || v === 1 || v === "1";
const str = (v: unknown) => (v == null ? "" : String(v)).trim();

/** API 오류 응답이면 DomemeError를 던집니다 */
export function unwrap(body: Json): Json {
  const err = body.errors ?? body.domeggook?.errors;
  if (err) throw new DomemeError(str(err.dcode) || str(err.code), str(err.dmessage) || str(err.message));
  return body.domeggook ?? body;
}

export function parseSearch(body: Json): SupplierSearchItem[] {
  const root = unwrap(body);
  return arr(root.list?.item).map((it) => ({
    id: str(it.no),
    title: str(it.title),
    cost: num(it.price),
    thumb: str(it.thumb),
    orderUnit: Math.max(1, num(it.unitQty)),
    adultOnly: bool(it.adultOnly),
    url: str(it.url),
  }));
}

interface SelectOpt {
  type?: string;
  set?: { name?: string; opts?: string[] }[];
  data?: Record<string, { name?: string; sup?: unknown; supPrice?: unknown; qty?: unknown; hid?: unknown }>;
}

/** selectOpt(JSON 문자열)를 옵션 그룹과 옵션 목록으로. 도매매(sup)에 보이고 판매 중(hid=0)인 것만 */
export function parseOptions(
  raw: unknown,
  inventory: number,
): { groups: string[]; options: SupplierOption[]; unsupported?: string } {
  if (raw == null || raw === "" || raw === "null") return { groups: [], options: [] };
  let o: SelectOpt;
  try {
    o = typeof raw === "string" ? JSON.parse(raw) : (raw as SelectOpt);
  } catch {
    return { groups: [], options: [], unsupported: "옵션 정보를 읽을 수 없음" };
  }
  if (!o?.data || Object.keys(o.data).length === 0) return { groups: [], options: [] };
  if (o.type && o.type !== "combination") {
    return { groups: [], options: [], unsupported: `지원하지 않는 옵션 형식(${o.type})` };
  }
  const sets = o.set ?? [];
  const groups = sets.map((s, i) => str(s.name) || `옵션${i + 1}`);
  const options: SupplierOption[] = [];
  for (const [code, d] of Object.entries(o.data)) {
    if (!bool(d.sup) || str(d.hid) !== "0") continue;
    const idx = code.split("_").map(Number);
    const values =
      sets.length > 0 && idx.length === sets.length && idx.every((n, i) => sets[i].opts?.[n] != null)
        ? idx.map((n, i) => str(sets[i].opts![n]))
        : str(d.name).split("/").map((s) => s.trim());
    options.push({
      code,
      values,
      extraCost: num(d.supPrice),
      stock: d.qty == null || d.qty === "" ? inventory : num(d.qty),
    });
  }
  return { groups: groups.length > 0 ? groups : ["옵션"], options };
}

/** 상품상세정보(getItemView v4.6) 응답 → 공통 상품 */
export function parseProduct(body: Json): SupplierProduct {
  const r = unwrap(body);
  const basis = r.basis ?? {};
  const price = r.price ?? {};
  const qty = r.qty ?? {};
  const deli = r.deli ?? {};
  const supplyDeli = deli.supply ?? {};
  const detail = r.detail ?? {};
  const thumb = r.thumb ?? {};

  const inventory = num(qty.inventory);
  const opt = parseOptions(r.selectOpt, inventory);

  // 배송비 부담: S 무료, P 선결제, B 착불, C 구매자 선택(선결제로 주문)
  const pay = str(supplyDeli.pay ?? deli.pay).toUpperCase() || "P";
  const shippingPayType = pay === "C" ? "P" : pay;
  const shippingFee = shippingPayType === "S" ? 0 : num(supplyDeli.fee);

  const reasons: string[] = [];
  if (opt.unsupported) reasons.push(opt.unsupported);
  if (shippingPayType === "B") reasons.push("착불 배송 상품");
  if (r.channel && !bool(r.channel.supply)) reasons.push("도매매에서 판매하지 않는 상품");
  if (bool(deli.fromOversea)) reasons.push("해외 직배송 상품");

  const parents = arr(r.category?.parents?.elem).map((c) => str(c.name));
  const current = r.category?.current ?? {};
  const keywords = arr<string>(basis.keywords?.kw ?? basis.keywords).map(str).filter(Boolean);

  return {
    supplier: SUPPLIER_ID,
    id: str(basis.no),
    title: str(basis.title),
    cost: num(price.supply),
    shippingFee,
    shippingPayType,
    extraShippingFee: { jeju: num(deli.feeExtra?.jeju), islands: num(deli.feeExtra?.islands) },
    orderUnit: Math.max(1, num(qty.supplyUnit) || 1),
    stock: opt.options.length > 0 ? opt.options.reduce((s, o) => s + o.stock, 0) : inventory,
    images: [str(thumb.original) || str(thumb.large)].filter(Boolean),
    detailHtml: str(r.desc?.contents?.item),
    optionGroups: opt.groups,
    options: opt.options,
    keywords,
    manufacturer: str(detail.manufacturer),
    model: str(detail.model),
    origin: str(detail.country),
    brand: "",
    adultOnly: bool(basis.adult),
    category: { code: str(current.code), name: str(current.name), path: [...parents, str(current.name)].filter(Boolean) },
    url: `https://domeme.domeggook.com/s/${str(basis.no)}`,
    notice: arr(detail.infoDuty?.item).map((i) => ({ name: str(i.name), value: str(i.desc) })),
    unsupportedReason: reasons.length > 0 ? reasons.join(", ") : undefined,
  };
}

/** 주문서 생성 API의 item[상품번호] 값: 구매채널||배송비부담||옵션코드|수량||판매자 전달사항||배송요청사항 */
export function formatOrderItem(req: PurchaseRequest): string {
  const code = req.optionCode || SINGLE_OPTION_CODE;
  if (!/^\d{2}(_\d{2})*$/.test(code)) throw new DomemeError("BAD_OPTION_CODE", `옵션 코드 "${code}" 형식이 아님`);
  if (!Number.isInteger(req.quantity) || req.quantity < 1) throw new DomemeError("BAD_QUANTITY", `수량 ${req.quantity}`);
  const note = cleanField(stripNonEucKr(req.sellerNote), 256);
  const memo = cleanField(stripNonEucKr(req.recipient.memo), 256);
  return ["supply", req.shippingPayType, `${code}|${req.quantity}`, note, memo].join("||");
}

/**
 * 주문서 생성 API의 deliinfo 값(소비자 정보):
 * 성명|이메일|우편번호|주소1|주소2|휴대전화|추가연락처|쇼핑몰명|통관고유부호
 * 이름·주소를 바꾸면 오배송이 날 수 있어, EUC-KR로 못 쓰는 글자가 있으면 고치지 않고 오류를 냅니다.
 */
export function formatDeliInfo(req: PurchaseRequest): string {
  const r = req.recipient;
  let mobile = formatPhone(r.phone);
  let extra = formatPhone(r.phone2);
  if (!isMobileLike(mobile) && isMobileLike(extra)) [mobile, extra] = [extra, mobile];
  if (!isMobileLike(mobile)) throw new DomemeError("BAD_MOBILE", `휴대전화로 쓸 번호가 없음(${r.phone})`);
  if (extra && !/^0\d{1,3}-\d{3,4}-\d{4}$|^1\d{3}-\d{4}$/.test(extra)) extra = "";

  const zip = r.zipCode.replace(/\D/g, "");
  if (zip.length !== 5) throw new DomemeError("BAD_ZIPCODE", `우편번호 "${r.zipCode}"`);

  const strict = { 성명: r.name, 주소1: r.address1, 주소2: r.address2 };
  for (const [label, v] of Object.entries(strict)) {
    const bad = nonEucKrChars(v);
    if (bad.length > 0) throw new DomemeError("NON_EUCKR", `${label}에 EUC-KR로 못 쓰는 글자(${bad.join("")})`);
  }

  const fields = [
    cleanField(r.name, 20),
    "",
    zip,
    cleanField(r.address1, 200),
    cleanField(r.address2, 200) || "-",
    mobile,
    extra,
    cleanField(stripNonEucKr(req.storeName), 16),
    cleanField(r.customsCode, 13),
  ];
  if (!fields[0] || !fields[3]) throw new DomemeError("BAD_RECIPIENT", "받는 사람 이름이나 주소가 비어 있음");
  return fields.join("|");
}

/** 주문서 생성 응답에서 주문번호 */
export function parseOrderResult(body: Json, productId: string): string {
  const r = unwrap(body);
  if (str(r.result).toUpperCase() !== "SUCCESS") throw new DomemeError("UNKNOWN_RESULT", JSON.stringify(r).slice(0, 300));
  const orders = arr(r.order);
  const mine = orders.find((o) => str(o.itemNo) === productId) ?? orders[0];
  const no = str(mine?.orderNo);
  if (!no) throw new DomemeError("NO_ORDER_NO", "응답에 주문번호가 없음");
  return no;
}
