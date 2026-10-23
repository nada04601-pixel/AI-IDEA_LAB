/** 숫자만 남긴 전화번호를 하이픈 형식으로 바꿉니다. 알 수 없는 형식이면 원래 숫자를 돌려줍니다. */
export function formatPhone(raw: string): string {
  const d = raw.replace(/\D/g, "").replace(/^82(?=1|2|[3-6]\d|70)/, "0");
  if (/^050\d/.test(d) && d.length === 12) return `${d.slice(0, 4)}-${d.slice(4, 8)}-${d.slice(8)}`;
  if (/^02/.test(d) && (d.length === 9 || d.length === 10)) {
    return `02-${d.slice(2, d.length - 4)}-${d.slice(-4)}`;
  }
  if (/^0\d\d/.test(d) && (d.length === 10 || d.length === 11)) {
    return `${d.slice(0, 3)}-${d.slice(3, d.length - 4)}-${d.slice(-4)}`;
  }
  if (/^1\d{7}$/.test(d)) return `${d.slice(0, 4)}-${d.slice(4)}`;
  return d;
}

/** 도매매 주문 API는 휴대전화 칸에 010~019, 050x, 0707로 시작하는 번호만 받습니다 */
export function isMobileLike(phone: string): boolean {
  return /^(01[0-9]|050[2-7]?|0707)-/.test(phone);
}

let eucKrChars: Set<string> | null = null;

/** KS X 1001(EUC-KR) 표에 있는 문자 집합. 처음 쓸 때 한 번 만듭니다 */
function eucKrSet(): Set<string> {
  if (eucKrChars) return eucKrChars;
  const dec = new TextDecoder("euc-kr");
  const set = new Set<string>();
  for (let hi = 0xa1; hi <= 0xfe; hi++) {
    for (let lo = 0xa1; lo <= 0xfe; lo++) {
      const ch = dec.decode(new Uint8Array([hi, lo]));
      if (ch !== "�") set.add(ch);
    }
  }
  eucKrChars = set;
  return set;
}

/** EUC-KR로 나타낼 수 없는 문자들(이모지, 일부 한글 등) */
export function nonEucKrChars(s: string): string[] {
  const set = eucKrSet();
  const bad = new Set<string>();
  for (const ch of s) {
    const c = ch.codePointAt(0)!;
    if (c < 0x80) continue;
    if (!set.has(ch)) bad.add(ch);
  }
  return [...bad];
}

/** EUC-KR로 나타낼 수 없는 문자를 지웁니다(배송 메모처럼 조금 바뀌어도 되는 글에만 씁니다) */
export function stripNonEucKr(s: string): string {
  const bad = new Set(nonEucKrChars(s));
  if (bad.size === 0) return s;
  return [...s].filter((ch) => !bad.has(ch)).join("").replace(/\s{2,}/g, " ").trim();
}

/** 도매매 주문 문자열의 구분자(|)와 줄바꿈을 지웁니다 */
export function cleanField(s: string, max: number): string {
  return s.replace(/[|\r\n\t]+/g, " ").replace(/\s{2,}/g, " ").trim().slice(0, max);
}
