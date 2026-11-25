"""테스트용 가짜 좌표 (실제 숭실대 좌표가 아님). config 값은 테스트 동안만 바뀝니다."""
import pytest

from app import config

TEST_COORDS = {
    "형남공학관": (37.49600, 126.95700),
    "중앙도서관": (37.49610, 126.95855),   # 약 140m -> 가까운 건물
    "학생회관":   (37.49600, 126.95980),   # 약 250m
    "베어드홀":   (37.50150, 126.95700),   # 약 600m
}


@pytest.fixture(autouse=True)
def campus(monkeypatch):
    monkeypatch.setattr(config, "BUILDING_COORDS", TEST_COORDS)
    monkeypatch.setattr(config, "NEARBY_BUILDINGS", {})
    monkeypatch.setattr(config, "NEARBY_METERS", 200)   # 위 가짜 좌표 기준
