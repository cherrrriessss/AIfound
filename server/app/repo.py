"""DB 접근 계층 (MOCK 메모리 ↔ Supabase).

행(row)은 supabase/schema.sql 컬럼 이름 그대로의 dict 로 주고받는다.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional, Protocol

from app.config import settings

Row = dict[str, Any]


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Repo(Protocol):
    # 프로필
    def get_profile(self, user_id: str) -> Optional[Row]: ...
    def ensure_profile(self, user_id: str, email: str) -> tuple[Row, bool]: ...
    def update_profile(self, user_id: str, fields: Row) -> Row: ...
    # 보관함·건물
    def list_lockers(self) -> list[Row]: ...
    def list_buildings(self) -> list[str]: ...
    # 사진 (Storage)
    def upload_photo(self, path: str, data: bytes) -> None: ...
    def photo_url(self, path: Optional[str]) -> Optional[str]: ...
    # 습득물
    def insert_found(self, row: Row) -> Row: ...
    def get_found(self, found_id: str) -> Optional[Row]: ...
    def list_found(self, *, category: Optional[str], building: Optional[str], status: Optional[str],
                   finder_id: Optional[str], offset: int, limit: int,
                   color: Optional[str] = None, date_from: Optional[datetime] = None,
                   date_to: Optional[datetime] = None, q: Optional[str] = None) -> tuple[list[Row], int]: ...
    # 분실 신고
    def insert_lost(self, row: Row) -> Row: ...
    def get_lost(self, lost_id: str) -> Optional[Row]: ...
    def update_lost(self, lost_id: str, fields: Row) -> Row: ...
    def list_lost(self, owner_id: str) -> list[Row]: ...
    # 매칭·수령 (주희선 파트가 채움 → 여기서는 읽기만)
    def matches_for_lost(self, lost_ids: list[str]) -> list[Row]: ...
    def matches_for_found(self, found_ids: list[str]) -> list[Row]: ...
    def count_pickups(self, user_id: str) -> tuple[int, int]: ...   # (내가 돌려준 수, 내가 찾은 수)
    # 회원 탈퇴
    def delete_account(self, user_id: str) -> None: ...


def _buildings_from(lockers: list[Row]) -> list[str]:
    configured = settings.building_list()
    if configured:
        return configured
    seen: list[str] = []
    for lk in lockers:
        if lk.get("building") and lk["building"] not in seen:
            seen.append(lk["building"])
    return seen


def clean_query(q: Optional[str]) -> Optional[str]:
    """검색어에서 PostgREST 필터 문법을 깨는 문자(쉼표·괄호·%·*)를 뺀다."""
    if not q:
        return None
    cleaned = "".join(ch for ch in q if ch not in ",()%*\\").strip()
    return cleaned[:40] or None


def _as_dt(v: Any) -> datetime:
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# MOCK: 메모리 저장 (서버 재시작 시 초기화)
# ---------------------------------------------------------------------------
class MemoryRepo:
    def __init__(self) -> None:
        self.profiles: dict[str, Row] = {}
        self.lockers: list[Row] = [
            {"id": "00000000-0000-0000-0000-000000000001", "name": "형남공학관 1층 행정실", "code": None,
             "building": "형남공학관", "location": None, "hours": "평일 09:00-18:00"},
            {"id": "00000000-0000-0000-0000-000000000002", "name": "중앙도서관 1층 안내데스크", "code": "B-03",
             "building": "중앙도서관", "location": "정문 출입 후 오른쪽 안내데스크", "hours": "매일 09:00-22:00"},
            {"id": "00000000-0000-0000-0000-000000000003", "name": "학생회관 분실물 센터", "code": None,
             "building": "학생회관", "location": None, "hours": "평일 10:00-17:00"},
        ]
        self.photos: dict[str, bytes] = {}
        self.found: dict[str, Row] = {}
        self.lost: dict[str, Row] = {}
        self.matches: list[Row] = []    # 테스트에서 직접 넣는다 (실제로는 주희선 서버가 채움)
        self.pickups: list[Row] = []
        self.deleted_users: list[str] = []

    def get_profile(self, user_id: str) -> Optional[Row]:
        return self.profiles.get(user_id)

    def ensure_profile(self, user_id: str, email: str) -> tuple[Row, bool]:
        if user_id in self.profiles:
            return self.profiles[user_id], False
        row = {"id": user_id, "email": email, "name": None, "department": None,
               "created_at": _now(), "updated_at": _now()}
        self.profiles[user_id] = row
        return row, True

    def update_profile(self, user_id: str, fields: Row) -> Row:
        row = self.profiles[user_id]
        row.update(fields, updated_at=_now())
        return row

    def list_lockers(self) -> list[Row]:
        return list(self.lockers)

    def list_buildings(self) -> list[str]:
        return _buildings_from(self.lockers)

    def upload_photo(self, path: str, data: bytes) -> None:
        self.photos[path] = data

    def photo_url(self, path: Optional[str]) -> Optional[str]:
        return f"/mock-photos/{path}" if path else None

    def insert_found(self, row: Row) -> Row:
        row = {"status": "stored", "match_status": "pending", **row,
               "id": str(uuid.uuid4()), "created_at": _now()}
        self.found[row["id"]] = row
        return row

    def get_found(self, found_id: str) -> Optional[Row]:
        return self.found.get(found_id)

    def list_found(self, *, category, building, status, finder_id, offset, limit,
                   color=None, date_from=None, date_to=None, q=None):
        rows = sorted(self.found.values(), key=lambda r: _as_dt(r["found_at"]), reverse=True)
        if color:
            rows = [r for r in rows if (r.get("attrs") or {}).get("color") == color]
        if date_from:
            rows = [r for r in rows if _as_dt(r["found_at"]) >= _as_dt(date_from)]
        if date_to:
            rows = [r for r in rows if _as_dt(r["found_at"]) <= _as_dt(date_to)]
        q = clean_query(q)
        if q:
            def hit(r: Row) -> bool:
                a = r.get("attrs") or {}
                text = " ".join(str(x or "") for x in (a.get("title"), a.get("brand"), a.get("model"),
                                                       a.get("subcategory"), r.get("description")))
                return q.lower() in text.lower()
            rows = [r for r in rows if hit(r)]
        if category:
            rows = [r for r in rows if r["category"] == category]
        if building:
            rows = [r for r in rows if r.get("building") == building]
        if status:
            rows = [r for r in rows if r["status"] == status]
        if finder_id:
            rows = [r for r in rows if r.get("finder_id") == finder_id]
        return rows[offset: offset + limit], len(rows)

    def insert_lost(self, row: Row) -> Row:
        row = {"status": "open", "photo_path": None, **row, "id": str(uuid.uuid4()), "created_at": _now()}
        self.lost[row["id"]] = row
        return row

    def get_lost(self, lost_id: str) -> Optional[Row]:
        return self.lost.get(lost_id)

    def update_lost(self, lost_id: str, fields: Row) -> Row:
        row = self.lost[lost_id]
        row.update(fields)
        return row

    def list_lost(self, owner_id: str) -> list[Row]:
        return sorted((r for r in self.lost.values() if r["owner_id"] == owner_id),
                      key=lambda r: r["created_at"], reverse=True)

    def matches_for_lost(self, lost_ids: list[str]) -> list[Row]:
        return [m for m in self.matches if m["lost_report_id"] in lost_ids]

    def matches_for_found(self, found_ids: list[str]) -> list[Row]:
        return [m for m in self.matches if m["found_item_id"] in found_ids]

    def count_pickups(self, user_id: str) -> tuple[int, int]:
        gave = sum(1 for p in self.pickups if p.get("finder_id") == user_id)
        got = sum(1 for p in self.pickups if p.get("receiver_id") == user_id)
        return gave, got

    def delete_account(self, user_id: str) -> None:
        lost_ids = [k for k, r in self.lost.items() if r["owner_id"] == user_id]
        for k in lost_ids:
            path = self.lost[k].get("photo_path")
            if path:
                self.photos.pop(path, None)
            del self.lost[k]
        self.matches = [m for m in self.matches if m["lost_report_id"] not in lost_ids]
        self.pickups = [p for p in self.pickups if p.get("receiver_id") != user_id]
        for p in self.pickups:
            if p.get("finder_id") == user_id:
                p["finder_id"] = None
        for r in self.found.values():
            if r.get("finder_id") == user_id:
                r["finder_id"] = None   # 물건은 보관함에 그대로 있으므로 습득물은 남기고 등록자만 지운다
        self.profiles.pop(user_id, None)
        self.deleted_users.append(user_id)


# ---------------------------------------------------------------------------
# Supabase (service 키 — 서버에서만)
# ---------------------------------------------------------------------------
FOUND_COLS = ("id,finder_id,category,attrs,description,building,location_detail,found_at,"
              "locker_id,photo_path,status,match_status,created_at")
LOST_COLS = "id,owner_id,category,attrs,description,buildings,lost_from,lost_to,photo_path,status,created_at"


class SupabaseRepo:
    SIGNED_URL_SECONDS = 60 * 60

    def __init__(self) -> None:
        from supabase import create_client  # 지연 import

        self.sb = create_client(settings.supabase_url, settings.supabase_service_key)
        self.bucket = settings.photo_bucket

    @staticmethod
    def _json_ready(row: Row) -> Row:
        return {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in row.items()}

    # 프로필 (가입 트리거가 먼저 만들지만, 혹시 없으면 여기서 만든다)
    def get_profile(self, user_id: str) -> Optional[Row]:
        res = self.sb.table("profiles").select("*").eq("id", user_id).limit(1).execute()
        return res.data[0] if res.data else None

    def ensure_profile(self, user_id: str, email: str) -> tuple[Row, bool]:
        existing = self.get_profile(user_id)
        if existing:
            return existing, False
        res = self.sb.table("profiles").upsert({"id": user_id, "email": email}).execute()
        return res.data[0], True

    def update_profile(self, user_id: str, fields: Row) -> Row:
        fields = {**fields, "updated_at": _now().isoformat()}
        return self.sb.table("profiles").update(fields).eq("id", user_id).execute().data[0]

    def list_lockers(self) -> list[Row]:
        return self.sb.table("lockers").select("*").order("building").order("name").execute().data

    def list_buildings(self) -> list[str]:
        return _buildings_from(self.list_lockers())

    def upload_photo(self, path: str, data: bytes) -> None:
        self.sb.storage.from_(self.bucket).upload(path, data, {"content-type": "image/jpeg"})

    def photo_url(self, path: Optional[str]) -> Optional[str]:
        if not path:
            return None
        res = self.sb.storage.from_(self.bucket).create_signed_url(path, self.SIGNED_URL_SECONDS)
        if isinstance(res, dict):
            return res.get("signedURL") or res.get("signedUrl")
        return getattr(res, "signed_url", None)

    def insert_found(self, row: Row) -> Row:
        res = self.sb.table("found_items").insert(self._json_ready(row)).execute().data[0]
        res.pop("embedding", None)
        return res

    def get_found(self, found_id: str) -> Optional[Row]:
        res = self.sb.table("found_items").select(FOUND_COLS).eq("id", found_id).limit(1).execute()
        return res.data[0] if res.data else None

    def list_found(self, *, category, building, status, finder_id, offset, limit,
                   color=None, date_from=None, date_to=None, q=None):
        query = self.sb.table("found_items").select(FOUND_COLS, count="exact")
        if category:
            query = query.eq("category", category)
        if building:
            query = query.eq("building", building)
        if status:
            query = query.eq("status", status)
        if finder_id:
            query = query.eq("finder_id", finder_id)
        if color:
            query = query.eq("attrs->>color", color)
        if date_from:
            query = query.gte("found_at", _as_dt(date_from).isoformat())
        if date_to:
            query = query.lte("found_at", _as_dt(date_to).isoformat())
        q = clean_query(q)
        if q:
            query = query.or_(",".join(f"{col}.ilike.*{q}*" for col in (
                "attrs->>title", "attrs->>brand", "attrs->>model", "attrs->>subcategory", "description")))
        res = query.order("found_at", desc=True).range(offset, offset + limit - 1).execute()
        return res.data, res.count or 0

    def insert_lost(self, row: Row) -> Row:
        res = self.sb.table("lost_reports").insert(self._json_ready(row)).execute().data[0]
        res.pop("embedding", None)
        return res

    def get_lost(self, lost_id: str) -> Optional[Row]:
        res = (self.sb.table("lost_reports")
               .select(LOST_COLS)
               .eq("id", lost_id).limit(1).execute())
        return res.data[0] if res.data else None

    def update_lost(self, lost_id: str, fields: Row) -> Row:
        self.sb.table("lost_reports").update(self._json_ready(fields)).eq("id", lost_id).execute()
        return self.get_lost(lost_id) or {}

    def list_lost(self, owner_id: str) -> list[Row]:
        return (self.sb.table("lost_reports")
                .select(LOST_COLS)
                .eq("owner_id", owner_id).order("created_at", desc=True).execute().data)

    def matches_for_lost(self, lost_ids: list[str]) -> list[Row]:
        if not lost_ids:
            return []
        return (self.sb.table("matches").select("id,lost_report_id,found_item_id,status")
                .in_("lost_report_id", lost_ids).execute().data)

    def matches_for_found(self, found_ids: list[str]) -> list[Row]:
        if not found_ids:
            return []
        return (self.sb.table("matches").select("id,lost_report_id,found_item_id,status")
                .in_("found_item_id", found_ids).execute().data)

    def count_pickups(self, user_id: str) -> tuple[int, int]:
        gave = self.sb.table("pickups").select("id", count="exact").eq("finder_id", user_id).limit(1).execute()
        got = self.sb.table("pickups").select("id", count="exact").eq("receiver_id", user_id).limit(1).execute()
        return gave.count or 0, got.count or 0

    def delete_account(self, user_id: str) -> None:
        """S28 회원 탈퇴. 외래키 때문에 순서가 중요하다.
        1) 내가 찾아간 수령 기록 삭제  2) 내 분실 신고 삭제(매칭은 cascade)
        3) 내가 등록한 습득물·돌려준 기록은 남기고 등록자만 비움  4) Auth 계정 삭제(프로필·설정·알림 cascade)
        """
        sb = self.sb
        photos = [r["photo_path"] for r in
                  sb.table("lost_reports").select("photo_path").eq("owner_id", user_id).execute().data
                  if r.get("photo_path")]
        sb.table("pickups").delete().eq("receiver_id", user_id).execute()
        sb.table("pickups").update({"finder_id": None}).eq("finder_id", user_id).execute()
        sb.table("pickups").update({"verified_by": None}).eq("verified_by", user_id).execute()
        sb.table("lost_reports").delete().eq("owner_id", user_id).execute()
        sb.table("found_items").update({"finder_id": None}).eq("finder_id", user_id).execute()
        if photos:
            try:
                sb.storage.from_(self.bucket).remove(photos)
            except Exception:  # 사진 삭제 실패는 탈퇴를 막지 않는다
                pass
        sb.auth.admin.delete_user(user_id)


_repo: Optional[Repo] = None


def get_repo() -> Repo:
    global _repo
    if _repo is None:
        _repo = MemoryRepo() if settings.mock else SupabaseRepo()
    return _repo
