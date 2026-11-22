"""환경 설정. 값은 .env 파일 또는 환경변수에서 읽는다.

MOCK=true 이면 Supabase/Gemini 키 없이도 서버가 돌아간다
(메모리 DB + 콘솔에 인증코드 출력 + 고정 AI 결과). 화면 개발·시연용.

키 이름은 주희선 님 서버(.env)와 같게 맞췄다 → 같은 .env 를 같이 써도 된다.
"""
import os
from dataclasses import dataclass, field
from pathlib import Path


def _load_dotenv(path: Path) -> None:
    """python-dotenv 없이 .env 를 읽는 최소 구현 (이미 있는 환경변수는 덮어쓰지 않음)."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def _env(*names: str, default: str = "") -> str:
    """여러 이름 중 처음으로 값이 있는 것. 빈 값("")은 없는 것으로 본다."""
    for n in names:
        v = os.getenv(n)
        if v:
            return v
    return default


def _bool(name: str, default: bool) -> bool:
    return _env(name, default=str(default)).lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    mock: bool = field(default_factory=lambda: _bool("MOCK", True))
    # MOCK 에서 '학생증(개인정보 있음)' 결과를 흉내 낼지 (S11 가림 화면 시연용)
    mock_pii: bool = field(default_factory=lambda: _bool("MOCK_PII", False))

    # 학교 메일 도메인 (이 도메인만 로그인 허용) — 팀에서 최종 확인 필요
    school_domain: str = field(default_factory=lambda: _env("SCHOOL_EMAIL_DOMAIN", default="soongsil.ac.kr"))

    # Supabase (서버에만 보관 — 앱에 절대 넣지 않음)
    supabase_url: str = field(default_factory=lambda: _env("SUPABASE_URL"))
    supabase_service_key: str = field(default_factory=lambda: _env("SUPABASE_SERVICE_KEY", "SUPABASE_SERVICE_ROLE_KEY"))
    # 인증코드 발송/확인용. 없으면 service 키로 대신한다.
    supabase_anon_key: str = field(default_factory=lambda: _env("SUPABASE_ANON_KEY", "SUPABASE_PUBLISHABLE_KEY"))
    photo_bucket: str = field(default_factory=lambda: _env("PHOTO_BUCKET", default="found-photos"))

    # Gemini (주희선 님과 같은 키·모델)
    gemini_api_key: str = field(default_factory=lambda: _env("GEMINI_API_KEY"))
    gemini_model: str = field(default_factory=lambda: _env("GEMINI_MODEL", default="gemini-2.5-flash"))

    # 매칭 서버(주희선) 내부 호출: 저장 직후 POST {MATCH_API_URL}/internal/match/...
    match_api_url: str = field(default_factory=lambda: _env("MATCH_API_URL").rstrip("/"))
    internal_key: str = field(default_factory=lambda: _env("INTERNAL_KEY"))

    # 건물 목록 (13 건물 선택). 쉼표로 구분. 비우면 lockers 표의 건물 이름을 쓴다.
    campus_buildings: str = field(default_factory=lambda: _env("CAMPUS_BUILDINGS"))

    # MOCK 모드에서 서버가 직접 발급하는 토큰 서명용
    mock_jwt_secret: str = field(default_factory=lambda: _env("MOCK_JWT_SECRET", default="dev-only-secret-change-me-32bytes-min!!"))

    # 인증코드 정책 (S02: 04:59 타이머)
    otp_ttl_seconds: int = 300
    otp_resend_cooldown_seconds: int = 60
    otp_max_attempts: int = 5

    # 사진 정책
    max_image_bytes: int = 10 * 1024 * 1024
    image_max_side: int = 1600

    def building_list(self) -> list[str]:
        return [b.strip() for b in self.campus_buildings.split(",") if b.strip()]


settings = Settings()
