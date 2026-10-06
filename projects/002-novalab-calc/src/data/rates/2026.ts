// 2026년 요율·기준값. 매년(특히 국민연금 상·하한은 7월) 확인 후 갱신하세요.
// 출처: 국민연금공단, 국민건강보험공단, 고용노동부, 국세청 / 확인일 2026-10
export const RATES = {
  year: 2026,
  checkedAt: "2026년 10월",
  pension: { rate: 0.0475, minBase: 410_000, maxBase: 6_590_000 }, // 근로자 부담 4.75%, 2026.7~2027.6 상·하한
  health: { rate: 0.03595 }, // 근로자 부담 3.595%
  longTermCare: { rateOfHealth: 0.1314 }, // 건강보험료의 13.14%
  employment: { rate: 0.009 }, // 근로자 부담 0.9%
  incomeTax: {
    brackets: [
      { upTo: 14_000_000, rate: 0.06 },
      { upTo: 50_000_000, rate: 0.15 },
      { upTo: 88_000_000, rate: 0.24 },
      { upTo: 150_000_000, rate: 0.35 },
      { upTo: 300_000_000, rate: 0.38 },
      { upTo: 500_000_000, rate: 0.4 },
      { upTo: 1_000_000_000, rate: 0.42 },
      { upTo: Infinity, rate: 0.45 },
    ],
    personalDeduction: 1_500_000, // 인적공제 1인당
    mealTaxFreeLimit: 200_000, // 식대 비과세 월 한도
  },
  localTaxRate: 0.1, // 지방소득세 = 소득세의 10%
  minimumWage: 10_320, // 2026년 최저시급(원)
  interestTax: { normal: 0.154, preferential: 0.095, exempt: 0 }, // 이자소득세(지방세 포함)
  // 주택 중개보수 상한요율(2021.10.19 시행). limit은 한도액(원), 없으면 한도 없음
  brokerage: {
    sale: [
      { under: 50_000_000, rate: 0.006, limit: 250_000 },
      { under: 200_000_000, rate: 0.005, limit: 800_000 },
      { under: 900_000_000, rate: 0.004 },
      { under: 1_200_000_000, rate: 0.005 },
      { under: 1_500_000_000, rate: 0.006 },
      { under: Infinity, rate: 0.007 },
    ],
    lease: [
      { under: 50_000_000, rate: 0.005, limit: 200_000 },
      { under: 100_000_000, rate: 0.004, limit: 300_000 },
      { under: 600_000_000, rate: 0.003 },
      { under: 1_200_000_000, rate: 0.004 },
      { under: 1_500_000_000, rate: 0.005 },
      { under: Infinity, rate: 0.006 },
    ],
  } as Record<"sale" | "lease", { under: number; rate: number; limit?: number }[]>,
};
