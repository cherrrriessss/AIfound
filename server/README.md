# AIfound 백엔드 — 김준희 파트

학교 메일 로그인 · 프로필 · 습득물 등록(Gemini 속성 추출) · 분실 신고 저장/수정/종료.
저장 직후 **주희선 님 매칭 서버**(`/internal/match/...`)를 호출한다.

## 팀 서버 구성

| 서버 | 담당 | 포트 | 하는 일 |
|---|---|---|---|
| 이 서버 | 김준희 | **8001** | 로그인, 프로필, 습득물 등록, 분실 신고 |
| 매칭 서버 | 주희선 | 8000 | 임베딩·매칭·푸시, 개인정보 가림(/privacy), 보관함 근처(/lockers/nearby), 수령, 알림 |

두 서버는 **같은 Supabase 테이블**(`supabase/schema.sql`)을 쓴다. 한 컴퓨터에서 둘 다 켤 수 있게 이 서버는 8001.

## 1. DB 만들기 (처음 한 번)

1. 주희선 님이 보낸 Supabase 초대 메일 수락
2. Supabase 대시보드 → **SQL Editor** → `supabase/schema.sql` 전체 붙여넣기 → **Run**
   - 주희선 님 테이블·매칭 함수는 컬럼 이름 그대로, 여기에 profiles·가입 트리거·RLS·사진 버킷을 더한 통합본
   - 여러 번 실행해도 안전
3. **Authentication → Sign In / Providers → Email** 켜기
4. **Authentication → Emails**의 **Magic Link**, **Confirm signup** 템플릿 본문에 `{{ .Token }}` 넣기
   (예: `AIfound 인증코드: {{ .Token }} (5분 안에 입력)`) → 메일에 6자리 코드가 간다

## 2. 실행

```powershell
cd aifound-backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env      # 메모장으로 열어 값 채우기 (아래 표)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

http://localhost:8001/docs 에서 API 를 눌러 볼 수 있다. `/health` 에 `"mock": false` 가 보이면 실제 모드.

| .env 키 | 값 |
|---|---|
| `MOCK` | 혼자 테스트 `true`, 실제 DB `false` |
| `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` | 주희선 님이 카톡으로 준 값 |
| `GEMINI_API_KEY`, `GEMINI_MODEL` | 주희선 님과 같은 값 |
| `MATCH_API_URL` | 주희선 서버 주소 (같은 컴퓨터면 `http://localhost:8000`) |
| `INTERNAL_KEY` | 주희선 서버 `.env` 의 INTERNAL_KEY |
| `SCHOOL_EMAIL_DOMAIN` | `soongsil.ac.kr` (팀 확인 필요) |

> 키는 `.env` 에만. 깃허브·앱 코드에 넣지 않는다.

## 3. 테스트

```powershell
pytest -q
```

## 4. API (앱 → 이 서버)

| 메서드 | 경로 | 화면 | 설명 |
|---|---|---|---|
| POST | `/auth/request-code` | 02 | 학교 메일로 6자리 코드 |
| POST | `/auth/verify` | 02 | 코드 확인 → Supabase 토큰, `is_new_user` |
| POST | `/auth/refresh` | – | 토큰 갱신 |
| GET/PATCH | `/me` | 03 | 이름, 학과 |
| GET | `/me/summary` | 22, 24 | 분실 신고·습득물 등록·수령 완료 건수, 돌려준 수 |
| DELETE | `/me` | 28 | 회원 탈퇴 (내 신고·수령 기록 삭제, 등록한 습득물은 남기고 등록자만 지움) |
| GET | `/buildings` | 13 | 건물 이름 목록 |
| GET | `/lockers?building=` | 14 | 보관함 (같은 건물 먼저) |
| POST | `/found/analyze` | 10→11·12 | 사진 → AI 속성 + 개인정보 영역 (저장 안 함) |
| POST | `/found` | 14 | 등록 → 저장 직후 `/internal/match/found/{id}` (백그라운드) |
| GET | `/found` | 07 | 찾아보기: `q`(이름·브랜드 검색), `category`, `color`, `building`, `date_from`, `date_to`, `page` |
| GET | `/found/{id}` | 08, 15 | 상세. 15 화면은 `match_status` 를 몇 초마다 다시 읽어 진행 표시 |
| GET | `/me/found` | 24 | 내가 등록한 습득물. `display_label` = 보관 중 / 주인 확인됨 / 수령 완료 |
| POST | `/lost` | 16→17 | 신고 → 저장 직후 `/internal/match/lost/{id}`, 그 응답을 `match` 로 돌려줌 |
| POST | `/lost/{id}/photo` | 16 | 참고 사진 (선택) |
| GET | `/me/lost?tab=open\|done` | 23 | 내 신고. `stage_label` = 매칭 대기 / 후보 있음 / 수령 대기 / 수령 완료 / 신고 종료, `match_count` = 후보 수 |
| GET | `/lost/{id}` | 23 | 내 신고 상세 |
| PATCH | `/lost/{id}` | 23 | 수정 → 다시 매칭 |
| POST | `/lost/{id}/close` | 23 | '찾았어요' (status=closed) |

### 저장 형식 (주희선 매칭과 같음)

- 물건 종류: `이어폰, 지갑, 학생증·카드, 휴대폰, 기타` (Gemini 도 이 목록에서만)
- `attrs`: `{category, subcategory, brand, model, color, features[], title}` — 색은 하나(`color`)
- 습득물: `building`(텍스트), `location_detail`, `found_at`, `locker_id`(uuid), `photo_path`
- 분실 신고: `buildings`(여러 개), `lost_from` ~ `lost_to`
- 사진 버킷 `found-photos`: `found/...` 는 로그인한 학생이 읽기 가능, `lost/...` 는 서버 서명 URL 로만

### `/found` 요청 예 (multipart)

- `image`: 사진 파일 (`mask_boxes` 가 있으면 서버가 가린 뒤 저장. 이미 `/privacy/blur` 로 가린 사진이면 비워 둔다)
- `data`: JSON 문자열
```json
{"attributes": {"...": "analyze 응답을 S12 에서 고친 값"},
 "building": "형남공학관", "location_detail": "3층 302호 앞",
 "found_at": "2026-11-11T14:00:00+09:00", "description": "고양이 스티커",
 "locker_id": "<lockers.id>", "mask_boxes": []}
```

## 5. AI 정확도 측정 (발표용)

`eval/README.md` 참고. 사진 + 정답 CSV 를 넣고 `python -m tools.eval_attributes` →
종류·색·브랜드 정확도, 개인정보 경고 정확도 표(`eval/summary.md`)가 나온다.

## 6. 폴더 구조

```
app/
  main.py · config.py(.env) · schemas.py(약속) · repo.py(MemoryRepo ↔ SupabaseRepo) · deps.py(로그인 확인)
  routers/  auth.py · found.py · lost.py
  services/ auth.py(OTP) · gemini.py(프롬프트·결과 정리) · images.py(EXIF 제거·가림)
            found.py(분석·등록) · match_client.py(매칭 서버 호출) · attributes.py(경고 문구)
            status.py(23 신고 단계, 24 습득물 배지, 22 건수)
tools/eval_attributes.py  정확도 측정 도구
supabase/schema.sql   팀 통합 스키마
tests/
```
