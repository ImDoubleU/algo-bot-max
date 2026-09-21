from __future__ import annotations

import asyncio
import ipaddress
import json
import socket
import warnings
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit
from uuid import uuid4

import httpx
from fastapi import UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_PRODUCT_IMAGE_BYTES = 10 * 1024 * 1024
PRODUCT_MEDIA_URL_PREFIX = "/media/products"
MAX_PRODUCT_IMAGE_PIXELS = 40_000_000
MASTER_IMAGE_MAX_SIZE = 2500
DETAIL_IMAGE_MAX_SIZE = 1600
THUMBNAIL_IMAGE_SIZE = 480
MASTER_IMAGE_QUALITY = 90
DETAIL_IMAGE_QUALITY = 84
THUMBNAIL_IMAGE_QUALITY = 78
MASTER_IMAGE_MAX_BYTES = 2_500_000
DETAIL_IMAGE_MAX_BYTES = 600_000
THUMBNAIL_IMAGE_MAX_BYTES = 200_000
MIN_CROP_FRACTION = 0.02
MAX_REMOTE_REDIRECTS = 5
MAX_REMOTE_METADATA_BYTES = 256 * 1024
REMOTE_IMAGE_TIMEOUT_SECONDS = 20.0
YANDEX_PUBLIC_DOWNLOAD_API = "https://cloud-api.yandex.net/v1/disk/public/resources/download"
YANDEX_PUBLIC_HOSTS = {
    "disk.yandex.com",
    "disk.yandex.kz",
    "disk.yandex.ru",
    "yadi.sk",
}
GOOGLE_DRIVE_HOSTS = {"drive.google.com", "www.drive.google.com"}
REDIRECT_STATUSES = {301, 302, 303, 307, 308}
REMOTE_REQUEST_HEADERS = {
    "Accept": "image/avif,image/webp,image/png,image/jpeg,*/*;q=0.5",
    "User-Agent": "AlgoMAX/1.0 product-image-import",
}


class ProductMediaError(ValueError):
    pass


@dataclass(frozen=True)
class SavedProductImage:
    path: Path
    url_path: str
    thumbnail_path: Path | None = None
    thumbnail_url_path: str | None = None
    master_path: Path | None = None
    master_url_path: str | None = None

    @property
    def paths(self) -> tuple[Path, ...]:
        return tuple(
            dict.fromkeys(
                path
                for path in (self.path, self.thumbnail_path, self.master_path)
                if path is not None
            )
        )


@dataclass(frozen=True)
class ProductImageCrop:
    x: float
    y: float
    width: float
    height: float

    def validate(self) -> ProductImageCrop:
        values = (self.x, self.y, self.width, self.height)
        if any(not 0 <= value <= 1 for value in values):
            raise ProductMediaError("Область кадрирования выходит за границы изображения")
        if self.width < MIN_CROP_FRACTION or self.height < MIN_CROP_FRACTION:
            raise ProductMediaError("Область кадрирования слишком мала")
        if self.x + self.width > 1.000001 or self.y + self.height > 1.000001:
            raise ProductMediaError("Область кадрирования выходит за границы изображения")
        return self


def create_remote_product_image_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=httpx.Timeout(REMOTE_IMAGE_TIMEOUT_SECONDS),
        follow_redirects=False,
        trust_env=False,
    )


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


def _has_alpha(image: Image.Image) -> bool:
    return image.mode in {"RGBA", "LA"} or (
        image.mode == "P" and "transparency" in image.info
    )


def _decoded_product_image(content: bytes, *, subject: str) -> Image.Image:
    if _image_extension(content) is None:
        raise ProductMediaError("Поддерживаются фотографии JPEG, PNG и WebP")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as source:
                if (source.format or "").upper() not in {"JPEG", "PNG", "WEBP"}:
                    raise ProductMediaError("Поддерживаются фотографии JPEG, PNG и WebP")
                if source.width * source.height > MAX_PRODUCT_IMAGE_PIXELS:
                    raise ProductMediaError(
                        f"{subject} имеет слишком большое разрешение"
                    )
                source.load()
                image = ImageOps.exif_transpose(source)
                image = image.convert("RGBA" if _has_alpha(image) else "RGB")
    except ProductMediaError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ProductMediaError(f"{subject} имеет слишком большое разрешение") from exc
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ProductMediaError("Файл поврежден или не является изображением") from exc
    if image.width < 2 or image.height < 2:
        raise ProductMediaError(f"{subject} имеет слишком маленькое разрешение")
    return image


