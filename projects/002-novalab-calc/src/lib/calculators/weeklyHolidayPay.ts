// 한 달 평균 주 수(365 ÷ 7 ÷ 12)
export const WEEKS_PER_MONTH = 365 / 7 / 12;

export type HolidayPayResult = {
  weeklyHours: number;
  eligible: boolean; // 주 15시간 이상
  holidayHours: number;
  weeklyPay: number; // 주휴수당 포함 주급
  holidayPay: number; // 주휴수당
  monthlyHours: number; // 주휴 포함 월 환산 시간
  monthlyPay: number;
};

export function calcWeeklyHolidayPay(hourlyWage: number, hoursPerDay: number, daysPerWeek: number): HolidayPayResult {
  const weeklyHours = hoursPerDay * daysPerWeek;
  const eligible = weeklyHours >= 15;
  const holidayHours = eligible ? (Math.min(weeklyHours, 40) / 40) * 8 : 0;
  const holidayPay = holidayHours * hourlyWage;
  const monthlyHours = (weeklyHours + holidayHours) * WEEKS_PER_MONTH;
  return {
    weeklyHours,
    eligible,
    holidayHours,
    holidayPay,
    weeklyPay: weeklyHours * hourlyWage + holidayPay,
    monthlyHours,
    monthlyPay: monthlyHours * hourlyWage,
  };
}
