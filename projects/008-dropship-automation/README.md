# 위탁판매 자동화 (008 프로토타입)

도매처 상품을 찾아 판매처에 등록하고, 주문이 들어오면 도매처에 고객 배송지로 발주하는 프로그램입니다.
지금은 **도매매 → 네이버 스마트스토어**를 지원하고, 쿠팡이나 다른 도매처는 어댑터만 더하면 같은 흐름에 붙습니다.

```
[소싱]  도매매 검색 → 규칙으로 고르기(가격·재고·제외 낱말) → 판매가 계산 → 스마트스토어 등록
[주문]  스마트스토어 결제 완료 주문 → 안전장치 확인 → 도매매 주문서 생성(고객 배송지) → 스마트스토어 발주 확인
```

- 설계 문서: [ideas/008-dropship-automation](../../ideas/008-dropship-automation/idea.md)
- 상태: **구상 단계 + 프로토타입 CLI** (실제 API 키로는 아직 검증 전). 설치형/SaaS 중 제품 형태는 미정

## 꼭 알아야 할 것

- **고정 IP 컴퓨터에서 실행해야 합니다.** 네이버 커머스API는 애플리케이션에 등록한 "API 호출 IP"에서만 응답합니다. GitHub Actions나 Cloudflare Worker는 IP가 바뀌어 쓸 수 없습니다. 집·사무실 PC(고정 IP), 미니 PC, 고정 IP VPS 중 하나를 쓰세요.
- **도매매 주문은 사업자 회원 + Private API 승인이 필요합니다.** 도매매 상품은 사업자 회원만 주문할 수 있고, 주문서 생성 API(setOrder)는 도매꾹 OpenAPI 화면에서 Private API 권한을 신청해 승인받아야 합니다.
- **도매매 주문은 이머니(현금성)로 바로 결제됩니다.** 잔액이 모자라면 주문이 실패하니 미리 충전해 두세요.
- **기본은 미리 보기입니다.** `--live`를 붙여야 실제로 상품을 등록하고 발주합니다. 처음에는 꼭 미리 보기로 결과를 확인하세요.

## 준비

