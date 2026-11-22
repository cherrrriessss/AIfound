"""사진 처리: 형식 확인, EXIF(GPS 등) 제거, 크기 줄이기, 개인정보 가림.

원칙: 서버는 '가림 처리된 사진'만 저장한다. 원본은 메모리에서만 쓰고 버린다.
"""
from __future__ import annotations

import io

from PIL import Image, ImageDraw, ImageOps, UnidentifiedImageError

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


class ImageError(ValueError):
    pass


def load_image(data: bytes, max_bytes: int) -> Image.Image:
    if not data:
        raise ImageError("사진 파일이 비어 있어요.")
    if len(data) > max_bytes:
        raise ImageError(f"사진은 {max_bytes // (1024 * 1024)}MB 이하만 올릴 수 있어요.")
    try:
        img = Image.open(io.BytesIO(data))
        fmt = img.format
        img.load()
    except (UnidentifiedImageError, OSError) as e:
        raise ImageError("사진 파일을 읽을 수 없어요. JPG/PNG/WEBP 로 올려 주세요.") from e
    if fmt not in ALLOWED_FORMATS:
        raise ImageError("JPG/PNG/WEBP 사진만 올릴 수 있어요.")
    # 폰 사진의 회전 정보(EXIF Orientation)를 실제 픽셀에 반영 → 이후 좌표가 앱 화면과 일치
    img = ImageOps.exif_transpose(img)
    return img.convert("RGB")


def shrink(img: Image.Image, max_side: int) -> Image.Image:
    if max(img.size) <= max_side:
        return img
    img = img.copy()
    img.thumbnail((max_side, max_side))
    return img


def to_jpeg(img: Image.Image, quality: int = 85) -> bytes:
    """새로 인코딩 → EXIF(위치정보, 기기정보)가 따라오지 않는다."""
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()


def box_to_pixels(box: list[int], width: int, height: int) -> tuple[int, int, int, int]:
    """Gemini 좌표 [ymin, xmin, ymax, xmax] (0~1000) → 픽셀 (left, top, right, bottom)."""
    ymin, xmin, ymax, xmax = box
    return (
        round(xmin / 1000 * width),
        round(ymin / 1000 * height),
        round(xmax / 1000 * width),
        round(ymax / 1000 * height),
    )


def apply_masks(img: Image.Image, boxes: list[list[int]], pad_ratio: float = 0.02) -> Image.Image:
    """가림 영역을 검은 사각형으로 덮는다 (블러는 복원 위험이 있어 단색으로)."""
    if not boxes:
        return img
    out = img.copy()
    draw = ImageDraw.Draw(out)
    w, h = out.size
    pad_x, pad_y = int(w * pad_ratio), int(h * pad_ratio)
    for b in boxes:
        l, t, r, btm = box_to_pixels(b, w, h)
        draw.rectangle((max(0, l - pad_x), max(0, t - pad_y), min(w, r + pad_x), min(h, btm + pad_y)), fill=(40, 40, 40))
    return out


def coverage(detected: list[int], masks: list[list[int]]) -> float:
    """감지된 개인정보 영역 중 가림 박스로 덮인 비율 (0~1). 박스끼리 겹침은 넉넉하게 근사."""
    ymin, xmin, ymax, xmax = detected
    area = max(1, (ymax - ymin) * (xmax - xmin))
    covered = 0
    for m in masks:
        my0, mx0, my1, mx1 = m
        iy = max(0, min(ymax, my1) - max(ymin, my0))
        ix = max(0, min(xmax, mx1) - max(xmin, mx0))
        covered += iy * ix
    return min(1.0, covered / area)


def unmasked_regions(detected: list[list[int]], masks: list[list[int]], threshold: float = 0.8) -> list[list[int]]:
    """80% 이상 덮이지 않은 감지 영역 목록 → 남아 있으면 '미가림 경고'."""
    return [d for d in detected if coverage(d, masks) < threshold]
