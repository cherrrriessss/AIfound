"""건물 사이 거리 / '가까운 건물' 판단 (config 의 BUILDING_COORDS, NEARBY_BUILDINGS 사용)."""
from typing import Optional
import math

from . import config


def distance_m(a: str, b: str) -> Optional[float]:
    if a and a == b:
        return 0.0
    pa, pb = config.BUILDING_COORDS.get(a), config.BUILDING_COORDS.get(b)
    if not pa or not pb:
        return None
    lat1, lon1, lat2, lon2 = map(math.radians, (*pa, *pb))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6_371_000 * math.asin(math.sqrt(h))


def is_nearby(a: str, b: str) -> bool:
    manual = config.NEARBY_BUILDINGS
    if b in manual.get(a, []) or a in manual.get(b, []):
        return True
    d = distance_m(a, b)
    return d is not None and 0 < d <= config.NEARBY_METERS
