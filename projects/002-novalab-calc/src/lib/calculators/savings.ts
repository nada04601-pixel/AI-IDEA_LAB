export type SavingsKind = "deposit" | "installment"; // 예금 | 적금
export type InterestType = "simple" | "monthlyCompound";

export type SavingsInput = {
  kind: SavingsKind;
  amount: number; // 예금: 예치금, 적금: 월 납입액
  annualRate: number; // 연이율(소수)
  months: number;
  interestType: InterestType;
  taxRate: number; // 이자소득세율(소수)
};

export type SavingsResult = {
  principal: number;
  interest: number;
  tax: number;
  afterTax: number; // 세후 수령액
};

export function calcSavings(i: SavingsInput): SavingsResult {
  const n = Math.max(1, Math.floor(i.months));
  const r = i.annualRate / 12;
  let principal: number;
  let interest: number;

  if (i.kind === "deposit") {
    principal = i.amount;
    interest = i.interestType === "simple" ? i.amount * r * n : i.amount * ((1 + r) ** n - 1);
  } else {
    principal = i.amount * n;
    interest = 0;
    // k번째 달에 낸 돈은 (n - k + 1)개월 동안 이자가 붙음
    for (let k = 1; k <= n; k++) {
      const m = n - k + 1;
      interest += i.interestType === "simple" ? i.amount * r * m : i.amount * ((1 + r) ** m - 1);
    }
  }

  interest = Math.floor(interest);
  const tax = Math.floor((interest * i.taxRate) / 10) * 10;
  return { principal, interest, tax, afterTax: principal + interest - tax };
}
