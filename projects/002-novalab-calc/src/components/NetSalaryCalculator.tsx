"use client";
import { useMemo, useState } from "react";
import { calcNetSalary } from "@/lib/calculators/netSalary";
import { num, won } from "@/lib/format";

export default function NetSalaryCalculator() {
  const [salaryMan, setSalaryMan] = useState("5000");
  const [nonTax, setNonTax] = useState("200000");
  const [dependents, setDependents] = useState("1");
  const [children, setChildren] = useState("0");

  const r = useMemo(
    () =>
      calcNetSalary({
        annualSalary: num(salaryMan) * 10_000,
        monthlyNonTaxable: num(nonTax),
        dependents: Math.min(Math.max(num(dependents), 1), 11),
        children: Math.min(num(children), 10),
      }),
    [salaryMan, nonTax, dependents, children]
  );

  const rows: [string, number][] = [
    ["국민연금", r.pension],
    ["건강보험", r.health],
    ["장기요양보험", r.longTermCare],
    ["고용보험", r.employment],
    ["소득세", r.incomeTax],
    ["지방소득세", r.localTax],
  ];

  return (
    <div className="calc">
      <div className="fields">
        <label>세전 연봉 (만원)
          <input inputMode="numeric" value={salaryMan} onChange={(e) => setSalaryMan(e.target.value)} />
        </label>
        <label>월 비과세액 (원)
          <input inputMode="numeric" value={nonTax} onChange={(e) => setNonTax(e.target.value)} />
        </label>
        <label>부양가족 수 (본인 포함)
          <input inputMode="numeric" value={dependents} onChange={(e) => setDependents(e.target.value)} />
        </label>
        <label>8~20세 자녀 수
          <input inputMode="numeric" value={children} onChange={(e) => setChildren(e.target.value)} />
        </label>
      </div>

      <div className="result" aria-live="polite">
        <div className="big">
          <span>월 예상 실수령액</span>
          <strong>{won(r.monthlyNet)}</strong>
          <small>연 환산 {won(r.annualNet)}</small>
        </div>
        <table>
          <tbody>
            <tr><th>월 세전 급여</th><td>{won(r.monthlyGross)}</td></tr>
            {rows.map(([k, v]) => (
              <tr key={k}><th>{k}</th><td>- {won(v)}</td></tr>
            ))}
            <tr className="sum"><th>공제 합계</th><td>- {won(r.totalDeduction)}</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
