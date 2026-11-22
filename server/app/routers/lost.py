"""분실 신고: S16 작성, S17 완료(매칭 결과), S23 내 신고·수정·'찾았어요'."""
import uuid
from datetime import datetime

from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from starlette.concurrency import run_in_threadpool

from app.config import settings
from app.deps import CurrentUser, current_user
from app.repo import Repo, Row, get_repo
from app.schemas import LostCreateIn, LostOut, LostUpdateIn
from app.services import images, match_client
from app.services.status import LOST_STAGE_LABEL, lost_stage

router = APIRouter(tags=["lost"])


def _out(repo: Repo, row: Row, match=None, matches: Optional[list] = None) -> LostOut:
    if matches is None:
        matches = repo.matches_for_lost([str(row["id"])])
    stage, count = lost_stage(row, matches)
    return LostOut(
        stage=stage, stage_label=LOST_STAGE_LABEL[stage], match_count=count,
        id=str(row["id"]), category=row["category"], attrs=row.get("attrs") or {},
        description=row.get("description"), buildings=row.get("buildings") or [],
        lost_from=row["lost_from"], lost_to=row["lost_to"],
        photo_url=repo.photo_url(row.get("photo_path")),
        status=row.get("status", "open"), created_at=row["created_at"], match=match,
    )


def _dt(v) -> datetime:
    """DB 에서 온 값(문자열)과 요청 값(datetime)을 같이 비교하려고."""
    return v if isinstance(v, datetime) else datetime.fromisoformat(str(v).replace("Z", "+00:00"))


def _own(repo: Repo, lost_id: str, user: CurrentUser) -> Row:
    row = repo.get_lost(lost_id)
    if not row or str(row["owner_id"]) != user.id:
        raise HTTPException(status_code=404, detail="분실 신고를 찾을 수 없어요.")
    return row


@router.post("/lost", response_model=LostOut, status_code=201,
             summary="분실 신고 (S16) → 저장 직후 매칭, 결과를 match 에 담아 17 화면으로")
async def create_lost(body: LostCreateIn, user: CurrentUser = Depends(current_user),
                      repo: Repo = Depends(get_repo)):
    if body.lost_from > body.lost_to:
        raise HTTPException(status_code=422, detail="잃어버린 시간 범위를 다시 확인해 주세요.")
    row = repo.insert_lost({
        "owner_id": user.id,
        "category": body.category,
        "attrs": body.to_attrs(),
        "description": body.description,
        "buildings": body.buildings,
        "lost_from": body.lost_from,
        "lost_to": body.lost_to,
    })
    # 17 화면에 '비슷한 습득물'을 보여 주려고 매칭 응답을 기다린다 (실패해도 신고는 저장됨)
    match = await run_in_threadpool(match_client.match_lost, str(row["id"]))
    return _out(repo, row, match)


@router.post("/lost/{lost_id}/photo", response_model=LostOut, summary="참고 사진 올리기 (S16, 선택)")
async def upload_lost_photo(lost_id: str, image: UploadFile = File(...),
                            user: CurrentUser = Depends(current_user), repo: Repo = Depends(get_repo)):
    _own(repo, lost_id, user)
    data = await image.read()
    try:
        img = images.shrink(images.load_image(data, settings.max_image_bytes), settings.image_max_side)
    except images.ImageError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    path = f"lost/{lost_id}/{uuid.uuid4().hex}.jpg"     # lost/ = 서버 서명 URL 로만 제공
    repo.upload_photo(path, images.to_jpeg(img))
    return _out(repo, repo.update_lost(lost_id, {"photo_path": path}))


@router.get("/me/lost", response_model=list[LostOut],
            summary="내 분실 신고 (S23). tab=open '진행 중', tab=done '완료' (종료·수령 완료)")
def my_lost(tab: Optional[str] = Query(default=None, pattern="^(open|done)$"),
            user: CurrentUser = Depends(current_user), repo: Repo = Depends(get_repo)):
    rows = repo.list_lost(user.id)
    matches = repo.matches_for_lost([str(r["id"]) for r in rows])
    outs = [_out(repo, r, matches=matches) for r in rows]
    if tab == "open":
        outs = [o for o in outs if o.stage not in ("closed", "received")]
    elif tab == "done":
        outs = [o for o in outs if o.stage in ("closed", "received")]
    return outs


@router.get("/lost/{lost_id}", response_model=LostOut, summary="내 분실 신고 상세")
def get_lost(lost_id: str, user: CurrentUser = Depends(current_user), repo: Repo = Depends(get_repo)):
    return _out(repo, _own(repo, lost_id, user))


@router.patch("/lost/{lost_id}", response_model=LostOut, summary="신고 수정 (S23 '수정') → 다시 매칭")
def update_lost(lost_id: str, body: LostUpdateIn, background: BackgroundTasks,
                user: CurrentUser = Depends(current_user), repo: Repo = Depends(get_repo)):
    row = _own(repo, lost_id, user)
    if row.get("status") != "open":
        raise HTTPException(status_code=409, detail="종료된 신고는 수정할 수 없어요.")
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        return _out(repo, row)

    fields: Row = {}
    attrs = dict(row.get("attrs") or {})
    for key in ("category", "brand", "model", "color", "features"):
        if key in changes:
            attrs[key] = changes[key]
    if any(k in changes for k in ("category", "brand", "model", "color", "features")):
        fields["attrs"] = attrs
    for key in ("category", "description", "buildings", "lost_from", "lost_to"):
        if key in changes and changes[key] is not None:
            fields[key] = changes[key]
    if _dt(fields.get("lost_from", row["lost_from"])) > _dt(fields.get("lost_to", row["lost_to"])):
        raise HTTPException(status_code=422, detail="잃어버린 시간 범위를 다시 확인해 주세요.")
    # 내용이 바뀌면 임베딩도 다시 만들어야 하므로 비우고 매칭을 다시 부른다
    fields["embedding"] = None
    updated = repo.update_lost(lost_id, fields)
    background.add_task(match_client.match_lost, lost_id)
    return _out(repo, updated)


@router.post("/lost/{lost_id}/close", response_model=LostOut, summary="'찾았어요' — 신고 종료 (S23)")
def close_lost(lost_id: str, user: CurrentUser = Depends(current_user), repo: Repo = Depends(get_repo)):
    _own(repo, lost_id, user)
    return _out(repo, repo.update_lost(lost_id, {"status": "closed"}))
