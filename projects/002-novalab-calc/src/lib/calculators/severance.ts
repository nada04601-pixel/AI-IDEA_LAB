export type SeveranceInput = {
  startDate: string; // 입사일 YYYY-MM-DD
  endDate: string; // 퇴사일(마지막 근무일 다음 날) YYYY-MM-DD
  last3MonthsWage: number; // 퇴직 전 3개월 임금 총액(원)
  annualBonus: number; // 직전 1년 상여금 총액(원)
  annualLeavePay: number; // 직전 1년 연차수당(원)
};

export type SeveranceResult = {
  eligible: boolean;
  serviceDays: number;
  periodDays: number; // 평균임금 산정기간(퇴직 전 3개월) 일수
  averageDailyWage: number;
  severancePay: number;
};

const DAY = 86_400_000;
const parse = (s: string) => {
  const [y, m, d] = s.split("-").map(Number);
  return Date.UTC(y, m - 1, d);
};

export function calcSeverance(input: SeveranceInput): SeveranceResult | null {
  const start = parse(input.startDate);
  const end = parse(input.endDate);
  if (Number.isNaN(start) || Number.isNaN(end) || end <= start) return null;

  const serviceDays = Math.round((end - start) / DAY);
  // 퇴직일 이전 3개월(달력 기준) 일수
  const e = new Date(end);
  const threeMonthsAgo = Date.UTC(e.getUTCFullYear(), e.getUTCMonth() - 3, e.getUTCDate());
  const periodDays = Math.round((end - threeMonthsAgo) / DAY);

  const wages = input.last3MonthsWage + (input.annualBonus * 3) / 12 + (input.annualLeavePay * 3) / 12;
  const averageDailyWage = periodDays > 0 ? wages / periodDays : 0;
  const severancePay = averageDailyWage * 30 * (serviceDays / 365);

  return {
    eligible: serviceDays >= 365,
    serviceDays,
    periodDays,
    averageDailyWage,
    severancePay: Math.floor(severancePay),
  };
}
