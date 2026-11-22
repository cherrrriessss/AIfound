"""S02 학교 메일 로그인 / S03 프로필 / S26 알림 설정."""
from fastapi import APIRouter, Depends, HTTPException

from app.config import settings
from app.deps import CurrentUser, current_user
from app.repo import Repo, get_repo
from app.schemas import (OkOut, ProfileOut, ProfileUpdateIn, RefreshIn, RequestCodeIn, RequestCodeOut,
                         SummaryOut, TokenOut, VerifyIn)
from app.services.status import build_summary
from app.services import auth

router = APIRouter(tags=["auth"])


def _profile_out(row: dict) -> ProfileOut:
    return ProfileOut(**{k: row.get(k) for k in ProfileOut.model_fields if row.get(k) is not None})


@router.post("/auth/request-code", response_model=RequestCodeOut, summary="인증코드 메일 발송 (S02 '인증코드 받기')")
def request_code(body: RequestCodeIn):
    try:
        email = auth.request_code(body.email)
    except auth.AuthError as e:
        raise HTTPException(status_code=e.status, detail=str(e)) from e
    return RequestCodeOut(email=email, expires_in=settings.otp_ttl_seconds,
                          resend_after=settings.otp_resend_cooldown_seconds)


@router.post("/auth/verify", response_model=TokenOut, summary="인증코드 확인 → 토큰 발급 (S02 '로그인')")
def verify(body: VerifyIn, repo: Repo = Depends(get_repo)):
    try:
        result = auth.verify_code(body.email, body.code)
    except auth.AuthError as e:
        raise HTTPException(status_code=e.status, detail=str(e)) from e
    profile, created = repo.ensure_profile(result.user_id, result.email)
    is_new = created or not profile.get("name")   # 이름이 없으면 S03 으로
    return TokenOut(access_token=result.access_token, refresh_token=result.refresh_token,
                    expires_in=result.expires_in, is_new_user=is_new, user=_profile_out(profile))


@router.post("/auth/refresh", response_model=TokenOut, summary="토큰 갱신")
def refresh(body: RefreshIn, repo: Repo = Depends(get_repo)):
    try:
        result = auth.refresh(body.refresh_token)
    except auth.AuthError as e:
        raise HTTPException(status_code=e.status, detail=str(e)) from e
    profile, _ = repo.ensure_profile(result.user_id, result.email)
    return TokenOut(access_token=result.access_token, refresh_token=result.refresh_token,
                    expires_in=result.expires_in, is_new_user=not profile.get("name"), user=_profile_out(profile))


@router.get("/me", response_model=ProfileOut, summary="내 프로필")
def me(user: CurrentUser = Depends(current_user), repo: Repo = Depends(get_repo)):
    return _profile_out(repo.get_profile(user.id) or {})


@router.patch("/me", response_model=ProfileOut, summary="프로필 저장: 이름·학과 (S03)")
def update_me(body: ProfileUpdateIn, user: CurrentUser = Depends(current_user), repo: Repo = Depends(get_repo)):
    fields = body.model_dump(exclude_none=True)
    if not fields:
        return _profile_out(repo.get_profile(user.id) or {})
    return _profile_out(repo.update_profile(user.id, fields))


@router.get("/me/summary", response_model=SummaryOut, summary="마이페이지 숫자 (S22) + 돌려준 수 (S24)")
def my_summary(user: CurrentUser = Depends(current_user), repo: Repo = Depends(get_repo)):
    return build_summary(repo, user.id)


@router.delete("/me", response_model=OkOut,
               summary="회원 탈퇴 (S28). 내 신고·수령 기록 삭제, 등록한 습득물은 남기고 등록자만 지움")
def delete_me(user: CurrentUser = Depends(current_user), repo: Repo = Depends(get_repo)):
    try:
        repo.delete_account(user.id)
    except Exception as e:
        raise HTTPException(status_code=500, detail="탈퇴 처리 중 문제가 생겼어요. 잠시 후 다시 시도해 주세요.") from e
    return OkOut()
