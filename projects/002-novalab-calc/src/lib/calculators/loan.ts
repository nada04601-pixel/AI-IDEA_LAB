export type RepaymentMethod = "annuity" | "equalPrincipal" | "bullet";

export const METHOD_LABEL: Record<RepaymentMethod, string> = {
  annuity: "원리금균등",
  equalPrincipal: "원금균등",
  bullet: "만기일시",
};

export type LoanRow = { month: number; principal: number; interest: number; payment: number; balance: number };

export type LoanResult = {
  method: RepaymentMethod;
  firstPayment: number;
  lastPayment: number;
  totalInterest: number;
  totalPayment: number;
  schedule: LoanRow[];
};

export function calcLoan(principal: number, annualRate: number, months: number, method: RepaymentMethod): LoanResult {
  const r = annualRate / 12;
  const n = Math.max(1, Math.floor(months));
  const schedule: LoanRow[] = [];
  let balance = principal;

  const annuityPayment = r === 0 ? principal / n : (principal * r * (1 + r) ** n) / ((1 + r) ** n - 1);

  for (let m = 1; m <= n; m++) {
    const interest = balance * r;
    let p: number;
    if (method === "annuity") p = m === n ? balance : annuityPayment - interest;
    else if (method === "equalPrincipal") p = m === n ? balance : principal / n;
    else p = m === n ? balance : 0;
    balance -= p;
    schedule.push({ month: m, principal: p, interest, payment: p + interest, balance: Math.max(0, balance) });
  }

  const totalInterest = schedule.reduce((s, row) => s + row.interest, 0);
  return {
    method,
    firstPayment: schedule[0].payment,
    lastPayment: schedule[n - 1].payment,
    totalInterest,
    totalPayment: principal + totalInterest,
    schedule,
  };
}
