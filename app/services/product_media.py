import asyncio
import ipaddress
import json
import socket
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit
from uuid import uuid4

import httpx
from fastapi import UploadFile

MAX_PRODUCT_IMAGE_BYTES = 10 * 1024 * 1024
PRODUCT_MEDIA_URL_PREFIX = "/media/products"
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


async def _save_product_image_content(
    content: bytes,
    *,
    media_root: str,
    subject: str,
) -> SavedProductImage:
    if not content:
        raise ProductMediaError(f"{subject} пусто")
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


async def save_product_image(
    upload: UploadFile,
    *,
    media_root: str,
    subject: str = "Фото товара",
) -> SavedProductImage:
    content = await upload.read(MAX_PRODUCT_IMAGE_BYTES + 1)
    if not content:
        raise ProductMediaError("Выбранный файл пуст")
    return await _save_product_image_content(
        content,
        media_root=media_root,
        subject=subject,
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
        )
    finally:
        if own_client:
            await client.aclose()


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
