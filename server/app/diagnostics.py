"""설정 진단: /health 와 서버 시작 로그에 '무엇이 빠졌는지'를 보여 준다."""
from __future__ import annotations

import base64
import json
import logging

from app.config import settings

log = logging.getLogger("aifound.config")


def supabase_key_kind(key: str) -> str:
    """service 키인지 확인. 앱용(anon/publishable) 키를 넣으면 RLS 때문에 표가 비어 보인다."""
    if not key:
        return "없음"
    if key.startswith("sb_secret_"):
        return "secret (정상)"
    if key.startswith("sb_publishable_"):
        return "publishable (앱용 키 — 서버에는 secret 키가 필요해요)"
    try:  # 예전 형식 JWT 키: payload 의 role 확인
        payload = key.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        role = json.loads(base64.urlsafe_b64decode(payload)).get("role")
        return "service_role (정상)" if role == "service_role" else f"{role} (앱용 키 — service_role 키가 필요해요)"
    except Exception:
        return "알 수 없는 형식"


def report() -> dict:
    problems: list[str] = []
    info: dict = {
        "mock": settings.mock,
        "school_domain": settings.school_domain,
        "gemini_model": settings.gemini_model,
        "gemini_key": bool(settings.gemini_api_key),
        "match_api": settings.match_api_url or None,
    }
    if settings.mock:
        info["note"] = "MOCK 모드: Supabase·Gemini 를 쓰지 않아요 (AI 결과는 항상 같은 예시)"
        return {"ok": True, **info, "problems": problems}

    info["supabase_url"] = bool(settings.supabase_url)
    info["supabase_key"] = supabase_key_kind(settings.supabase_service_key)
    if not settings.supabase_url:
        problems.append("SUPABASE_URL 이 비어 있어요")
    if "정상" not in info["supabase_key"]:
        problems.append(f"SUPABASE_SERVICE_KEY: {info['supabase_key']}")
    if not settings.gemini_api_key:
        problems.append("GEMINI_API_KEY 가 비어 있어요 → 사진 분석이 안 돼요")
    if settings.match_api_url and not settings.internal_key:
        problems.append("MATCH_API_URL 은 있는데 INTERNAL_KEY 가 비어 있어요")

    if settings.supabase_url and settings.supabase_service_key:
        try:
            from app.repo import get_repo
            repo = get_repo()
            lockers = repo.list_lockers()
            info["lockers"] = len(lockers)
            info["buildings"] = repo.list_buildings()
            if not lockers and not settings.building_list():
                problems.append("lockers 표가 비어 있어요 → 13 건물 목록·14 보관함이 비어요 (SQL 로 보관함 추가)")
        except Exception as e:  # 표 없음, 키 틀림 등
            info["lockers"] = None
            problems.append(f"Supabase 조회 실패: {str(e)[:160]}")
    return {"ok": not problems, **info, "problems": problems}


def log_startup() -> None:
    r = report()
    log.warning("설정 확인: mock=%s, gemini_key=%s, model=%s, supabase_key=%s, lockers=%s",
                r["mock"], r["gemini_key"], r["gemini_model"], r.get("supabase_key", "-"), r.get("lockers", "-"))
    for p in r["problems"]:
        log.warning("  ⚠ %s", p)
