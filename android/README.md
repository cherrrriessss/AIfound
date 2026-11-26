# AIfound 안드로이드 앱 — 김준희 파트 화면

Java + XML, Android Studio 프로젝트. 아래 화면이 김준희 서버(`aifound-backend`, 포트 8001)와 연결돼 있다. 매칭·알림·수령은 주희선 서버(8000) 담당.

| 화면 | 클래스 | 서버 API |
|---|---|---|
| S02 학교 메일 로그인 | `LoginActivity` | `/auth/request-code`, `/auth/verify` |
| S03 프로필 설정 | `ProfileActivity` | `PATCH /me` (이름·학과) |
| (임시) 홈 · 내가 등록한 습득물 | `HomeActivity` | `/me`, `/me/found` |
| S10 사진 촬영·선택 | `PhotoActivity` | `/found/analyze` |
| S11 개인정보 가리기 | `MaskingActivity` + `MaskEditorView` | (S10 결과 사용) |
| S12 AI 인식 결과 | `AiTagsActivity` | – |
| S13 습득 장소·시간 | `FoundInfoActivity` | `/buildings` (건물 이름) |
| S14 보관함 선택 → 등록 | `StorageActivity` | `/lockers?building=`, `POST /found` |
| S15 등록 완료 | `FoundDoneActivity` | – |

## 이민서 파트

| 화면 | 클래스 | 서버 API |
|---|---|---|
| S04 온보딩 (첫 가입 후 1번) | `OnboardingActivity` | – |
| S06 홈 | `HomeActivity` | `/me`, `GET /found?size=5`, 8000 `/matches/summary`(배너), `/notifications`(알림 점) |
| S07 찾아보기 | `FoundListActivity` | `GET /found` (q, category, color, building, date_from, page) |
| S08 습득물 상세 | `FoundDetailActivity` | `GET /found/{id}`, 8000 `POST /found-items/{id}/claim` ('내 물건이에요') |
| S09 보관함 위치 | `StorageMapActivity` | – (지도는 휴대폰 지도 앱으로) |
| S16 분실 신고 / 수정 | `LostReportActivity` | `POST /lost`, `POST /lost/{id}/photo`, `PATCH /lost/{id}`, `/buildings` |
| S17 신고 완료 | `LostDoneActivity` | (`POST /lost` 응답의 `match`) |
| S18 분실물 매칭 탭 | `MatchListActivity` | `GET /me/lost?tab=open`, 8000 `/lost-reports/{id}/matches` |
| S19 매칭 상세 | `MatchDetailActivity` | 8000 `/matches/{id}`, `/matches/{id}/claim` |
| S20 수령 안내 · 코드 · QR | `ClaimActivity` | 8000 `/matches/{id}/pickup`, `/pickup/code`, `/pickup/status` |
| S21 내 물건 아님 (시트) | `MatchDetailActivity` 안 | 8000 `/matches/{id}/reject` |
| S22 마이페이지 | `MyPageActivity` | `/me`, `/me/summary`, 8000 `/notifications` |
| S23 내 분실 신고 | `MyLostActivity` | `GET /me/lost`, `POST /lost/{id}/close` |
| S24 내가 등록한 습득물 | `MyFoundActivity` | `/me/found`, `/me/summary` |
| S25 수령 기록 | `HistoryActivity` | 8000 `/pickups?kind=` |
| S26 알림 설정 | `NotiSettingActivity` | 8000 `GET/PUT /settings/notifications` |
| S27 알림함 | `InboxActivity` | 8000 `/notifications`, `/notifications/read-all` |
| S05 푸시 알림 | `util/PushService`, `util/Push` | 8000 `POST /devices` |
| S28 설정 (프로필 수정·로그아웃·탈퇴·약관) | `SettingsActivity` (+ `ProfileActivity` 수정 모드) | `PATCH /me`, `DELETE /me` |

- 매칭 서버(8000)는 `ApiClient.match(this)` 로 부른다. 주소는 김준희 서버 주소에서 포트만 8000 (`TokenStore.matchUrl`).
- **S08 '내 물건이에요'는 매칭 없이 바로 수령 요청**한다 (팀 결정). 내 신고와 이미 매칭돼 있으면 그 매칭을, 없으면
  매칭 서버가 '직접 수령 요청' 매칭(점수 0)을 만들어 같은 수령 흐름(S20 → 행정실 확인 → S25)을 탄다.
  본인 확인은 행정실에서 학교 메일 + 수령 코드로.
