"""화면에 보여 줄 '진행 상태' 계산 (S23, S24, S22).

matches.status (주희선 매칭 서버가 바꿈):
    candidate → claimed(내 물건이에요) → received(수령 완료)
    rejected(내 물건 아님), closed(다른 사람이 수령)
"""
from __future__ import annotations

from typing import Iterable

from app.repo import Repo, Row
from app.schemas import SummaryOut

LOST_STAGE_LABEL = {
    "waiting": "매칭 대기",
    "candidates": "후보 있음",
    "claimed": "수령 대기",
    "received": "수령 완료",
    "closed": "신고 종료",
}

FOUND_STATUS_LABEL = {
    "stored": "보관 중",
    "owner_confirmed": "주인 확인됨",
    "returned": "수령 완료",
}

ACTIVE = ("candidate", "claimed")   # 후보로 셀 상태


def lost_stage(lost: Row, matches: Iterable[Row]) -> tuple[str, int]:
    """(단계, 후보 수). S23: 매칭 대기 → 후보 있음 → 수령 대기 → 수령 완료."""
    ms = [m for m in matches if str(m["lost_report_id"]) == str(lost["id"])]
    statuses = {m.get("status") for m in ms}
    count = sum(1 for m in ms if m.get("status") in ACTIVE)
    if "received" in statuses:
        return "received", count
    if lost.get("status") == "closed":
        return "closed", count
    if "claimed" in statuses:
        return "claimed", count
    if count > 0:
        return "candidates", count
    return "waiting", 0


def found_display(found: Row, matches: Iterable[Row]) -> str:
    """S24 배지: 보관 중 / 주인 확인됨 / 수령 완료."""
    if found.get("status") == "returned":
        return "returned"
    ms = [m for m in matches if str(m["found_item_id"]) == str(found["id"])]
    if any(m.get("status") in ("claimed", "received") for m in ms):
        return "owner_confirmed"
    return "stored"


def build_summary(repo: Repo, user_id: str) -> SummaryOut:
    """S22 마이페이지 숫자 3개 + S24 '지금까지 n명에게 돌려줬어요'."""
    lost = repo.list_lost(user_id)
    lost_matches = repo.matches_for_lost([str(r["id"]) for r in lost])
    stages = [lost_stage(r, lost_matches)[0] for r in lost]
    found, _ = repo.list_found(category=None, building=None, status=None,
                               finder_id=user_id, offset=0, limit=1000)
    found_matches = repo.matches_for_found([str(r["id"]) for r in found])
    returned = sum(1 for r in found if found_display(r, found_matches) == "returned")
    gave, got = repo.count_pickups(user_id)
    return SummaryOut(
        lost_count=len(lost),
        lost_open_count=sum(1 for s in stages if s not in ("closed", "received")),
        found_count=len(found),
        returned_count=max(returned, gave),
        received_count=max(got, sum(1 for s in stages if s == "received")),
    )
