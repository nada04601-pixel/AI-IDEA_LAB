# 마음장부 Play 스토어 출시 준비

출시용 빌드는 `.github/workflows/maeum-jangbu-release.yml`이 만든다. 아래 1~3은 **처음 한 번만** 하면 된다.

## 1. 업로드 키 만들기 (내 PC에서, 한 번만)

Play 스토어는 **Play 앱 서명**을 쓴다. 실제 앱 서명 키는 구글이 보관하고, 우리는 앱을 올릴 때 쓰는 **업로드 키**만 가진다. 업로드 키를 잃어버려도 Play Console에서 새 키로 바꿀 수 있다.

Java가 설치된 PC에서 (Windows PowerShell 기준):

```powershell
keytool -genkeypair -v -keystore maeum-jangbu-upload.jks -alias upload -keyalg RSA -keysize 2048 -validity 10000
```

- 비밀번호 2개(키 저장소, 키)를 정한다. 같은 값이어도 된다.
- 이름·조직 질문은 아무 값이나 괜찮다 (앱에 표시되지 않음).
- 만든 `maeum-jangbu-upload.jks`와 비밀번호는 **저장소에 올리지 말고** 따로 안전하게 보관한다.

## 2. GitHub Secrets에 등록 (한 번만)

키 파일을 글자로 바꿔 클립보드에 복사:

```powershell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("maeum-jangbu-upload.jks")) | Set-Clipboard
```

GitHub 저장소 → **Settings → Secrets and variables → Actions → New repository secret** 에서 4개 등록:

| 이름 | 값 |
|---|---|
| `MAEUM_JANGBU_UPLOAD_KEYSTORE_BASE64` | 위에서 복사한 글자 |
| `MAEUM_JANGBU_UPLOAD_KEYSTORE_PASSWORD` | 키 저장소 비밀번호 |
| `MAEUM_JANGBU_UPLOAD_KEY_ALIAS` | `upload` |
| `MAEUM_JANGBU_UPLOAD_KEY_PASSWORD` | 키 비밀번호 |

## 3. 출시용 AAB 만들기

둘 중 하나:

- **태그로**: `git tag maeum-jangbu-v1.0.0 && git push origin maeum-jangbu-v1.0.0` → 버전 이름 1.0.0
- **버튼으로**: GitHub → Actions → "마음장부 출시 빌드" → Run workflow (이 파일이 main 브랜치에 있어야 버튼이 보인다)

끝나면 실행 화면 아래 **Artifacts**에서 `maeum-jangbu-1.0.0.aab`를 내려받는다 (30일 보관, 공개 Releases에는 올리지 않음).

- 버전 코드는 자동으로 `1000 + 실행 번호`라 올릴 때마다 커진다.
- 빌드 중에 들어가면 안 되는 권한(인터넷·카메라·정확한 알람)이 있으면 실패한다 (`scripts/check-permissions.sh`).

## 4. Play Console 등록

1. [Play Console](https://play.google.com/console) 개발자 계정 (등록비 $25, 한 번)
2. 앱 만들기 → 앱 이름 `마음장부`, 무료
3. **Play 앱 서명** 사용 (기본값) → 3에서 받은 AAB 업로드 (내부 테스트 트랙부터 권장)
4. 스토어 등록정보
   - 제목: `마음장부 - 축의금·부의금 경조사 장부` (idea.md 1장)
   - 스크린샷: 휴대폰 화면 2장 이상
5. **개인정보처리방침 URL**: `PRIVACY.md`를 공개 주소에 올리고 그 주소를 입력
   - 예: 노바랩 사이트(novalabs.co.kr)에 같은 내용으로 페이지 추가, 또는 main에 합친 뒤 `https://github.com/nada04601-pixel/AI-IDEA_LAB/blob/main/projects/004-maeum-jangbu/PRIVACY.md`
   - 출시 전 `PRIVACY.md` 10장의 **문의 이메일**을 채운다 (앱 안 [설정 → 개인정보처리방침]에도 같은 파일이 보인다)
6. **데이터 보안(Data safety)** 설문 답변
   - 데이터 수집: **수집 안 함** — 앱은 인터넷 권한이 없고 모든 처리가 기기 안에서만 이루어진다 (기기 안에서만 처리되는 데이터는 "수집"에 해당하지 않음)
   - 데이터 공유: **공유 안 함**
   - 전송 중 암호화: 해당 없음 (전송하지 않음)
   - 데이터 삭제 요청: 앱 삭제 또는 [설정 → 모든 기록 삭제]
7. **연락처 권한**: 앱은 연락처를 읽기 전에 안내 화면에서 동의를 받는다 (연락처에서 불러오기 → "동의하고 불러오기"). 심사에서 물으면 "사람 추가 시 이름·회사명 자동 입력, 기기 밖으로 보내지 않음"으로 답한다.
8. 콘텐츠 등급 설문, 타깃층(만 18세 이상 권장), 광고 없음 체크 → 검토 제출

## 앱 설정에서 확인된 것

| 항목 | 설정 |
|---|---|
| 인터넷 권한 | 없음 (라이브러리가 넣는 것도 제거, 빌드에서 검사) |
| 카메라 권한 | 없음 (기본 카메라 앱으로 촬영) |
| 정확한 알람 권한 | 없음 (알림은 몇 분 오차 허용) |
| 연락처 | 읽기만, 여러 명 불러오기에서만 요청, 사전 동의 화면 |
| 구글 클라우드 자동 백업 | 제외 (`res/xml/data_extraction_rules.xml`). 휴대폰 간 직접 옮기기는 허용 |
