"""AIfound API 서버 진입점.

실행:  uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
       (8000 은 주희선 님 매칭 서버. 한 컴퓨터에서 둘 다 켤 수 있게 8001 사용)
문서:  http://localhost:8001/docs  (Swagger — 이민서가 여기서 API 를 눌러볼 수 있음)
에뮬레이터에서 접속: http://10.0.2.2:8001
"""
import logging

from fastapi import FastAPI, Response

from app import diagnostics
from app.config import settings
from app.repo import MemoryRepo, get_repo
from app.routers import auth, found, lost

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(
    title="AIfound API",
    version="0.1.0",
    description="AIfound 백엔드 (김준희 파트) — 학교 메일 로그인 · 프로필 · 습득물 등록(Gemini 속성 추출) · 분실 신고 저장/수정/종료. 저장 직후 매칭 서버(주희선)를 호출한다.",
)

app.include_router(auth.router)
app.include_router(found.router)
app.include_router(lost.router)


@app.get("/health", tags=["system"], summary="설정 진단 — problems 에 빠진 설정이 나온다")
def health():
    return diagnostics.report()


@app.on_event("startup")
def _startup_check():
    diagnostics.log_startup()


if settings.mock:
    @app.get("/mock-photos/{path:path}", include_in_schema=False)
    def mock_photo(path: str):
        repo = get_repo()
        data = repo.photos.get(path) if isinstance(repo, MemoryRepo) else None
        if data is None:
            return Response(status_code=404)
        return Response(content=data, media_type="image/jpeg")
