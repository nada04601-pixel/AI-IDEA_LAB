/**
 * S-06/S-07 첫 진료 가이드.
 * 프로토타입: 목록과 틀만 있음. 본문은 별도 콘텐츠 문서로 작성·출처 확인 후 채운다.
 * 비용·제도 관련 글은 반드시 basedOn(정보 기준일)을 표시한다.
 */
export interface Guide {
  slug: string
  section: '처음이라면' | '비용과 지원' | '예약하기'
  title: string
  basedOn?: string
  body: string[] // 문단
  links?: { label: string; url: string }[]
  draft: boolean
}

export const GUIDES: Guide[] = [
  {
    slug: 'where-to-go',
    section: '처음이라면',
    title: '정신건강의학과와 상담센터, 어디로 가야 할까요?',
    body: [],
    draft: true,
  },
  {
    slug: 'first-visit',
    section: '처음이라면',
    title: '첫 진료는 어떻게 진행되나요?',
    body: [],
    draft: true,
  },
  {
    slug: 'records',
    section: '처음이라면',
    title: '진료 기록이 남으면 불이익이 있나요?',
    body: [],
    draft: true,
  },
  {
    slug: 'cost',
    section: '비용과 지원',
    title: '대략적인 비용',
    body: [],
    draft: true,
  },
  {
    slug: 'free-counseling',
    section: '비용과 지원',
    title: '무료로 상담받을 수 있는 곳',
    body: [],
    draft: true,
  },
  {
    slug: 'voucher',
    section: '비용과 지원',
    title: '심리상담 바우처',
    body: [],
    draft: true,
  },
  {
    slug: 'call-script',
    section: '예약하기',
    title: '예약 전화, 이렇게 말해보세요',
    body: [
      '예약 전화는 짧게 끝나도 괜찮아요. 아래 문장을 그대로 읽어도 됩니다.',
      '“안녕하세요, 처음 진료를 받으려고 하는데요. 예약할 수 있을까요?”',
      '병원에서 이름, 연락처, 원하는 날짜를 물어볼 수 있어요. 왜 오시는지 자세히 묻는 경우는 드물고, 물어보면 “요즘 기분이 계속 가라앉아서요” 정도로 말해도 충분해요.',
      '전화가 어렵다면 온라인 예약이나 문자 예약을 받는 곳도 있어요.',
    ],
    draft: false,
  },
]

export const GUIDE_SECTIONS = ['처음이라면', '비용과 지원', '예약하기'] as const

export const findGuide = (slug: string) => GUIDES.find((g) => g.slug === slug)
