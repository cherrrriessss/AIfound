"""습득물: S10~S15 등록, S07 목록, S08 상세, S24 내가 등록한 습득물 / 건물·보관함."""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from app.deps import CurrentUser, current_user
from app.repo import Repo, get_repo
from app.schemas import AnalyzeOut, FoundCreateIn, FoundListOut, FoundOut, LockerOut
from app.services import found as found_svc
from app.services import match_client

router = APIRouter(tags=["found"])


@router.get("/buildings", response_model=list[str], summary="건물 이름 목록 (S13 건물 선택)")
def buildings(repo: Repo = Depends(get_repo)):
    return repo.list_buildings()


@router.get("/lockers", response_model=list[LockerOut], summary="보관함 목록 (S14, 습득 건물과 같은 건물 먼저)")
def lockers(building: Optional[str] = None, repo: Repo = Depends(get_repo)):
    out = [found_svc.locker_out(lk, building) for lk in repo.list_lockers()]
    return sorted(out, key=lambda lk: (not lk.same_building, lk.building, lk.name))


@router.post("/found/analyze", response_model=AnalyzeOut,
             summary="사진 → AI 속성·개인정보 영역 (S10 촬영 직후, 저장 안 함)")
async def analyze(image: UploadFile = File(...), user: CurrentUser = Depends(current_user)):
    data = await image.read()
    # Gemini 호출은 동기 → 스레드로 넘겨 서버가 멈추지 않게
    try:
        return await run_in_threadpool(found_svc.analyze, data)
    except found_svc.FoundError as e:
        raise HTTPException(status_code=e.status, detail=str(e)) from e


@router.post("/found", response_model=FoundOut, status_code=201,
             summary="습득물 등록 (S14 '등록하기'). multipart: image + data(JSON 문자열)")
async def create_found(
    background: BackgroundTasks,
    image: UploadFile = File(...),
    data: str = Form(..., description="FoundCreateIn JSON"),
    user: CurrentUser = Depends(current_user),
    repo: Repo = Depends(get_repo),
):
    try:
        body = FoundCreateIn.model_validate_json(data)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors(include_url=False, include_context=False)) from e
    img = await image.read()
    try:
        row = await run_in_threadpool(found_svc.register, repo, user.id, img, body)
    except found_svc.FoundError as e:
        raise HTTPException(status_code=e.status, detail=str(e)) from e
    # 저장 직후 매칭 서버 호출 (주희선) — 응답을 기다리지 않음. 15 화면은 match_status 로 진행 상황 확인
    background.add_task(match_client.match_found, str(row["id"]))
    return found_svc.to_found_out(repo, row)


def _outs(repo: Repo, rows: list) -> list[FoundOut]:
    """목록 변환: 보관함·매칭을 한 번에 읽어서 행마다 DB 를 다시 부르지 않게."""
    lockers = {str(lk["id"]): lk for lk in repo.list_lockers()}
    matches = repo.matches_for_found([str(r["id"]) for r in rows])
    return [found_svc.to_found_out(repo, r, lockers, matches) for r in rows]


@router.get("/found", response_model=FoundListOut,
            summary="습득물 찾아보기 (S07): 검색 + 종류·색·건물·날짜 필터, 최신순")
def list_found(
    q: Optional[str] = Query(default=None, max_length=40, description="물건 이름·브랜드·모델·특징 검색"),
    category: Optional[str] = None,
    color: Optional[str] = None,
    building: Optional[str] = None,
    date_from: Optional[datetime] = Query(default=None, description="이 시각 이후에 주운 것"),
    date_to: Optional[datetime] = Query(default=None, description="이 시각 이전에 주운 것"),
    status: Optional[str] = Query(default="stored"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=50),
    user: CurrentUser = Depends(current_user),
    repo: Repo = Depends(get_repo),
):
    rows, total = repo.list_found(category=category, building=building, status=status,
                                  finder_id=None, offset=(page - 1) * size, limit=size,
                                  color=color, date_from=date_from, date_to=date_to, q=q)
    return FoundListOut(items=_outs(repo, rows), total=total, page=page, size=size)


@router.get("/me/found", response_model=list[FoundOut],
            summary="내가 등록한 습득물 (S24) — display_label 이 '보관 중/주인 확인됨/수령 완료' 배지")
def my_found(user: CurrentUser = Depends(current_user), repo: Repo = Depends(get_repo)):
    rows, _ = repo.list_found(category=None, building=None, status=None,
                              finder_id=user.id, offset=0, limit=100)
    return _outs(repo, rows)


@router.get("/found/{found_id}", response_model=FoundOut,
            summary="습득물 상세 (S08). S15 에서는 match_status 를 몇 초마다 다시 읽어 진행 상황을 보여 준다")
def get_found(found_id: str, user: CurrentUser = Depends(current_user), repo: Repo = Depends(get_repo)):
    row = repo.get_found(found_id)
    if not row:
        raise HTTPException(status_code=404, detail="습득물을 찾을 수 없어요.")
    return found_svc.to_found_out(repo, row)
