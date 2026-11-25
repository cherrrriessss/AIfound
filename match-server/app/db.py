"""Supabase(PostgreSQL + pgvector) 접근 함수 모음.
테이블과 함수 정의는 sql/schema.sql 참고."""
from typing import Optional
from datetime import datetime

from supabase import create_client

from . import config

_sb = None


def sb():
    global _sb
    if _sb is None:
        _sb = create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_KEY)
    return _sb


def _parse_times(row: dict) -> dict:
    for k in ("found_at", "lost_from", "lost_to", "created_at"):
        v = row.get(k) if row else None
        if isinstance(v, str):
            row[k] = datetime.fromisoformat(v.replace("Z", "+00:00"))
    return row


# ---------- 조회 ----------
def get_found(found_id: str) -> dict:
    return _parse_times(sb().table("found_items").select("*").eq("id", found_id).single().execute().data)


def get_lost(lost_id: str) -> dict:
    return _parse_times(sb().table("lost_reports").select("*").eq("id", lost_id).single().execute().data)


# ---------- 임베딩 / 상태 ----------
def set_embedding(table: str, row_id: str, pgvector_text: str) -> None:
    sb().table(table).update({"embedding": pgvector_text}).eq("id", row_id).execute()


def set_match_status(found_id: str, status: str) -> None:
    """15 등록 완료 화면의 진행 표시: pending -> searching -> notified / no_match"""
    sb().table("found_items").update({"match_status": status}).eq("id", found_id).execute()


def get_match_status(found_id: str) -> dict:
    return sb().table("found_items").select("id, match_status, finder_id").eq("id", found_id).single().execute().data


# ---------- 벡터 검색 (후보 거르기 + 의미 유사도) ----------
def search_lost_for_found(found_id: str) -> list[dict]:
    rows = sb().rpc("match_lost_for_found", {
        "p_found_id": found_id, "p_days": config.CANDIDATE_DAYS, "p_limit": config.CANDIDATE_LIMIT,
    }).execute().data or []
    return [_parse_times(r) for r in rows]


def search_found_for_lost(lost_id: str) -> list[dict]:
    rows = sb().rpc("match_found_for_lost", {
        "p_lost_id": lost_id, "p_days": config.CANDIDATE_DAYS, "p_limit": config.CANDIDATE_LIMIT,
    }).execute().data or []
    return [_parse_times(r) for r in rows]


# ---------- 매칭 결과 ----------
def save_match(found_id: str, lost_id: str, score: int, detail: dict,
               reason: str, short_reason: str, ai_likelihood: Optional[int]) -> dict:
    """같은 (습득물, 신고) 쌍은 한 번만 저장(있으면 점수만 갱신). 이미 거절된 쌍은 건드리지 않음."""
    existing = (sb().table("matches").select("id, status, notified")
                .eq("found_item_id", found_id).eq("lost_report_id", lost_id).execute().data)
    if existing and existing[0]["status"] == "rejected":
        return existing[0]
    row = {"found_item_id": found_id, "lost_report_id": lost_id, "score": score, "detail": detail,
           "reason": reason, "short_reason": short_reason, "ai_likelihood": ai_likelihood}
    return sb().table("matches").upsert(row, on_conflict="found_item_id,lost_report_id").execute().data[0]


def mark_notified(match_id: str) -> None:
    sb().table("matches").update({"notified": True}).eq("id", match_id).execute()


MATCH_FIELDS = ("id, score, detail, reason, short_reason, status, seen, created_at, lost_report_id,"
                " claimed_at, pickup_deadline,"
                " found_items(id, finder_id, attrs, building, location_detail, found_at, photo_path, locker_id,"
                " lockers(id, name, building, location, hours)),"
                " lost_reports!inner(id, owner_id, attrs, buildings, lost_from, lost_to, photo_path)")


def get_match_for_owner(match_id: str, user_id: str) -> Optional[dict]:
    rows = (sb().table("matches").select(MATCH_FIELDS)
            .eq("id", match_id).eq("lost_reports.owner_id", user_id).execute().data)
    return rows[0] if rows else None


def list_matches_for_lost(lost_id: str, user_id: str) -> list[dict]:
    """18 매칭 탭: 기준 점수 이상, 거절 안 한 후보, 일치율 높은 순."""
    return (sb().table("matches").select(MATCH_FIELDS)
            .eq("lost_report_id", lost_id).eq("lost_reports.owner_id", user_id)
            .neq("status", "rejected").gte("score", config.NOTIFY_THRESHOLD)
            .order("score", desc=True).execute().data or [])


