import asyncio
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

from fastapi import UploadFile

MAX_PRODUCT_IMAGE_BYTES = 10 * 1024 * 1024
PRODUCT_MEDIA_URL_PREFIX = "/media/products"


class ProductMediaError(ValueError):
    pass


@dataclass(frozen=True)
class SavedProductImage:
    path: Path
    url_path: str


def _image_extension(content: bytes) -> str | None:
    if content.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return ".webp"
    return None


def _prepare_media_root(media_root: str) -> Path:
    root = Path(media_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _resolve_media_target(media_root: str, filename: str) -> tuple[Path, Path]:
    root = Path(media_root).expanduser().resolve()
    return root, (root / filename).resolve()


async def save_product_image(
    upload: UploadFile,
    *,
    media_root: str,
    subject: str = "Фото товара",
) -> SavedProductImage:
    content = await upload.read(MAX_PRODUCT_IMAGE_BYTES + 1)
    if not content:
        raise ProductMediaError("Выбранный файл пуст")
    if len(content) > MAX_PRODUCT_IMAGE_BYTES:
        raise ProductMediaError(f"{subject} должно быть не больше 10 МБ")

    extension = _image_extension(content)
    if extension is None:
        raise ProductMediaError("Поддерживаются фотографии JPEG, PNG и WebP")

    root = await asyncio.to_thread(_prepare_media_root, media_root)
    filename = f"{uuid4().hex}{extension}"
    target = root / filename
    await asyncio.to_thread(target.write_bytes, content)
    return SavedProductImage(
        path=target,
        url_path=f"{PRODUCT_MEDIA_URL_PREFIX}/{filename}",
    )


async def remove_product_image(image: SavedProductImage | None) -> None:
    if image is None:
        return
    try:
        await asyncio.to_thread(image.path.unlink, missing_ok=True)
    except OSError:
        return


async def remove_product_image_url(photo_url: str | None, *, media_root: str) -> None:
    if not photo_url:
        return
    path = urlsplit(photo_url).path
    prefix = f"{PRODUCT_MEDIA_URL_PREFIX}/"
    if not path.startswith(prefix):
        return
    filename = path.removeprefix(prefix)
    if not filename or Path(filename).name != filename:
        return
    root, target = await asyncio.to_thread(_resolve_media_target, media_root, filename)
    if target.parent != root:
        return
    try:
        await asyncio.to_thread(target.unlink, missing_ok=True)
    except OSError:
        return
