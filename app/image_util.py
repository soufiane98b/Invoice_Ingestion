from __future__ import annotations

import io

from PIL import Image

MAX_SIDE = 1600
MAX_BYTES = 900_000
JPEG_QUALITY_START = 82


def compress_image(data: bytes, mime: str = "image/jpeg") -> tuple[bytes, str]:
    """Réduit la photo à ~1 Mo max pour Gemini et le quota egress Cloud Run."""
    if mime == "application/pdf":
        return data, mime
    try:
        image = Image.open(io.BytesIO(data))
    except Exception:
        return data, mime or "image/jpeg"

    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")
    elif image.mode == "L":
        image = image.convert("RGB")

    image.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.LANCZOS)
    quality = JPEG_QUALITY_START
    payload = _jpeg_bytes(image, quality)
    while len(payload) > MAX_BYTES and quality > 40:
        quality -= 8
        payload = _jpeg_bytes(image, quality)
    if len(payload) > MAX_BYTES:
        image.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
        payload = _jpeg_bytes(image, 70)
    return payload, "image/jpeg"


def _jpeg_bytes(image: Image.Image, quality: int) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=quality, optimize=True)
    return buffer.getvalue()
