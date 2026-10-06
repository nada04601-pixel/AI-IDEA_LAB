"use client";
import { useMemo, useState } from "react";
import { calcSeverance } from "@/lib/calculators/severance";
import { num, won } from "@/lib/format";

export default function SeveranceCalculator() {
  const [start, setStart] = useState("2022-03-02");
  const [end, setEnd] = useState("2026-10-01");
  const [wage, setWage] = useState("10500000");
  const [bonus, setBonus] = useState("3000000");
  const [leave, setLeave] = useState("0");

  const r = useMemo(
    () =>
      calcSeverance({
        startDate: start,
        endDate: end,
        last3MonthsWage: num(wage),
        annualBonus: num(bonus),
        annualLeavePay: num(leave),
      }),
    [start, end, wage, bonus, leave]
  );

  return (
    <div className="calc">
      <div className="fields">
        <label>입사일
          <input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
        </label>
        <label>퇴직일 (마지막 근무일 다음 날)
          <input type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
        </label>
        <label>퇴직 전 3개월 임금 총액 (원)
          <input inputMode="numeric" value={wage} onChange={(e) => setWage(e.target.value)} />
        </label>
        <label>직전 1년 상여금 총액 (원)
          <input inputMode="numeric" value={bonus} onChange={(e) => setBonus(e.target.value)} />
        </label>
        <label>직전 1년 연차수당 (원)
          <input inputMode="numeric" value={leave} onChange={(e) => setLeave(e.target.value)} />
        </label>
      </div>

      <div className="result" aria-live="polite">
        {!r ? (
          <p className="warn">퇴직일은 입사일보다 뒤여야 합니다.</p>
        ) : (
          <>
            <div className="big">
              <span>예상 퇴직금 (세전)</span>
              <strong>{won(r.severancePay)}</strong>
              <small>재직 {r.serviceDays.toLocaleString("ko-KR")}일</small>
            </div>
            {!r.eligible && (
              <p className="warn">재직 기간이 1년 미만이면 법정 퇴직금 지급 대상이 아닙니다. 참고용으로만 보세요.</p>
            )}
            <table>
              <tbody>
                <tr><th>평균임금 산정 기간</th><td>{r.periodDays}일</td></tr>
                <tr><th>1일 평균임금</th><td>{won(r.averageDailyWage)}</td></tr>
                <tr className="sum"><th>퇴직금 = 1일 평균임금 × 30 × 재직일수 ÷ 365</th><td>{won(r.severancePay)}</td></tr>
              </tbody>
            </table>
          </>
        )}
      </div>
    </div>
  );
}
