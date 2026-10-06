export const won = (n: number) => `${Math.round(n).toLocaleString("ko-KR")}원`;
export const num = (v: string) => Number(v.replace(/[^0-9.]/g, "")) || 0;
export const pct = (r: number, digits = 1) => `${(r * 100).toFixed(digits)}%`;