- 예전 임시 마이페이지(`TempMyPageActivity`)는 지웠다. 로그아웃·탈퇴는 S28 설정에 있다.
- **S05 푸시(FCM)**: `util/PushService`(받기·알림 띄우기), `util/Push`(토큰 등록·누르면 갈 화면).
  - 켜는 법: Firebase 콘솔의 **`google-services.json`** 을 `android/app/` 에 넣고 다시 빌드 (깃에는 안 올림).
    파일이 없으면 푸시만 꺼진 채로 그대로 빌드·실행된다.
  - 서버 쪽: Firebase 서비스 계정 키를 `match-server/firebase-service-account.json` 에 두기 (`.env` 의 `FIREBASE_CREDENTIALS`).
    없으면 서버는 푸시만 건너뛰고 S27 알림함에는 그대로 저장한다.
  - 홈(S06)에 들어올 때 토큰을 `POST /devices` 로 등록, 로그아웃·탈퇴 때 토큰 삭제.
  - 알림을 누르면 (앱이 꺼져 있어도) 홈 위에 바로 화면이 열린다: match → S19, reminder → S20,
    owner_found → S24, received → S25. S27 알림함에서 누를 때도 같은 규칙.
- S28 이용약관 문구 넣음 (`SettingsActivity.TERMS`). 시행일 등은 팀에서 바꿔도 됨.
- 공통 도우미: `util/Fmt` (시간·장소·물건 이름·사진 주소), `util/Ui` (선택 칩, 배지, 토글), 사진은 Glide, QR 은 zxing.
- 빌드: Gradle 8.7 은 **JDK 17~21** 이 필요하다. Android Studio 의 Gradle JDK 를 21 로 고르기 (25 면 빌드가 바로 실패함).

## 실행 순서

1. **서버 먼저 켜기** (`aifound-backend` 폴더, README 참고)
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
   ```
2. **Android Studio → Open → `AIfoundApp` 폴더** 선택
   - 처음 열면 Gradle Sync 가 몇 분 걸린다 (인터넷 필요).
   - "Gradle JDK" 를 물으면 Android Studio 기본 JDK(17 이상) 선택.
3. **에뮬레이터 실행 → ▶ Run 'app'**
   - 에뮬레이터는 서버 주소가 `http://10.0.2.2:8001` 으로 이미 맞춰져 있다.
4. 로그인: 아이디 입력 → 인증코드 받기 → **서버 터미널에 찍힌 6자리** 입력 (MOCK 모드)
5. 홈 → 주운 물건 등록하기 → 사진 → 가림 → AI 결과 → 장소 → 보관함 → 등록

### 실제 폰으로 실행할 때

- 폰과 컴퓨터를 같은 와이파이에 연결하고, 서버를 `--host 0.0.0.0` 으로 켠다.
- 컴퓨터 IP 확인 (Windows: `ipconfig`, Mac: 시스템 설정 > 네트워크).
  WSL 에서 서버를 켰다면 Windows 쪽 포트 연결이 필요할 수 있으니, 처음엔 Windows PowerShell 에서 서버를 켜는 것이 편하다.
- 앱 로그인 화면 맨 아래 **서버 설정** → `http://<컴퓨터 IP>:8001` 저장.

### 가림 화면(S11) 시연

MOCK 모드의 AI 는 기본적으로 '에어팟' 결과를 준다. 서버 `.env` 에 `MOCK_PII=true` 를 넣고 서버를 다시 켜면
'학생증(이름·학번·얼굴 감지)' 결과가 나와서 자동 가림 / 직접 가리기 / 미가림 경고를 시연할 수 있다.

## 구조

```
app/src/main/java/com/aifound/app/
  net/   ApiService(API 목록) · ApiClient(Retrofit, 토큰 자동 첨부) · Models(JSON) · ApiCallback(오류 처리)
  data/  TokenStore(토큰·서버 주소 저장) · FoundDraft(등록 5단계 입력값) · Catalog(종류·색 목록)
  util/  ImageUtils(회전·축소·EXIF 제거) · Steps(단계 헤더)
  ui/    화면들
```

- 사진은 폰에서 먼저 1600px 로 줄이고 EXIF(위치 정보)를 없앤 뒤 보낸다.
- 가림 좌표는 서버와 같은 `[ymin, xmin, ymax, xmax]`(0~1000).
- `Catalog` 의 종류(팀 합의 5개)·색 목록은 서버 `schemas.py` 와 같아야 한다 (분실 신고 화면에서도 이 목록).

## 이민서·주희선 파트에 넘길 것

- 이민서: `net/` 폴더를 그대로 가져가 다른 화면에서도 `ApiClient.get(this).xxx()` 로 호출하면 된다.
- FCM 토큰은 주희선 서버 `POST /devices` 로 보낸다 (이민서 파트).