def list_unseen_for_owner(user_id: str) -> list[dict]:
    """06 홈 '새 매칭 후보 N건' 배너."""
    return (sb().table("matches").select(MATCH_FIELDS)
            .eq("lost_reports.owner_id", user_id).eq("seen", False).neq("status", "rejected")
            .gte("score", config.NOTIFY_THRESHOLD).order("score", desc=True).execute().data or [])


def update_match(match_id: str, fields: dict) -> None:
    sb().table("matches").update(fields).eq("id", match_id).execute()


# ---------- 수령 (20, 25) ----------
PICKUP_FIELDS = ("id, status, claimed_at, pickup_deadline,"
                 " found_items(id, finder_id, attrs, locker_id, photo_path, lockers(id, name, building, location, hours)),"
                 " lost_reports(id, owner_id)")


def get_staff_lockers(user_id: str) -> list[str]:
    rows = sb().table("locker_staff").select("locker_id").eq("user_id", user_id).execute().data or []
    return [r["locker_id"] for r in rows]


def list_claimed_for_lockers(locker_ids: list[str]) -> list[dict]:
    return (sb().table("matches").select(PICKUP_FIELDS.replace("found_items(", "found_items!inner("))
            .eq("status", "claimed").in_("found_items.locker_id", locker_ids).execute().data or [])


def list_due_reminders(before) -> list[dict]:
    return (sb().table("matches").select(PICKUP_FIELDS)
            .eq("status", "claimed").eq("reminded", False)
            .lte("pickup_deadline", before.isoformat()).execute().data or [])


def create_pickup(row: dict) -> dict:
    return sb().table("pickups").insert(row).execute().data[0]


def set_found_status(found_id: str, status: str) -> None:
    sb().table("found_items").update({"status": status}).eq("id", found_id).execute()


def set_lost_status(lost_id: str, status: str) -> None:
    sb().table("lost_reports").update({"status": status}).eq("id", lost_id).execute()


def close_other_matches(found_id: str, keep_match_id: str) -> None:
    (sb().table("matches").update({"status": "closed"})
     .eq("found_item_id", found_id).neq("id", keep_match_id).execute())


def list_pickups(user_id: str, kind: str = "all") -> list[dict]:
    """25 수령 기록: all / mine(내가 찾은 것) / given(내가 돌려준 것)"""
    q = sb().table("pickups").select(
        "id, received_at, code, receiver_id, finder_id,"
        " found_items(id, attrs, photo_path), lockers(name)")
    if kind == "mine":
        q = q.eq("receiver_id", user_id)
    elif kind == "given":
        q = q.eq("finder_id", user_id)
    else:
        q = q.or_(f"receiver_id.eq.{user_id},finder_id.eq.{user_id}")
    return q.order("received_at", desc=True).execute().data or []




# ---------- 알림함 / 설정 / 푸시 토큰 ----------
def add_notification(user_id: str, kind: str, title: str, body: str, data: dict) -> None:
    sb().table("notifications").insert(
        {"user_id": user_id, "type": kind, "title": title, "body": body, "data": data}).execute()


def list_notifications(user_id: str) -> list[dict]:
    return (sb().table("notifications").select("*").eq("user_id", user_id)
            .order("created_at", desc=True).limit(50).execute().data or [])


def mark_all_read(user_id: str) -> None:
    sb().table("notifications").update({"read": True}).eq("user_id", user_id).execute()


def get_settings(user_id: str) -> dict:
    rows = sb().table("user_settings").select("*").eq("user_id", user_id).execute().data
    return rows[0] if rows else {"user_id": user_id, "match_alert": True}


def save_settings(user_id: str, fields: dict) -> dict:
    return sb().table("user_settings").upsert({"user_id": user_id, **fields}).execute().data[0]


def get_tokens(user_id: str) -> list[str]:
    rows = sb().table("user_devices").select("fcm_token").eq("user_id", user_id).execute().data or []
    return [r["fcm_token"] for r in rows]


def save_token(user_id: str, token: str) -> None:
    sb().table("user_devices").upsert({"user_id": user_id, "fcm_token": token},
                                      on_conflict="fcm_token").execute()


def delete_token(token: str) -> None:
    sb().table("user_devices").delete().eq("fcm_token", token).execute()


# ---------- 로그인 사용자 확인 ----------
def user_id_from_jwt(jwt: str) -> Optional[str]:
    """앱이 보낸 Supabase 로그인 토큰이 진짜인지 확인하고 사용자 id를 돌려줌."""
    try:
        return sb().auth.get_user(jwt).user.id
    except Exception:
        return None
