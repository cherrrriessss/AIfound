"""설정값 모음. 값은 .env 파일에서 읽어 옵니다."""
import os

from dotenv import load_dotenv

load_dotenv()

# ---- 외부 서비스 키 (절대 앱이나 깃허브에 올리지 말 것) ----
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")   # service_role 키 (서버 전용)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
FIREBASE_CREDENTIALS = os.getenv("FIREBASE_CREDENTIALS", "firebase-service-account.json")
INTERNAL_KEY = os.getenv("INTERNAL_KEY", "change-me")         # 서버끼리 호출할 때 쓰는 비밀값
TIMEZONE = "Asia/Seoul"

# ---- 모델 ----
# 모델 이름은 자주 바뀌므로 Google AI Studio에서 확인 후 .env에서 바꾸세요.
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
EMBED_MODEL = os.getenv("EMBED_MODEL", "gemini-embedding-001")
EMBED_DIM = int(os.getenv("EMBED_DIM", "768"))   # pgvector 인덱스는 2000차원 이하만 가능

# ---- 물건 종류 (16 분실 신고 화면의 칩과 같아야 함) ----
CATEGORIES = ["이어폰", "지갑", "학생증·카드", "휴대폰", "기타"]

# ---- 매칭 점수 (발표 자료 기준 초기값, 테스트 후 조정) ----
W_ATTR, W_SEM, W_PLACE, W_TIME = 40, 25, 20, 15

SEM_FLOOR = float(os.getenv("SEM_FLOOR", "0.5"))   # 이 값 이하의 코사인 유사도는 0점 처리
TIME_WINDOW_HOURS = 72          # 분실 시간대가 끝나고 이만큼 지나서 주웠으면 시간 점수 0
CANDIDATE_DAYS = 14             # 이 기간 안의 신고/습득물만 후보로 봄
CANDIDATE_LIMIT = 20            # 벡터 검색으로 가져올 후보 수
RERANK_TOP_K = 5                # AI 재비교할 상위 후보 수
RERANK_WEIGHT = 0.4             # 순서 정할 때: 규칙 점수 x 0.6 + AI 판단 x 0.4
AI_MIN_LIKELIHOOD = 30          # AI가 '같은 물건 가능성'을 이보다 낮게 보면 후보에서 뺌
NOTIFY_THRESHOLD = int(float(os.getenv("NOTIFY_THRESHOLD", "60")))   # 일치율 이 점수 이상만 후보/알림
NOTIFY_TOP_N = 3                # 알림 보낼 최대 인원(상위 3명)

# 속성 비교에 쓰는 항목과 가중치 (12 AI 인식 결과 화면의 종류/브랜드/색 + 모델)
ATTR_KEYS = {"category": 0.35, "brand": 0.25, "model": 0.2, "color": 0.2}

# ---- 숭실대학교 캠퍼스 ----
SCHOOL_NAME = "숭실대학교"

# 건물 이름 목록은 김준희 서버(/buildings, CAMPUS_BUILDINGS)가 관리해요. 아래 좌표의 이름도 그 목록과 똑같이 써 주세요.

# 건물 좌표 (위도, 경도) -> 같은 건물이 아니어도 200m 안이면 '가까운 건물'로 장소 점수 절반.
# 카카오맵/네이버지도에서 건물을 우클릭하면 좌표를 볼 수 있어요.
# 비워 두면 '같은 건물이면 만점, 아니면 0점'으로만 계산돼요.
BUILDING_COORDS: dict[str, tuple[float, float]] = {
    # "형남공학관": (37.0000, 126.0000),   <- 이런 형식으로 채우기
}

NEARBY_METERS = 200           # 이 거리 안이면 '가까운 건물' (장소 점수 절반)

# 좌표 대신 직접 '가까운 건물'을 정하고 싶으면 여기에 (좌표보다 우선)
NEARBY_BUILDINGS: dict[str, list[str]] = {
    # "형남공학관": ["정보과학관", "진리관"],
}

# 수령 코드 만들 때 쓰는 비밀값 (.env 에서 바꾸세요)
PICKUP_SECRET = os.getenv("PICKUP_SECRET", "change-this-pickup-secret")

# 21 '어떤 점이 달랐나요?' 선택지
REJECT_REASONS = ["category", "color", "brand_model", "place_time", "other"]