def _fit_within(image: Image.Image, max_size: int) -> Image.Image:
    result = image.copy()
    if max(result.size) > max_size:
        result.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
    return result


def _crop_box(image: Image.Image, crop: ProductImageCrop) -> tuple[int, int, int, int]:
    crop.validate()
    left = max(0, min(image.width - 1, round(crop.x * image.width)))
    top = max(0, min(image.height - 1, round(crop.y * image.height)))
    right = max(left + 1, min(image.width, round((crop.x + crop.width) * image.width)))
    bottom = max(top + 1, min(image.height, round((crop.y + crop.height) * image.height)))
    return left, top, right, bottom


def _encode_webp(
    image: Image.Image,
    *,
    quality: int,
    max_bytes: int,
) -> bytes:
    candidate = image.copy()
    while True:
        for current_quality in range(quality, 49, -7):
            output = BytesIO()
            candidate.save(
                output,
                format="WEBP",
                quality=current_quality,
                method=4,
                exact=_has_alpha(candidate),
            )
            encoded = output.getvalue()
            if len(encoded) <= max_bytes or current_quality <= 50:
                break
        if len(encoded) <= max_bytes or max(candidate.size) <= THUMBNAIL_IMAGE_SIZE:
            return encoded
        next_size = (
            max(1, round(candidate.width * 0.88)),
            max(1, round(candidate.height * 0.88)),
        )
        if next_size == candidate.size:
            return encoded
        candidate = candidate.resize(next_size, Image.Resampling.LANCZOS)


def _write_atomic(path: Path, content: bytes) -> None:
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_bytes(content)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _save_product_image_set(
    content: bytes,
    *,
    media_root: str,
    subject: str,
    crop: ProductImageCrop | None,
) -> SavedProductImage:
    root = _prepare_media_root(media_root)
    image = _decoded_product_image(content, subject=subject)
    master = _fit_within(image, MASTER_IMAGE_MAX_SIZE)
    detail_source = master.crop(_crop_box(master, crop)) if crop is not None else master.copy()
    detail = _fit_within(detail_source, DETAIL_IMAGE_MAX_SIZE)
    thumbnail = ImageOps.fit(
        detail_source,
        (THUMBNAIL_IMAGE_SIZE, THUMBNAIL_IMAGE_SIZE),
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.5),
    )

    token = uuid4().hex
    master_path = root / f"{token}-master.webp"
    detail_path = root / f"{token}-detail.webp"
    thumbnail_path = root / f"{token}-thumb.webp"
    created: list[Path] = []
    try:
        for path, encoded in (
            (
                master_path,
                _encode_webp(
                    master,
                    quality=MASTER_IMAGE_QUALITY,
                    max_bytes=MASTER_IMAGE_MAX_BYTES,
                ),
            ),
            (
                detail_path,
                _encode_webp(
                    detail,
                    quality=DETAIL_IMAGE_QUALITY,
                    max_bytes=DETAIL_IMAGE_MAX_BYTES,
                ),
            ),
            (
                thumbnail_path,
                _encode_webp(
                    thumbnail,
                    quality=THUMBNAIL_IMAGE_QUALITY,
                    max_bytes=THUMBNAIL_IMAGE_MAX_BYTES,
                ),
            ),
        ):
            _write_atomic(path, encoded)
            created.append(path)
    except Exception:
        for path in created:
            path.unlink(missing_ok=True)
        raise
    return SavedProductImage(
        path=detail_path,
        url_path=f"{PRODUCT_MEDIA_URL_PREFIX}/{detail_path.name}",
        thumbnail_path=thumbnail_path,
        thumbnail_url_path=f"{PRODUCT_MEDIA_URL_PREFIX}/{thumbnail_path.name}",
        master_path=master_path,
        master_url_path=f"{PRODUCT_MEDIA_URL_PREFIX}/{master_path.name}",
    )


