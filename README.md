# AIfound

숭실대 AI 분실물 찾기 앱 (모바일프로그래밍 프로젝트)

| 폴더 | 내용 | 담당 |
|---|---|---|
| `android/` | 안드로이드 앱 (Java + XML) | 김준희(02·03·10~15), 이민서(나머지 화면) |
| `server/` | 로그인·습득물·분실 신고 서버 (FastAPI, 포트 8001) | 김준희 |
| `match-server/` | 매칭·알림·수령 서버 (FastAPI, 포트 8000) | 주희선 |

자세한 실행 방법은 각 폴더의 README.md 를 보세요.

## 처음 한 번
1. Supabase SQL Editor 에서 `server/supabase/schema.sql` 실행 (팀 통합 스키마, 두 서버가 같이 씀)
2. `server/.env`, `match-server/.env` 채우기 — Supabase·Gemini 키와 `INTERNAL_KEY` 는 **두 서버가 같은 값**
3. `match-server/firebase-service-account.json` 넣기 (푸시), 앱에는 `android/app/google-services.json`

## 같이 켜기 (터미널 2개)
```bash
cd server       && uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
cd match-server && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
`server/.env` 에 `MATCH_API_URL=http://localhost:8000`, `MOCK=false` 일 때 등록·신고 → 매칭 → 알림이 끝까지 이어진다.
앱에서 8000번을 부르는 방법은 `match-server/ANDROID.md`.

## 주의
- `.env`, `firebase-service-account.json`, `google-services.json` 은 **절대 올리지 않기** (카톡으로만 주고받기)
- 작업은 각자 브랜치에서 하고, main 에 합칠 때 Pull Request
