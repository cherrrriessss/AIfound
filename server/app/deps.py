"""공통 의존성: 로그인 사용자 꺼내기."""
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException

from app.repo import Repo, get_repo
from app.services import auth


@dataclass
class CurrentUser:
    id: str
    email: str


def current_user(authorization: str = Header(default=""), repo: Repo = Depends(get_repo)) -> CurrentUser:
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="로그인이 필요해요.")
    try:
        user_id, email = auth.user_from_token(token)
    except auth.AuthError as e:
        raise HTTPException(status_code=e.status, detail=str(e)) from e
    repo.ensure_profile(user_id, email)
    return CurrentUser(id=user_id, email=email)
