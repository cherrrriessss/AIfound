"""주희선 님 매칭 서버 호출 (저장 직후).

    POST {MATCH_API_URL}/internal/match/found/{found_id}   헤더 X-Internal-Key
    POST {MATCH_API_URL}/internal/match/lost/{lost_id}     헤더 X-Internal-Key

MATCH_API_URL 이 비어 있으면(예: MOCK 혼자 테스트) 호출하지 않고 None 을 돌려준다.
매칭이 실패해도 등록·신고 저장은 이미 끝났으므로 오류를 앱에 올리지 않는다.
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any, Optional

from app.config import settings

log = logging.getLogger("aifound.match")

TIMEOUT_SECONDS = 60   # 임베딩 + Gemini 재비교 시간


def _post(path: str) -> Optional[Any]:
    if not settings.match_api_url:
        log.info("MATCH_API_URL 없음 → 매칭 호출 생략: %s", path)
        return None
    url = f"{settings.match_api_url}{path}"
    req = urllib.request.Request(url, data=b"", method="POST",
                                 headers={"X-Internal-Key": settings.internal_key, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as r:
            body = r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        log.warning("매칭 서버 오류 %s → %s %s", url, e.code, e.read()[:300])
        return None
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        log.warning("매칭 서버 연결 실패 %s: %s", url, e)
        return None
    try:
        return json.loads(body) if body else None
    except ValueError:
        return None


def match_found(found_id: str) -> Optional[Any]:
    """습득물 저장 직후 (백그라운드로 호출)."""
    return _post(f"/internal/match/found/{found_id}")


def match_lost(lost_id: str) -> Optional[Any]:
    """분실 신고 저장 직후 (응답을 17 화면에 전달하므로 기다린다)."""
    return _post(f"/internal/match/lost/{lost_id}")
