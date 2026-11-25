"""속성 문장 -> 임베딩 벡터 (Gemini 임베딩 모델)."""
import math

from google import genai
from google.genai import types

from . import config

_client = None


def _gemini():
    global _client
    if _client is None:
        _client = genai.Client(api_key=config.GEMINI_API_KEY)
    return _client


def _normalize(vec: list[float]) -> list[float]:
    # 차원을 줄여서 받으면 길이가 1이 아니므로 직접 정규화해야 코사인 비교가 정확함
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def embed(text: str) -> list[float]:
    """문장 하나를 EMBED_DIM 차원 벡터로."""
    result = _gemini().models.embed_content(
        model=config.EMBED_MODEL,
        contents=text,
        config=types.EmbedContentConfig(
            task_type="SEMANTIC_SIMILARITY",
            output_dimensionality=config.EMBED_DIM,
        ),
    )
    return _normalize(list(result.embeddings[0].values))


def to_pgvector(vec: list[float]) -> str:
    """Supabase(pgvector)에 넣을 수 있는 문자열 형태: '[0.1,0.2,...]'"""
    return "[" + ",".join(f"{v:.6f}" for v in vec) + "]"
