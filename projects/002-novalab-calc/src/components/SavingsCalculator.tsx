"use client";
import { useMemo, useState } from "react";
import { calcSavings, type InterestType, type SavingsKind } from "@/lib/calculators/savings";
import { RATES } from "@/data/rates/2026";
import { num, won } from "@/lib/format";

const TAX = {
  normal: `일반과세 (${(RATES.interestTax.normal * 100).toFixed(1)}%)`,
  preferential: `세금우대 (${(RATES.interestTax.preferential * 100).toFixed(1)}%)`,
  exempt: "비과세 (0%)",
} as const;
type TaxKey = keyof typeof TAX;

export default function SavingsCalculator() {
  const [kind, setKind] = useState<SavingsKind>("installment");
  const [amount, setAmount] = useState("500000");
  const [rate, setRate] = useState("3.5");
  const [months, setMonths] = useState("12");
  const [interestType, setInterestType] = useState<InterestType>("simple");
  const [tax, setTax] = useState<TaxKey>("normal");

  const r = useMemo(
    () =>
      calcSavings({
        kind,
        amount: num(amount),
        annualRate: Math.min(num(rate), 100) / 100,
        months: Math.min(Math.max(num(months), 1), 600),
        interestType,
        taxRate: RATES.interestTax[tax],
      }),
    [kind, amount, rate, months, interestType, tax]
  );

  return (
    <div className="calc">
      <div className="fields">
        <label>상품 종류
          <select value={kind} onChange={(e) => setKind(e.target.value as SavingsKind)}>
            <option value="installment">적금 (매달 납입)</option>
            <option value="deposit">예금 (한 번에 예치)</option>
          </select>
        </label>
        <label>{kind === "deposit" ? "예치 금액 (원)" : "월 납입액 (원)"}
          <input inputMode="numeric" value={amount} onChange={(e) => setAmount(e.target.value)} />
        </label>
        <label>연 이자율 (%)
          <input inputMode="decimal" value={rate} onChange={(e) => setRate(e.target.value)} />
        </label>
        <label>기간 (개월)
          <input inputMode="numeric" value={months} onChange={(e) => setMonths(e.target.value)} />
        </label>
        <label>이자 계산 방식
          <select value={interestType} onChange={(e) => setInterestType(e.target.value as InterestType)}>
            <option value="simple">단리</option>
            <option value="monthlyCompound">월복리</option>
          </select>
        </label>
        <label>과세 구분
          <select value={tax} onChange={(e) => setTax(e.target.value as TaxKey)}>
            {(Object.keys(TAX) as TaxKey[]).map((k) => <option key={k} value={k}>{TAX[k]}</option>)}
          </select>
        </label>
      </div>

      <div className="result" aria-live="polite">
        <div className="big">
          <span>만기 세후 수령액</span>
          <strong>{won(r.afterTax)}</strong>
          <small>세후 이자 {won(r.interest - r.tax)}</small>
        </div>
        <table>
          <tbody>
            <tr><th>원금 합계</th><td>{won(r.principal)}</td></tr>
            <tr><th>세전 이자</th><td>{won(r.interest)}</td></tr>
            <tr><th>이자소득세</th><td>- {won(r.tax)}</td></tr>
            <tr className="sum"><th>세후 수령액</th><td>{won(r.afterTax)}</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