async def _save_product_image_content(
    content: bytes,
    *,
    media_root: str,
    subject: str,
    crop: ProductImageCrop | None = None,
) -> SavedProductImage:
    if not content:
        raise ProductMediaError(f"{subject} пусто")
    if len(content) > MAX_PRODUCT_IMAGE_BYTES:
        raise ProductMediaError(f"{subject} должно быть не больше 10 МБ")

    return await asyncio.to_thread(
        _save_product_image_set,
        content,
        media_root=media_root,
        subject=subject,
        crop=crop,
    )


async def save_product_image(
    upload: UploadFile,
    *,
    media_root: str,
    subject: str = "Фото товара",
    crop: ProductImageCrop | None = None,
) -> SavedProductImage:
    content = await upload.read(MAX_PRODUCT_IMAGE_BYTES + 1)
    if not content:
        raise ProductMediaError("Выбранный файл пуст")
    return await _save_product_image_content(
        content,
        media_root=media_root,
        subject=subject,
        crop=crop,
    )


def _is_yandex_public_link(url: str) -> bool:
    parsed = urlsplit(url)
    return (parsed.hostname or "").casefold() in YANDEX_PUBLIC_HOSTS


def _google_drive_file_id(url: str) -> tuple[str, str | None] | None:
    parsed = urlsplit(url)
    if (parsed.hostname or "").casefold() not in GOOGLE_DRIVE_HOSTS:
        return None

    path_parts = [part for part in parsed.path.split("/") if part]
    file_id: str | None = None
    if len(path_parts) >= 3 and path_parts[0] == "file" and path_parts[1] == "d":
        file_id = path_parts[2]
    elif len(path_parts) >= 2 and path_parts[0] == "d":
        file_id = path_parts[1]
    else:
        file_id = parse_qs(parsed.query).get("id", [None])[0]

    if not file_id or not all(char.isalnum() or char in "_-" for char in file_id):
        return None
    resource_key = parse_qs(parsed.query).get("resourcekey", [None])[0]
    return file_id, resource_key


def _google_drive_download_url(file_id: str, resource_key: str | None) -> str:
    params = {"id": file_id, "export": "download", "confirm": "t"}
    if resource_key:
        params["resourcekey"] = resource_key
    return f"https://drive.usercontent.google.com/download?{urlencode(params)}"


def _address_is_global(address: str) -> bool:
    parsed = ipaddress.ip_address(address)
    if isinstance(parsed, ipaddress.IPv6Address) and parsed.ipv4_mapped is not None:
        parsed = parsed.ipv4_mapped
    return parsed.is_global


async def _ensure_public_remote_url(url: str) -> None:
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise ProductMediaError("Некорректная ссылка на фото") from exc

    if parsed.scheme.casefold() not in {"http", "https"} or not parsed.hostname:
        raise ProductMediaError("Ссылка на фото должна начинаться с http:// или https://")
    if parsed.username or parsed.password:
        raise ProductMediaError("Ссылка на фото не должна содержать логин или пароль")

    resolved_port = port or (443 if parsed.scheme.casefold() == "https" else 80)
    try:
        addresses = await asyncio.to_thread(
            socket.getaddrinfo,
            parsed.hostname,
            resolved_port,
            type=socket.SOCK_STREAM,
        )
    except OSError as exc:
        raise ProductMediaError("Не удалось найти сервер по ссылке на фото") from exc

    remote_addresses = {entry[4][0] for entry in addresses}
    if not remote_addresses or any(not _address_is_global(address) for address in remote_addresses):
        raise ProductMediaError("Ссылка на фото ведет во внутреннюю или локальную сеть")


