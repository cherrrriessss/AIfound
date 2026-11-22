# AIfound

숭실대 AI 분실물 찾기 앱 (모바일프로그래밍 프로젝트)

| 폴더 | 내용 | 담당 |
|---|---|---|
| `android/` | 안드로이드 앱 (Java + XML) | 김준희(02·03·10~15), 이민서(나머지 화면) |
| `server/` | 로그인·습득물·분실 신고 서버 (FastAPI, 포트 8001) | 김준희 |
| `match-server/` | 매칭·알림·수령 서버 (포트 8000) — 추가 예정 | 주희선 |

자세한 실행 방법은 각 폴더의 README.md 를 보세요.

## 주의
- `.env`, `firebase-service-account.json`, `google-services.json` 은 **절대 올리지 않기** (카톡으로만 주고받기)
- 작업은 각자 브랜치에서 하고, main 에 합칠 때 Pull Request
