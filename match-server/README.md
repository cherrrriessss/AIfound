# AIfound 매칭 서버 — 주희선 파트 (포트 8000)

속성 문장 임베딩 · 유사도 점수 · 상위 후보 AI 재비교와 이유 · 기준 이상 푸시 알림 · 알림함/알림 설정 · 매칭 결과/피드백 · 수령(코드, 행정실 확인, 기록, 리마인드).

## 팀 서버 구성

| 서버 | 폴더 | 담당 | 포트 | 하는 일 |
|---|---|---|---|---|
| 기본 서버 | `server/` | 김준희 | 8001 | 로그인, 프로필, 습득물 등록(Gemini 속성·개인정보 감지·가림), 분실 신고, 건물·보관함 목록 |
| **매칭 서버** | `match-server/` | **주희선** | **8000** | 매칭, 알림, 수령 |

- 두 서버는 **같은 Supabase**를 쓴다. 테이블은 `server/supabase/schema.sql` (팀 통합본) 하나만 실행하면 된다.
- 김준희 서버가 저장 직후 이 서버의 `/internal/match/...` 를 부른다 (`X-Internal-Key` 헤더).
- 앱은 로그인 토큰(`Authorization: Bearer ...`)을 두 서버에 똑같이 보낸다.

## 1. 처음 설치 (Mac / Windows)

VS Code 에서 **`match-server` 폴더**를 열고 터미널에서:

Mac (uv 사용)
```bash
uv venv -p 3.12
source .venv/bin/activate
uv pip install -r requirements.txt
cp .env.example .env
```

Windows (PowerShell)
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

`.env` 값 채우기 (주석 참고):
- `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `GEMINI_API_KEY`, `GEMINI_MODEL`, `INTERNAL_KEY` → **김준희 서버 `server/.env` 와 같은 값**
  (`SUPABASE_URL` 은 `.supabase.co` 로 끝나야 함. `/rest/v1` 붙이지 않기)
- `PICKUP_SECRET` → 아무 긴 문자열 (`python -c "import secrets; print(secrets.token_hex(16))"`)
- `firebase-service-account.json` → Firebase 콘솔 > 프로젝트 설정 > 서비스 계정 > 새 비공개 키, 이 폴더에 이 이름으로 저장

## 2. 실행 / 테스트

```bash
pytest -q                                                    # 키 없이 18개
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
- http://localhost:8000/health → `"supabase": true, "gemini": true` 이면 키가 들어간 것
- http://localhost:8000/docs → API 를 직접 눌러 볼 수 있음

**두 서버 같이 켜기:** 터미널 2개. `server/` 는 8001, `match-server/` 는 8000.
김준희 서버 `.env` 에 `MATCH_API_URL=http://localhost:8000`, `INTERNAL_KEY` 같은 값, **`MOCK=false`**
(MOCK 모드 로그인 토큰은 진짜 Supabase 토큰이 아니라 이 서버가 알아보지 못함).

## 3. 동작 흐름

```
[14 등록하기] 김준희 서버 POST /found → 저장 → POST /internal/match/found/{id} (바로 응답, 뒤에서 진행)
  ① attrs(JSON) → 한 문장 → Gemini 임베딩 768차원 → found_items.embedding
  ② Supabase 함수 match_lost_for_found: 같은 종류(한쪽 '기타'면 통과) · 분실 시간대 이후 · 14일 · 벡터 가까운 순 20개
     → 일치율 = 속성 40 + 의미 25 + 장소 20 + 시간 15   (19 화면 점수 막대, 합 = 일치율)
  ③ 상위 5개만 Gemini 재비교 → 같은 물건 가능성 0~100 + 이유. 30 미만이면 제외, 순서 = 일치율×0.6 + AI×0.4
  ④ 일치율 60 이상 중 상위 3명 → matches 저장 → 알림함 + FCM 푸시 (05 화면 문구)
     found_items.match_status: searching → notified / no_match   (15 화면 진행 표시)

[16 신고하기] 김준희 서버 POST /lost → 저장 → POST /internal/match/lost/{id} (기다림)
  → 보관 중인 습득물에서 같은 방식으로 찾아 결과를 돌려줌 → 김준희 서버가 17 화면에 'match' 로 전달 (푸시 없음)
  신고 수정(PATCH /lost/{id}) 때는 김준희 서버가 embedding 을 지우고 다시 부름 → 새로 계산
```
- 속성 비교: 종류 0.35 · 브랜드 0.25 · 모델 0.2 · 색 0.2. 값이 비었거나(브랜드 null = 확인 불가) `기타`면 그 항목은 빼고 계산
- Gemini 재비교가 실패해도 규칙 점수 + 기본 이유("종류·브랜드·색 일치")로 계속 진행
- 숫자(비중, 기준 60, 건물 좌표)는 모두 `app/config.py`