async def _fetch_remote_bytes(
    client: httpx.AsyncClient,
    url: str,
    *,
    max_bytes: int,
    accept: str | None = None,
) -> tuple[bytes, str]:
    current_url = url
    headers = dict(REMOTE_REQUEST_HEADERS)
    if accept:
        headers["Accept"] = accept

    for redirect_count in range(MAX_REMOTE_REDIRECTS + 1):
        await _ensure_public_remote_url(current_url)
        try:
            async with client.stream("GET", current_url, headers=headers) as response:
                if response.status_code in REDIRECT_STATUSES:
                    location = response.headers.get("location")
                    if not location:
                        raise ProductMediaError("Сервер фото вернул перенаправление без адреса")
                    if redirect_count == MAX_REMOTE_REDIRECTS:
                        raise ProductMediaError("Слишком много перенаправлений по ссылке на фото")
                    current_url = urljoin(str(response.url), location)
                    continue
                if response.status_code >= 400:
                    raise ProductMediaError(
                        f"Сервер фото вернул ошибку HTTP {response.status_code}"
                    )

                content_length = response.headers.get("content-length")
                if content_length:
                    try:
                        declared_size = int(content_length)
                    except ValueError:
                        declared_size = 0
                    if declared_size > max_bytes:
                        raise ProductMediaError("Фото должно быть не больше 10 МБ")

                content = bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > max_bytes:
                        raise ProductMediaError("Фото должно быть не больше 10 МБ")
                return bytes(content), str(response.url)
        except ProductMediaError:
            raise
        except httpx.TimeoutException as exc:
            raise ProductMediaError("Сервер с фото не ответил вовремя") from exc
        except httpx.HTTPError as exc:
            raise ProductMediaError("Не удалось скачать фото по указанной ссылке") from exc

    raise ProductMediaError("Слишком много перенаправлений по ссылке на фото")


async def _resolve_remote_image_url(
    client: httpx.AsyncClient,
    source_url: str,
) -> tuple[str, str | None]:
    if _is_yandex_public_link(source_url):
        api_url = f"{YANDEX_PUBLIC_DOWNLOAD_API}?{urlencode({'public_key': source_url})}"
        try:
            content, _ = await _fetch_remote_bytes(
                client,
                api_url,
                max_bytes=MAX_REMOTE_METADATA_BYTES,
                accept="application/json",
            )
            payload = json.loads(content)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ProductMediaError("Яндекс Диск не вернул ссылку на скачивание") from exc
        except ProductMediaError as exc:
            raise ProductMediaError(
                "Не удалось открыть файл на Яндекс Диске. Проверьте публичный доступ"
            ) from exc
        href = payload.get("href") if isinstance(payload, dict) else None
        if not isinstance(href, str) or not href:
            raise ProductMediaError("Яндекс Диск не вернул ссылку на скачивание")
        return href, "yandex"

    source_host = (urlsplit(source_url).hostname or "").casefold()
    if source_host in GOOGLE_DRIVE_HOSTS:
        google_file = _google_drive_file_id(source_url)
        if google_file is None:
            raise ProductMediaError("Не удалось определить файл по ссылке Google Drive")
        return _google_drive_download_url(*google_file), "google"

    return source_url, None


async def save_remote_product_image(
    photo_url: str,
    *,
    media_root: str,
    client: httpx.AsyncClient | None = None,
    crop: ProductImageCrop | None = None,
) -> SavedProductImage:
    source_url = photo_url.strip().replace("\\&", "&")
    if not source_url:
        raise ProductMediaError("Ссылка на фото пуста")

    own_client = client is None
    if client is None:
        client = create_remote_product_image_client()
    try:
        download_url, provider = await _resolve_remote_image_url(client, source_url)
        try:
            content, _ = await _fetch_remote_bytes(
                client,
                download_url,
                max_bytes=MAX_PRODUCT_IMAGE_BYTES,
            )
        except ProductMediaError as exc:
            host = (urlsplit(source_url).hostname or "").casefold()
            if "downloader.disk.yandex" in host:
                raise ProductMediaError(
                    "Временная ссылка Яндекс Диска истекла. Используйте ссылку «Поделиться»"
                ) from exc
            raise

        if _image_extension(content) is None:
            source_host = (urlsplit(source_url).hostname or "").casefold()
            if "downloader.disk.yandex" in source_host:
                raise ProductMediaError(
                    "Временная ссылка Яндекс Диска истекла. Используйте ссылку «Поделиться»"
                )
            if provider == "google":
                raise ProductMediaError(
                    "Google Drive не отдал изображение. Включите доступ «Все, у кого есть ссылка»"
                )
            if provider == "yandex":
                raise ProductMediaError("По публичной ссылке Яндекс Диска получено не изображение")
            raise ProductMediaError("Ссылка ведет на веб-страницу или неподдерживаемый файл")
        return await _save_product_image_content(
            content,
            media_root=media_root,
            subject="Фото по ссылке",
            crop=crop,
        )
    finally:
        if own_client:
            await client.aclose()


