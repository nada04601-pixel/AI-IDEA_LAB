/**
 * S-08 도움받을 곳. 오프라인에서도 열리도록 앱에 내장한다.
 * ⚠️ 출시 전 공식 출처에서 번호·운영시간을 다시 확인하고 CHECKED_ON을 갱신할 것. (screens.md 6. 미결 사항)
 */
export const CHECKED_ON = '미확인 (출시 전 확인 필요)'

export const CONTACTS = [
  { name: '자살예방상담전화', number: '109', note: '24시간' },
  { name: '정신건강위기상담전화', number: '1577-0199', note: '24시간 · 번호 확인 필요' },
  { name: '긴급 상황 (구급)', number: '119', note: '' },
  { name: '긴급 상황 (경찰)', number: '112', note: '' },
]

export const telHref = (number: string) => `tel:${number.replaceAll('-', '')}`
