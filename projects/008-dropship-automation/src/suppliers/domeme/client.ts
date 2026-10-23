import { request } from "../../core/http.ts";
import type { PurchaseRequest, PurchaseResult, SupplierAdapter, SupplierProduct, SupplierSearchItem, SupplierSearchQuery } from "../../core/types.ts";
import {
  DomemeError,
  SUPPLIER_ID,
  formatDeliInfo,
  formatOrderItem,
  parseOrderResult,
  parseProduct,
  parseSearch,
  unwrap,
} from "./parse.ts";

const API = "https://domeggook.com/ssl/api/";
/** 로그인 유지(loginKeep=on)는 30일. 넉넉히 20일마다 새로 로그인합니다 */
const SESSION_DAYS = 20;

export interface DomemeConfig {
  /** Open API 키(주문은 Private API 권한 승인이 필요) */
  apiKey: string;
  /** 주문용 사업자 회원 아이디. 도매매 상품은 사업자 회원만 주문할 수 있습니다 */
  userId: string;
  password: string;
  /** 이 프로그램이 도는 컴퓨터의 공인 IP(로그인 API 필수값) */
  clientIp: string;
  /** API로 만든 주문서를 구분하는 영문 이름 */
  alliance: string;
  /** 현금영수증 자동 발행 */
  cashReceipt: boolean;
}

export interface KeyValue {
  getState(key: string): string | null;
  setState(key: string, value: string): void;
}

export class DomemeSupplier implements SupplierAdapter {
  readonly id = SUPPLIER_ID;
  private cfg: DomemeConfig;
  private kv: KeyValue;

  constructor(cfg: DomemeConfig, kv: KeyValue) {
    this.cfg = cfg;
    this.kv = kv;
  }

  async search(q: SupplierSearchQuery): Promise<SupplierSearchItem[]> {
    const params: Record<string, string> = {
      ver: "4.1",
      mode: "getItemList",
      aid: this.cfg.apiKey,
      market: "supply",
      om: "json",
      sz: String(q.size ?? 50),
      pg: String(q.page ?? 1),
    };
    if (q.keyword) params.kw = q.keyword;
    if (q.category) params.ca = q.category;
    if (q.minPrice != null) params.mnp = String(q.minPrice);
    if (q.maxPrice != null) params.mxp = String(q.maxPrice);
    if (q.sort) params.so = q.sort;
    return parseSearch(await this.get(params));
  }

  async getProduct(id: string): Promise<SupplierProduct> {
    return parseProduct(await this.get({ ver: "4.6", mode: "getItemView", aid: this.cfg.apiKey, no: id, om: "json" }));
  }

  /**
   * 주문서 생성. 이머니(현금성)가 바로 빠져나가므로 재시도하지 않습니다.
   * 단 "주문 전에 정보가 변경된 상품"은 주문서가 안 만들어진 경우라 한 번만 다시 보냅니다(연동 가이드 2.5).
   */
  async purchase(req: PurchaseRequest): Promise<PurchaseResult> {
    const form = {
      ver: "4.3",
      mode: "setOrder",
      aid: this.cfg.apiKey,
      id: this.cfg.userId,
      receipt: this.cfg.cashReceipt ? "1" : "0",
      market: "supply",
      [`item[${req.productId}]`]: formatOrderItem(req),
      deliinfo: formatDeliInfo(req),
      notify: "false",
      alliance: this.cfg.alliance,
      ie: "utf-8",
      oe: "utf-8",
      om: "json",
    };
    for (let attempt = 0; ; attempt++) {
      try {
        const body = await this.postWithSession(form);
        return { supplierOrderNo: parseOrderResult(body, req.productId) };
      } catch (e) {
        if (e instanceof DomemeError && e.code === "ITEM_INFO_CHANGED_ERROR" && attempt === 0) continue;
        throw e;
      }
    }
  }

  private async get(params: Record<string, string>): Promise<Record<string, any>> {
    const res = await request(`${API}?${new URLSearchParams(params)}`);
    return (await res.json()) as Record<string, any>;
  }

  private async post(form: Record<string, string>): Promise<Record<string, any>> {
    const res = await request(API, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams(form),
      retries: 0,
    });
    return (await res.json()) as Record<string, any>;
  }

  /** 로그인 세션(sId)을 붙여 보냅니다. 세션이 만료됐다는 오류면 다시 로그인해 한 번 더 보냅니다 */
  private async postWithSession(form: Record<string, string>): Promise<Record<string, any>> {
    for (let attempt = 0; ; attempt++) {
      const sId = await this.session(attempt > 0);
      const body = await this.post({ ...form, sId });
      try {
        unwrap(body);
        return body;
      } catch (e) {
        if (e instanceof DomemeError && e.code === "INCORRECT_CERTIFICATE" && attempt === 0) continue;
        throw e;
      }
    }
  }

  private async session(forceNew: boolean): Promise<string> {
    if (!this.cfg.userId || !this.cfg.password || !this.cfg.clientIp) {
      throw new DomemeError("NO_LOGIN_CONFIG", "주문하려면 DOMEME_USER_ID, DOMEME_PASSWORD, DOMEME_CLIENT_IP가 필요합니다");
    }
    const key = `domeme.session.${this.cfg.userId}`;
    if (!forceNew) {
      const saved = this.kv.getState(key);
      if (saved) {
        const { sId, until } = JSON.parse(saved) as { sId: string; until: number };
        if (Date.now() < until) return sId;
      }
    }
    const r = unwrap(
      await this.post({
        ver: "4.1",
        mode: "setLogin",
        aid: this.cfg.apiKey,
        id: this.cfg.userId,
        pw: this.cfg.password,
        om: "json",
        oe: "utf-8",
        loginKeep: "on",
        userAgent: "dropship-automation",
        ip: this.cfg.clientIp,
        device: "thirdparty",
      }),
    );
    const sId = String(r.sId ?? "");
    if (!sId) throw new DomemeError("LOGIN_FAILED", "로그인 응답에 sId가 없음");
    this.kv.setState(key, JSON.stringify({ sId, until: Date.now() + SESSION_DAYS * 86_400_000 }));
    return sId;
  }
}