async def remove_product_image(image: SavedProductImage | None) -> None:
    if image is None:
        return
    for path in image.paths:
        try:
            await asyncio.to_thread(path.unlink, missing_ok=True)
        except OSError:
            continue


def _local_product_image_path(photo_url: str, *, media_root: str) -> Path:
    path = urlsplit(photo_url).path
    prefix = f"{PRODUCT_MEDIA_URL_PREFIX}/"
    if not path.startswith(prefix):
        raise ProductMediaError("Исходное фото товара недоступно для кадрирования")
    filename = path.removeprefix(prefix)
    if not filename or Path(filename).name != filename:
        raise ProductMediaError("Некорректный адрес исходного фото")
    root, target = _resolve_media_target(media_root, filename)
    if target.parent != root or not target.is_file():
        raise ProductMediaError("Исходное фото товара не найдено")
    return target


def _save_recropped_variants(
    content: bytes,
    *,
    media_root: str,
    crop: ProductImageCrop | None,
    master_url_path: str,
) -> SavedProductImage:
    root = _prepare_media_root(media_root)
    master = _decoded_product_image(content, subject="Исходное фото")
    detail_source = master.crop(_crop_box(master, crop)) if crop is not None else master.copy()
    detail = _fit_within(detail_source, DETAIL_IMAGE_MAX_SIZE)
    thumbnail = ImageOps.fit(
        detail_source,
        (THUMBNAIL_IMAGE_SIZE, THUMBNAIL_IMAGE_SIZE),
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.5),
    )
    token = uuid4().hex
    detail_path = root / f"{token}-detail.webp"
    thumbnail_path = root / f"{token}-thumb.webp"
    created: list[Path] = []
    try:
        for path, encoded in (
            (
                detail_path,
                _encode_webp(
                    detail,
                    quality=DETAIL_IMAGE_QUALITY,
                    max_bytes=DETAIL_IMAGE_MAX_BYTES,
                ),
            ),
            (
                thumbnail_path,
                _encode_webp(
                    thumbnail,
                    quality=THUMBNAIL_IMAGE_QUALITY,
                    max_bytes=THUMBNAIL_IMAGE_MAX_BYTES,
                ),
            ),
        ):
            _write_atomic(path, encoded)
            created.append(path)
    except Exception:
        for path in created:
            path.unlink(missing_ok=True)
        raise
    return SavedProductImage(
        path=detail_path,
        url_path=f"{PRODUCT_MEDIA_URL_PREFIX}/{detail_path.name}",
        thumbnail_path=thumbnail_path,
        thumbnail_url_path=f"{PRODUCT_MEDIA_URL_PREFIX}/{thumbnail_path.name}",
        master_url_path=master_url_path,
    )


async def recrop_product_image(
    master_url: str,
    *,
    media_root: str,
    crop: ProductImageCrop | None,
) -> SavedProductImage:
    master_path = await asyncio.to_thread(
        _local_product_image_path,
        master_url,
        media_root=media_root,
    )
    content = await asyncio.to_thread(master_path.read_bytes)
    master_url_path = urlsplit(master_url).path
    return await asyncio.to_thread(
        _save_recropped_variants,
        content,
        media_root=media_root,
        crop=crop,
        master_url_path=master_url_path,
    )


async def optimize_existing_product_image(
    photo_url: str,
    *,
    media_root: str,
    crop: ProductImageCrop | None = None,
) -> SavedProductImage:
    path = urlsplit(photo_url).path
    if path.startswith(f"{PRODUCT_MEDIA_URL_PREFIX}/"):
        source_path = await asyncio.to_thread(
            _local_product_image_path,
            photo_url,
            media_root=media_root,
        )
        content = await asyncio.to_thread(source_path.read_bytes)
        return await _save_product_image_content(
            content,
            media_root=media_root,
            subject="Фото товара",
            crop=crop,
        )
    return await save_remote_product_image(
        photo_url,
        media_root=media_root,
        crop=crop,
    )


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


async def remove_product_image_urls(
    photo_urls: list[str | None] | tuple[str | None, ...] | set[str | None],
    *,
    media_root: str,
) -> None:
    for photo_url in set(photo_urls):
        await remove_product_image_url(photo_url, media_root=media_root)