## 4. 앱이 부르는 API (이 서버, 8000)

모두 헤더 `Authorization: Bearer <Supabase 로그인 토큰>` 필요. 응답은 snake_case.

| 화면 | API | 설명 |
|---|---|---|
| 03 알림 허용 / 로그인 후 | `POST /devices` `{"fcm_token": "..."}` | 푸시 받을 기기 등록 |
| 05 푸시 | (서버가 보냄) | data: `type=match`, `match_id`, `lost_report_id` → 19 로 이동 |
| 06 홈 배너 | `GET /matches/summary` | `new_count`, 대표 1건 |
| 15 등록 완료 | 김준희 서버 `GET /found/{id}` 의 `match_status` | searching / notified / no_match |
| 18 매칭 탭 | `GET /lost-reports/{lost_id}/matches` | 일치율 60% 이상, 높은 순, `short_reason`, 습득물 정보 |
| 19 매칭 상세 | `GET /matches/{id}` | `score`, `reason`, `breakdown`(속성·의미·장소·시간), 내 신고, 습득물, 보관함 |
| 19 '내 물건이에요' | `POST /matches/{id}/claim` | 7일 수령 대기 + 습득자에게 '주인이 확인했어요' |
| 21 '보내고 후보에서 제외' | `POST /matches/{id}/reject` `{"reasons": [...]}` | category / color / brand_model / place_time / other |
| 20 수령 안내 | `GET /matches/{id}/pickup` | 물건, 기한, 보관함, 수령 코드 |
| 20 수령 코드 | `GET /matches/{id}/pickup/code` | 6자리 + QR 문자열, `expires_in` 초 뒤 다시 호출 |
| 20 '수령 완료 확인' | `GET /matches/{id}/pickup/status` | `received` true/false |
| 행정실 담당자 | `POST /staff/pickups/verify` `{"code": "..."}` | 코드·QR 확인 → 수령 완료, 기록, 양쪽 알림 (`locker_staff` 등록 계정만) |
| 25 수령 기록 | `GET /pickups?kind=all\|mine\|given` | |
| 26 알림 설정 | `GET` / `PUT /settings/notifications` | match_alert, owner_alert, pickup_reminder, quiet_start, quiet_end, interest_buildings |
| 27 알림함 | `GET /notifications`, `POST /notifications/read-all` | 방해 금지 중에도 알림함에는 쌓임 |

서버 내부용 (`X-Internal-Key`): `POST /internal/match/found/{id}`, `POST /internal/match/lost/{id}`, `POST /internal/cron/reminders`(하루 1번, 수령 기한 하루 전 알림).

앱(이민서 님) 연결 예시 코드는 `ANDROID.md`.

## 5. 폴더 구조

```
app/
  main.py      API (위 표)
  config.py    .env + 점수 비중·기준·건물 좌표
  pipeline.py  매칭 흐름 ①~④, 알림 보내기
  sentence.py  attrs → 임베딩용 한 문장
  embedding.py Gemini 임베딩
  scoring.py   속성·의미·장소·시간 점수
  rerank.py    상위 후보 Gemini 재비교 + 이유
  notify.py    FCM 전송          alerts.py  알림 설정·방해 금지
  pickup.py    수령 코드·확인·기록·리마인드, 주인 확인 알림
  geo.py       건물 거리           db.py      Supabase 읽기/쓰기
tests/         키 없이 도는 테스트 (가짜 DB·Gemini·FCM)
```
