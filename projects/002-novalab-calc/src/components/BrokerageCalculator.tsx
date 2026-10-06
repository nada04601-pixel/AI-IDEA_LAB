"use client";
import { useMemo, useState } from "react";
import { calcBrokerage, type DealType } from "@/lib/calculators/brokerage";
import { num, pct, won } from "@/lib/format";

export default function BrokerageCalculator() {
  const [type, setType] = useState<DealType>("sale");
  const [priceMan, setPriceMan] = useState("50000");
  const [depositMan, setDepositMan] = useState("1000");
  const [rentMan, setRentMan] = useState("60");

  const r = useMemo(
    () => calcBrokerage(type, num(priceMan) * 10_000, num(depositMan) * 10_000, num(rentMan) * 10_000),
    [type, priceMan, depositMan, rentMan]
  );

  return (
    <div className="calc">
      <div className="fields">
        <label>거래 종류
          <select value={type} onChange={(e) => setType(e.target.value as DealType)}>
            <option value="sale">매매·교환</option>
            <option value="jeonse">전세</option>
            <option value="monthly">월세</option>
          </select>
        </label>
        {type === "monthly" ? (
          <>
            <label>보증금 (만원)
              <input inputMode="numeric" value={depositMan} onChange={(e) => setDepositMan(e.target.value)} />
            </label>
            <label>월세 (만원)
              <input inputMode="numeric" value={rentMan} onChange={(e) => setRentMan(e.target.value)} />
            </label>
          </>
        ) : (
          <label>{type === "sale" ? "매매가 (만원)" : "전세 보증금 (만원)"}
            <input inputMode="numeric" value={priceMan} onChange={(e) => setPriceMan(e.target.value)} />
          </label>
        )}
      </div>

      <div className="result" aria-live="polite">
        <div className="big">
          <span>중개보수 상한 (부가세 별도)</span>
          <strong>{won(r.fee)}</strong>
          <small>부가세 포함 시 최대 {won(r.fee + r.vat)}</small>
        </div>
        <table>
          <tbody>
            <tr><th>계산 기준 거래금액</th><td>{won(r.dealAmount)}</td></tr>
            <tr><th>상한 요율</th><td>{pct(r.rate)}</td></tr>
            <tr><th>한도액</th><td>{r.limit ? won(r.limit) : "없음"}</td></tr>
            <tr className="sum"><th>중개보수 상한</th><td>{won(r.fee)}</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
