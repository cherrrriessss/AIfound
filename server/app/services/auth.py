"""학교 메일 로그인 (6자리 인증코드, 비밀번호 없음).

흐름 (S02 → S03)
  1. POST /auth/request-code  {email: "student01"}           → 학교 메일로 6자리 코드 발송
  2. POST /auth/verify        {email, code: "123456"}        → access_token 발급
  3. 이후 모든 요청 헤더: Authorization: Bearer <access_token>
  4. is_new_user=True 이면 앱이 S03 프로필 설정으로 보냄

실제 모드: Supabase Auth 의 Email OTP 기능이 메일 발송·코드 검증·토큰 발급을 맡는다.
MOCK 모드: 코드를 서버 콘솔에 출력하고, 서버가 직접 JWT 를 만든다.
"""
from __future__ import annotations

import hmac
import logging
import re
import secrets
import time
import uuid
from dataclasses import dataclass
from typing import Optional

import jwt

from app.config import settings

log = logging.getLogger("aifound.auth")

LOCAL_PART = re.compile(r"^[A-Za-z0-9._-]{2,64}$")
MOCK_TOKEN_SECONDS = 60 * 60 * 24 * 7


class AuthError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def normalize_school_email(raw: str, domain: Optional[str] = None) -> str:
    """'student01' → 'student01@university.ac.kr'. 다른 도메인이면 거절."""
    domain = (domain or settings.school_domain).lower()
    value = raw.strip().lower()
    if "@" in value:
        local, _, dom = value.partition("@")
        if dom != domain:
            raise AuthError(f"@{domain} 학교 메일만 사용할 수 있어요.")
    else:
        local = value
    if not LOCAL_PART.match(local):
        raise AuthError("메일 아이디 형식이 올바르지 않아요.")
    return f"{local}@{domain}"


@dataclass
class _Pending:
    code: str
    expires_at: float
    sent_at: float
    attempts: int = 0


@dataclass
class AuthResult:
    user_id: str
    email: str
    access_token: str
    refresh_token: Optional[str]
    expires_in: int


class OtpGate:
    """재전송 대기시간과 시도 횟수 제한 (두 모드 공통). MOCK 에선 코드도 여기서 관리."""

    def __init__(self) -> None:
        self._pending: dict[str, _Pending] = {}

    def check_cooldown(self, email: str, now: Optional[float] = None) -> None:
        now = now or time.time()
        p = self._pending.get(email)
        if p and now - p.sent_at < settings.otp_resend_cooldown_seconds:
            wait = int(settings.otp_resend_cooldown_seconds - (now - p.sent_at)) + 1
            raise AuthError(f"{wait}초 후에 다시 보낼 수 있어요.", status=429)

    def issue(self, email: str, now: Optional[float] = None) -> str:
        now = now or time.time()
        code = f"{secrets.randbelow(1_000_000):06d}"
        self._pending[email] = _Pending(code=code, expires_at=now + settings.otp_ttl_seconds, sent_at=now)
        return code

    def mark_sent(self, email: str, now: Optional[float] = None) -> None:
        """실제 모드: 코드는 Supabase 가 갖고 있고, 여기선 보낸 시각·시도 횟수만 기록."""
        now = now or time.time()
        self._pending[email] = _Pending(code="", expires_at=now + settings.otp_ttl_seconds, sent_at=now)

    def count_attempt(self, email: str) -> None:
        p = self._pending.get(email)
        if p is None:
            raise AuthError("먼저 인증코드를 받아 주세요.")
        p.attempts += 1
        if p.attempts > settings.otp_max_attempts:
            self._pending.pop(email, None)
            raise AuthError("시도 횟수를 넘었어요. 인증코드를 다시 받아 주세요.", status=429)

    def verify_local(self, email: str, code: str, now: Optional[float] = None) -> None:
        now = now or time.time()
        self.count_attempt(email)
        p = self._pending[email]
        if now > p.expires_at:
            self._pending.pop(email, None)
            raise AuthError("인증코드가 만료됐어요. 다시 받아 주세요.")
        if not hmac.compare_digest(p.code, code):
            raise AuthError("인증코드가 맞지 않아요.")
        self._pending.pop(email, None)

    def clear(self, email: str) -> None:
        self._pending.pop(email, None)


