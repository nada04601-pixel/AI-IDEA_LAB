"use client";
import { useMemo, useState } from "react";
import { calcWeeklyHolidayPay } from "@/lib/calculators/weeklyHolidayPay";
import { RATES } from "@/data/rates/2026";
import { num, won } from "@/lib/format";

export default function WeeklyHolidayPayCalculator() {
  const [wage, setWage] = useState(String(RATES.minimumWage));
  const [hours, setHours] = useState("8");
  const [days, setDays] = useState("5");

  const hourly = num(wage);
  const r = useMemo(
    () => calcWeeklyHolidayPay(hourly, Math.min(num(hours), 24), Math.min(num(days), 7)),
    [hourly, hours, days]
  );
  const belowMinimum = hourly > 0 && hourly < RATES.minimumWage;

  return (
    <div className="calc">
      <div className="fields">
        <label>시급 (원)
          <input inputMode="numeric" value={wage} onChange={(e) => setWage(e.target.value)} />
        </label>
        <label>하루 근무 시간
          <input inputMode="decimal" value={hours} onChange={(e) => setHours(e.target.value)} />
        </label>
        <label>주 근무 일수
          <input inputMode="numeric" value={days} onChange={(e) => setDays(e.target.value)} />
        </label>
      </div>

      <div className="result" aria-live="polite">
        <div className="big">
          <span>주휴수당 포함 월급 (세전)</span>
          <strong>{won(r.monthlyPay)}</strong>
          <small>주급 {won(r.weeklyPay)}</small>
        </div>
        {belowMinimum && (
          <p className="warn">입력한 시급이 {RATES.year}년 최저시급 {won(RATES.minimumWage)}보다 낮습니다.</p>
        )}
        {!r.eligible && (
          <p className="warn">주 소정근로시간이 15시간 미만이면 주휴수당이 발생하지 않습니다.</p>
        )}
        <table>
          <tbody>
            <tr><th>주 근무 시간</th><td>{r.weeklyHours}시간</td></tr>
            <tr><th>주휴 시간</th><td>{r.holidayHours.toFixed(1)}시간</td></tr>
            <tr><th>주휴수당 (주)</th><td>{won(r.holidayPay)}</td></tr>
            <tr><th>월 환산 시간</th><td>{r.monthlyHours.toFixed(1)}시간</td></tr>
            <tr className="sum"><th>월 환산 급여</th><td>{won(r.monthlyPay)}</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
