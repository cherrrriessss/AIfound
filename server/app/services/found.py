"""습득물 등록 핵심 로직 (웹 프레임워크와 무관 → 단위 테스트 가능).

S10 사진 → [analyze] → S11 가림 + S12 태그 확인 → S13 장소·시간 → S14 보관함 → [register]
register 가 끝나면 라우터가 매칭 서버(주희선)를 백그라운드로 부른다.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from app.config import settings
from app.repo import Repo, Row
from app.schemas import AnalyzeOut, FoundCreateIn, FoundOut, LockerOut
from app.services import gemini, images
from app.services.attributes import pii_warning_text
from app.services.status import FOUND_STATUS_LABEL, found_display


class FoundError(ValueError):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def analyze(image_bytes: bytes) -> AnalyzeOut:
    """사진 → AI 속성 + 개인정보 영역. DB 에는 아무것도 저장하지 않는다."""
    try:
        img = images.load_image(image_bytes, settings.max_image_bytes)
    except images.ImageError as e:
        raise FoundError(str(e)) from e
    img = images.shrink(img, settings.image_max_side)
    try:
        attrs = gemini.extract_attributes(images.to_jpeg(img))
    except gemini.GeminiError as e:
        raise FoundError(str(e), status=502) from e
    if not attrs.is_item:
        raise FoundError("사진에서 물건을 찾지 못했어요. 물건 전체가 보이게 다시 찍어 주세요.", status=422)
    return AnalyzeOut(attributes=attrs, pii_warning=pii_warning_text(attrs),
                      image_width=img.width, image_height=img.height)


def register(repo: Repo, finder_id: str, image_bytes: bytes, data: FoundCreateIn) -> Row:
    """가림 적용 → 사진 업로드 → found_items 저장. 저장된 row 반환."""
    lockers = {str(lk["id"]): lk for lk in repo.list_lockers()}
    if data.locker_id not in lockers:
        raise FoundError("보관함을 다시 선택해 주세요.")

    try:
        img = images.load_image(image_bytes, settings.max_image_bytes)
    except images.ImageError as e:
        raise FoundError(str(e)) from e
    img = images.shrink(img, settings.image_max_side)

    attrs = data.attributes
    mask_boxes = [m.box for m in data.mask_boxes]
    detected = [r.box for r in attrs.pii_regions]

    # 미가림 경고: AI 가 찾은 개인정보 영역이 덮이지 않았으면 거부 (S11 '가린 뒤에 등록돼요')
    if images.unmasked_regions(detected, mask_boxes):
        raise FoundError("아직 가리지 않은 개인정보가 있어요. '자동 가림'을 누르거나 직접 가려 주세요.", status=422)

    masked = images.apply_masks(img, mask_boxes)
    # found/ 폴더 = 로그인한 학생이 볼 수 있는 사진 (schema.sql Storage 정책)
    path = f"found/{datetime.now(timezone.utc):%Y/%m}/{uuid.uuid4().hex}.jpg"
    repo.upload_photo(path, images.to_jpeg(masked))

    return repo.insert_found({
        "finder_id": finder_id,
        "category": attrs.category,
        "attrs": attrs.to_attrs(),
        "description": data.description,
        "building": data.building,
        "location_detail": data.location_detail,
        "found_at": data.found_at,
        "locker_id": data.locker_id,
        "photo_path": path,
    })


def locker_out(lk: Row, near_building: Optional[str] = None) -> LockerOut:
    return LockerOut(
        id=str(lk["id"]), name=lk["name"], code=lk.get("code"), building=lk["building"],
        location=lk.get("location"), hours=lk.get("hours"),
        same_building=near_building is not None and lk["building"] == near_building,
    )


def to_found_out(repo: Repo, row: Row, lockers: Optional[dict[str, Row]] = None,
                 matches: Optional[list[Row]] = None) -> FoundOut:
    if lockers is None:
        lockers = {str(lk["id"]): lk for lk in repo.list_lockers()}
    if matches is None:
        matches = repo.matches_for_found([str(row["id"])])
    display = found_display(row, matches)
    attrs = row.get("attrs") or {}
    lk = lockers.get(str(row.get("locker_id")))
    return FoundOut(
        id=str(row["id"]),
        photo_url=repo.photo_url(row.get("photo_path")),
        category=row["category"],
        attrs=attrs,
        title=attrs.get("title") or row["category"],
        description=row.get("description"),
        building=row.get("building"),
        location_detail=row.get("location_detail"),
        found_at=row["found_at"],
        locker=locker_out(lk) if lk else None,
        status=row.get("status", "stored"),
        match_status=row.get("match_status", "pending"),
        created_at=row["created_at"],
        display_status=display,
        display_label=FOUND_STATUS_LABEL[display],
    )