gate = OtpGate()


# ---------------------------------------------------------------------------
# Supabase 클라이언트 (요청마다 새로 — 세션이 서로 섞이지 않게)
# ---------------------------------------------------------------------------
def _sb_auth_client():
    from supabase import create_client
    from supabase.lib.client_options import SyncClientOptions

    opts = SyncClientOptions(auto_refresh_token=False, persist_session=False)
    return create_client(settings.supabase_url, settings.supabase_anon_key or settings.supabase_service_key, opts)


# ---------------------------------------------------------------------------
# 공개 함수 (라우터에서 호출)
# ---------------------------------------------------------------------------
def request_code(raw_email: str) -> str:
    email = normalize_school_email(raw_email)
    gate.check_cooldown(email)
    if settings.mock:
        code = gate.issue(email)
        log.warning("[MOCK] %s 인증코드: %s", email, code)
        print(f"[MOCK] {email} 인증코드: {code}", flush=True)
        return email
    try:
        _sb_auth_client().auth.sign_in_with_otp({"email": email, "options": {"should_create_user": True}})
    except Exception as e:
        log.exception("Supabase OTP 발송 실패")
        raise AuthError("메일을 보내지 못했어요. 잠시 후 다시 시도해 주세요.", status=502) from e
    gate.mark_sent(email)
    return email


def verify_code(raw_email: str, code: str) -> AuthResult:
    email = normalize_school_email(raw_email)
    if settings.mock:
        gate.verify_local(email, code)
        user_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"aifound:{email}"))
        return AuthResult(user_id, email, _mock_token(user_id, email), None, MOCK_TOKEN_SECONDS)

    gate.count_attempt(email)
    try:
        res = _sb_auth_client().auth.verify_otp({"email": email, "token": code, "type": "email"})
    except Exception as e:
        raise AuthError("인증코드가 맞지 않거나 만료됐어요.") from e
    if not res.session or not res.user:
        raise AuthError("인증코드가 맞지 않거나 만료됐어요.")
    gate.clear(email)
    return AuthResult(res.user.id, email, res.session.access_token, res.session.refresh_token,
                      res.session.expires_in or 3600)


def refresh(refresh_token: str) -> AuthResult:
    if settings.mock:
        raise AuthError("MOCK 모드 토큰은 7일간 유효해요. 만료되면 다시 로그인하세요.")
    try:
        res = _sb_auth_client().auth.refresh_session(refresh_token)
    except Exception as e:
        raise AuthError("다시 로그인해 주세요.", status=401) from e
    if not res.session or not res.user:
        raise AuthError("다시 로그인해 주세요.", status=401)
    return AuthResult(res.user.id, res.user.email or "", res.session.access_token,
                      res.session.refresh_token, res.session.expires_in or 3600)


def user_from_token(token: str) -> tuple[str, str]:
    """Bearer 토큰 → (user_id, email). 실패하면 AuthError(401)."""
    if settings.mock:
        try:
            payload = jwt.decode(token, settings.mock_jwt_secret, algorithms=["HS256"], audience="aifound")
        except jwt.PyJWTError as e:
            raise AuthError("로그인이 필요해요.", status=401) from e
        return payload["sub"], payload["email"]
    try:
        res = _sb_auth_client().auth.get_user(token)
    except Exception as e:
        raise AuthError("로그인이 필요해요.", status=401) from e
    if not res or not res.user or not (res.user.email or "").endswith("@" + settings.school_domain):
        raise AuthError("로그인이 필요해요.", status=401)
    return res.user.id, res.user.email


def _mock_token(user_id: str, email: str) -> str:
    now = int(time.time())
    return jwt.encode(
        {"sub": user_id, "email": email, "aud": "aifound", "iat": now, "exp": now + MOCK_TOKEN_SECONDS},
        settings.mock_jwt_secret,
        algorithm="HS256",
    )