1. Node.js 22.18 이상 설치(타입스크립트를 빌드 없이 바로 실행합니다)
2. 네이버 [커머스API센터](https://apicenter.commerce.naver.com)에서 스마트스토어 통합매니저 계정으로 애플리케이션 등록
   - 권한: 상품, 주문
   - API 호출 IP: 이 프로그램을 돌릴 컴퓨터의 공인 IP
   - 애플리케이션 ID·시크릿을 받아 둡니다
3. 도매꾹 > OpenAPI > API 발급/관리에서 Open API 키 발급, 주문까지 쓰려면 Private API 권한 신청
4. 설정 파일 만들기
   ```bash
   cd projects/008-dropship-automation
   npm install
   cp .env.example .env               # 키·아이디·비밀번호·공인 IP
   cp config.example.json config.json # 가격 규칙·필터·검색 작업
   ```
   `.env`, `config.json`, `data/`는 git에 올라가지 않습니다.

## 사용법

```bash
npm run cli -- categories 텀블러          # 스마트스토어 카테고리 ID 찾기 → config.json jobs에 넣기
npm run cli -- search 텀블러              # 도매매 검색, 예상 판매가
npm run cli -- inspect 12345678           # 상품 상세와 등록 가능 여부(옵션·배송비·이익)
npm run cli -- register 12345678 --category 50000000          # 미리 보기
npm run cli -- register 12345678 --category 50000000 --live   # 실제 등록
npm run cli -- source --live              # config.json jobs대로 검색해서 등록
npm run cli -- orders                     # 새 주문 미리 보기(어떤 주소로 무엇을 발주할지)
npm run cli -- orders --live              # 실제 발주 + 스마트스토어 발주 확인
npm run cli -- status                     # 사람이 볼 주문(보류·실패·불명)
npm run cli -- approve 2026102312345001   # 확인한 주문을 다음 실행 때 발주
```

`orders --live`는 사람이 확인할 주문이 있으면 종료 코드 2로 끝나므로, 예약 실행에서 알림을 걸 수 있습니다.

### 자동 실행

주문 처리는 10~30분마다, 상품 소싱은 하루 한두 번이면 충분합니다.

```cron
*/15 * * * * cd /path/to/projects/008-dropship-automation && npm run -s cli -- orders --live >> data/orders.log 2>&1
10 9 * * *   cd /path/to/projects/008-dropship-automation && npm run -s cli -- source --live >> data/source.log 2>&1
```

Windows는 작업 스케줄러에서 같은 명령을 등록하면 됩니다.

## 주문 처리 안전장치

| 상황 | 처리 |
|---|---|
| 같은 상품주문을 두 번 처리 | 저장소(`data/dropship.db`)에 상품주문번호로 기록해 다시 발주하지 않음 |
| 발주를 보내고 응답 전에 멈춤(정전·네트워크) | `unknown`으로 두고 자동 재발주 안 함. 도매매에서 주문 여부를 확인 |
| 이미 발주 확인했거나 취소·반품 요청이 있는 주문 | 건너뜀(판매자센터에서 직접 처리한 주문과 겹치지 않음) |
| 등록 때보다 공급가가 5% 넘게 오름 | `held`(보류) |
| 발주 금액이 고객 결제 금액보다 큼(역마진) | 보류 |
| 발주 금액이 한도(`maxOrderAmount`) 초과 | 보류 |
| 공급처 옵션이 사라졌거나 재고 부족 | 보류 |
| 받는 사람 이름·주소에 EUC-KR로 못 쓰는 글자(예: 똠), 휴대전화 없음 | 보류(도매매 주문 API 제약. 주소를 바꾸면 오배송 위험이 있어 고치지 않음) |
| 도매매가 거절(품절·이머니 부족 등) | `failed` |
| 실행당 발주 한도 초과, 도매매 조회 일시 오류 | `pending`, 다음 실행에 자동 처리 |
| 스마트스토어 발주 확인 실패 | `ordered`로 두고 다음 실행에 다시 확인 |

보류·실패·불명 주문은 `status`로 보고, 처리 방법을 정한 뒤 `approve`하면 다음 실행에서 안전장치 없이 발주합니다.
판매자센터에서 직접 처리하기로 했다면 승인하지 않고 두면 됩니다.

## 설계

```
src/
  core/                 판매처·공급처를 모르는 공통 흐름
    types.ts            공통 모델과 어댑터 인터페이스(SupplierAdapter, MarketAdapter)
    pricing.ts          판매가 = (원가 + 고정비 [+ 배송비]) × (1 + 이익률) ÷ (1 − 수수료율)
    listing.ts          공급처 상품 → 판매처 상품(필터·가격·재고 상한)
    sourcing.ts         검색 → 등록
    fulfillment.ts      주문 → 발주 → 발주 확인, 안전장치
  suppliers/domeme/     도매매 어댑터(상품리스트 v4.1, 상품상세 v4.6, 로그인 v4.1, 주문서 생성 v4.3)
  markets/smartstore/   스마트스토어 어댑터(OAuth 전자서명, 이미지 업로드, 상품 등록 v2, 주문 조회·발주 확인)
  store/store.ts        SQLite(node:sqlite): 등록 기록, 발주 기록, 조회 커서
  registry.ts           어댑터 등록부(새 공급처·판매처는 여기에 한 줄)
  cli.ts
```

### 주문과 공급처 상품을 잇는 방법

상품을 등록할 때 스마트스토어 **판매자 관리 코드**에 `domeme:<도매매 상품번호>`, 각 옵션의 **옵션 관리 코드**에 도매매 옵션 코드(`00_01` 등)를 넣습니다.
주문이 들어오면 주문 정보의 `sellerProductCode`·`optionManageCode`로 그대로 돌아오므로, 별도 매핑표 없이도 어떤 도매처의 어떤 옵션을 발주할지 압니다.
판매자센터에서 상품을 복사하거나 고쳐도 이 코드만 남아 있으면 계속 동작합니다(코드가 비면 저장소의 등록 기록으로 찾습니다).

### 쿠팡 붙이기

`src/markets/coupang/`에 `MarketAdapter`를 구현합니다.

- `registerProduct`: 쿠팡 상품 생성 API. `Listing.sourceKey`를 쿠팡의 판매자 상품 코드(externalVendorSku 등)에, 옵션 코드를 옵션별 판매자 코드에 넣습니다
- `fetchPaidOrders`/`getOrderLines`: 발주서 목록 조회(결제 완료 상태) → `MarketOrderLine`
- `confirmOrders`: 상품준비중 처리
- 쿠팡 카테고리·고시정보·필수 속성은 스마트스토어와 달라 `config.json`에 `coupang` 기본값 칸을 따로 둡니다

그다음 `registry.ts`의 `marketFactories`에 `coupang`을 더하고 `config.json`의 `market`을 바꾸면 소싱·주문 흐름은 그대로 씁니다.
두 판매처를 동시에 돌리려면 판매처마다 설정 파일을 하나씩 두고(`--config coupang.json`) 같은 `data/` 폴더를 쓰게 하면 됩니다.
저장소의 등록·발주 기록은 판매처 이름으로 나뉘어 있어 섞이지 않습니다.

### 다른 도매처 붙이기

`src/suppliers/<이름>/`에 `SupplierAdapter`(search, getProduct, purchase)를 구현하고 `registry.ts`의 `supplierFactories`에 더합니다.
판매자 관리 코드가 `<이름>:<상품번호>`가 되므로, 주문 처리는 주문마다 알맞은 도매처로 자동으로 나뉩니다.
발주 결과가 확실하지 않은 오류(응답 없음, 일부만 주문 등)는 `SupplierError(code, message, orderMayExist = true)`로 던지면 자동 재발주를 막습니다.

### 다음 단계로 생각해 둔 기능

- **송장 연동**: 도매매 "구매 주문서 목록/상세 조회"(Private API)로 송장번호를 읽어 스마트스토어 발송 처리(`/v1/pay-order/seller/product-orders/dispatch`). `SupplierAdapter`에 `getShipments`, `MarketAdapter`에 `dispatch`를 더하는 방식
- **가격·재고 동기화**: 도매매 "전체품절확인목록"이나 상품정보 동기화 API로 바뀐 상품을 찾아 스마트스토어 가격·재고 수정, 품절 시 판매 중지
- **취소·반품**: 스마트스토어 취소 요청 → 도매매 "구매취소 신청"
- **같은 주문의 여러 상품 묶어 발주**: 지금은 상품주문 1건마다 주문서 1장(배송비가 따로 붙을 수 있음)
- **알림**: `orders` 종료 코드 2일 때 카카오톡·슬랙·메일로 알림

## 확인된 것과 직접 확인할 것

- 도매매 API 형식은 도매꾹 OpenAPI 문서(상품리스트, 상품상세정보, 주문옵션 가이드, 주문서 생성 연동 가이드 2026-07-07판)를, 스마트스토어 API는 커머스API 문서 2.90.1을 기준으로 만들었습니다. 전자서명은 문서의 예시 값으로 테스트합니다
- 실제 키로는 아직 호출해 보지 않았습니다. 처음 쓸 때 `inspect` → `register`(미리 보기) → `register --live`로 상품 하나를 올려 판매자센터에서 확인하고, 주문 처리도 미리 보기 결과를 먼저 보세요
- 카테고리에 따라 KC 인증 등 추가 항목이 필요할 수 있습니다. 등록이 거절되면 오류 메시지의 항목을 `config.json`의 `smartstore.detailAttributeExtra`에 넣으세요(예: `{"certificationTargetExcludeContent": {"kcCertifiedProductExclusionYn": "TRUE"}}`)
- 원산지는 국산이면 "국산", 그 밖에는 "상세설명에 표시"로 등록합니다. 상세 이미지에 원산지가 없는 상품은 판매자센터에서 고쳐 주세요
- 위탁판매 상품의 상세 이미지·문구는 도매처가 허락한 범위에서 쓰고, 상표·인증이 필요한 상품(건강기능식품, 전기용품 등)은 `excludeKeywords`로 거르는 걸 권합니다

```bash
npm test          # 단위 테스트
npm run typecheck
```
