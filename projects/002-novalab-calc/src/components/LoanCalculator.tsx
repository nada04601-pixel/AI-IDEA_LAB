"use client";
import { useMemo, useState } from "react";
import { calcLoan, METHOD_LABEL, type RepaymentMethod } from "@/lib/calculators/loan";
import { num, won } from "@/lib/format";

const METHODS = Object.keys(METHOD_LABEL) as RepaymentMethod[];

export default function LoanCalculator() {
  const [amountMan, setAmountMan] = useState("10000");
  const [rate, setRate] = useState("4.5");
  const [years, setYears] = useState("5");
  const [method, setMethod] = useState<RepaymentMethod>("annuity");

  const principal = num(amountMan) * 10_000;
  const months = Math.min(Math.max(Math.round(num(years) * 12), 1), 600);
  const annualRate = Math.min(num(rate), 100) / 100;

  const results = useMemo(
    () => METHODS.map((m) => calcLoan(principal, annualRate, months, m)),
    [principal, annualRate, months]
  );
  const selected = results.find((r) => r.method === method)!;

  return (
    <div className="calc">
      <div className="fields">
        <label>대출 금액 (만원)
          <input inputMode="numeric" value={amountMan} onChange={(e) => setAmountMan(e.target.value)} />
        </label>
        <label>연 이자율 (%)
          <input inputMode="decimal" value={rate} onChange={(e) => setRate(e.target.value)} />
        </label>
        <label>상환 기간 (년)
          <input inputMode="decimal" value={years} onChange={(e) => setYears(e.target.value)} />
        </label>
        <label>상환 방식
          <select value={method} onChange={(e) => setMethod(e.target.value as RepaymentMethod)}>
            {METHODS.map((m) => <option key={m} value={m}>{METHOD_LABEL[m]}</option>)}
          </select>
        </label>
      </div>

      <div className="result" aria-live="polite">
        <div className="big">
          <span>{METHOD_LABEL[method]} 첫 달 상환액</span>
          <strong>{won(selected.firstPayment)}</strong>
          <small>총 이자 {won(selected.totalInterest)}</small>
        </div>

        <table>
          <thead>
            <tr><th>상환 방식</th><td>첫 달</td><td>총 이자</td></tr>
          </thead>
          <tbody>
            {results.map((r) => (
              <tr key={r.method} className={r.method === method ? "sum" : undefined}>
                <th>{METHOD_LABEL[r.method]}</th>
                <td>{won(r.firstPayment)}</td>
                <td>{won(r.totalInterest)}</td>
              </tr>
            ))}
          </tbody>
        </table>

        <details>
          <summary>{METHOD_LABEL[method]} 월별 상환 일정 보기 ({months}회)</summary>
          <div className="scroll">
            <table>
              <thead>
                <tr><th>회차</th><td>원금</td><td>이자</td><td>상환액</td><td>잔액</td></tr>
              </thead>
              <tbody>
                {selected.schedule.map((row) => (
                  <tr key={row.month}>
                    <th>{row.month}</th>
                    <td>{won(row.principal)}</td>
                    <td>{won(row.interest)}</td>
                    <td>{won(row.payment)}</td>
                    <td>{won(row.balance)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      </div>
    </div>
  );
}
