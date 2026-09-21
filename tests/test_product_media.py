from __future__ import annotations

from io import BytesIO

import httpx
import pytest
from PIL import Image

import app.services.product_media as product_media
from app.services.product_media import (
    ProductImageCrop,
    ProductMediaError,
    recrop_product_image,
    save_remote_product_image,
)


async def _allow_remote_url(_url: str) -> None:
    return None


def _image_bytes(format_name: str, *, size: tuple[int, int] = (900, 600)) -> bytes:
    mode = "RGBA" if format_name == "PNG" else "RGB"
    color = (30, 120, 220, 140) if mode == "RGBA" else (30, 120, 220)
    image = Image.new(mode, size, color)
    output = BytesIO()
    image.save(output, format=format_name)
    return output.getvalue()


async def test_yandex_public_link_is_resolved_and_saved(
    tmp_path,
    monkeypatch,
) -> None:
    source_url = "https://disk.yandex.ru/i/R2zYXllwq-cyIw"
    download_url = "https://downloader.disk.yandex.ru/disk/public-photo"
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.host == "cloud-api.yandex.net":
            assert request.url.params["public_key"] == source_url
            return httpx.Response(200, json={"href": download_url})
        assert str(request.url) == download_url
        return httpx.Response(200, content=_image_bytes("JPEG"))

    monkeypatch.setattr(product_media, "_ensure_public_remote_url", _allow_remote_url)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        saved = await save_remote_product_image(
            source_url,
            media_root=str(tmp_path),
            client=client,
        )

    assert saved.url_path.startswith("/media/products/")
    assert saved.url_path.endswith("-detail.webp")
    assert saved.thumbnail_path is not None
    assert saved.master_path is not None
    with Image.open(saved.thumbnail_path) as thumbnail:
        assert thumbnail.size == (480, 480)
    assert [request.url.host for request in requests] == [
        "cloud-api.yandex.net",
        "downloader.disk.yandex.ru",
    ]


async def test_google_drive_share_link_is_downloaded_and_saved(
    tmp_path,
    monkeypatch,
) -> None:
    source_url = (
        "https://drive.google.com/file/d/1AbC_def-234/view?usp=sharing&resourcekey=resource-key"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "drive.usercontent.google.com"
        assert request.url.params["id"] == "1AbC_def-234"
        assert request.url.params["export"] == "download"
        assert request.url.params["resourcekey"] == "resource-key"
        return httpx.Response(200, content=_image_bytes("PNG"))

    monkeypatch.setattr(product_media, "_ensure_public_remote_url", _allow_remote_url)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        saved = await save_remote_product_image(
            source_url,
            media_root=str(tmp_path),
            client=client,
        )

    assert saved.url_path.endswith("-detail.webp")
    with Image.open(saved.path) as detail:
        assert detail.mode == "RGBA"


async def test_direct_image_link_is_downloaded_and_saved(
    tmp_path,
    monkeypatch,
) -> None:
    source_url = "https://cdn.example.org/catalog/photo.webp"

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == source_url
        return httpx.Response(200, content=_image_bytes("WEBP"))

    monkeypatch.setattr(product_media, "_ensure_public_remote_url", _allow_remote_url)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        saved = await save_remote_product_image(
            source_url,
            media_root=str(tmp_path),
            client=client,
        )

    assert saved.url_path.endswith(".webp")


async def test_product_image_crop_creates_square_variants(tmp_path) -> None:
    saved = await product_media._save_product_image_content(
        _image_bytes("JPEG", size=(1600, 900)),
        media_root=str(tmp_path),
        subject="Фото",
        crop=ProductImageCrop(x=0.25, y=0, width=0.5, height=8 / 9),
    )

    assert saved.thumbnail_path is not None
    assert saved.master_path is not None
    with Image.open(saved.path) as detail, Image.open(saved.thumbnail_path) as thumbnail:
        assert detail.width == detail.height
        assert thumbnail.size == (480, 480)
        assert saved.thumbnail_path.stat().st_size <= product_media.THUMBNAIL_IMAGE_MAX_BYTES

    recropped = await recrop_product_image(
        saved.master_url_path or "",
        media_root=str(tmp_path),
        crop=ProductImageCrop(x=0, y=0, width=0.5, height=8 / 9),
    )
    assert recropped.master_path is None
    assert recropped.master_url_path == saved.master_url_path
    assert recropped.path != saved.path


async def test_product_image_applies_exif_orientation(tmp_path) -> None:
    source = Image.new("RGB", (120, 60), (220, 80, 40))
    exif = source.getexif()
    exif[274] = 6
    output = BytesIO()
    source.save(output, format="JPEG", exif=exif)

    saved = await product_media._save_product_image_content(
        output.getvalue(),
        media_root=str(tmp_path),
        subject="Фото",
    )

    assert saved.master_path is not None
    with Image.open(saved.master_path) as master:
        assert master.size == (60, 120)


async def test_product_image_rejects_excessive_pixel_count(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(product_media, "MAX_PRODUCT_IMAGE_PIXELS", 5_000)
    with pytest.raises(ProductMediaError, match="слишком большое разрешение"):
        await product_media._save_product_image_content(
            _image_bytes("PNG", size=(100, 100)),
            media_root=str(tmp_path),
            subject="Фото",
        )


async def test_expired_yandex_downloader_link_has_actionable_error(
    tmp_path,
    monkeypatch,
) -> None:
    source_url = "https://1.downloader.disk.yandex.ru/preview/expired"

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, content=b"expired")

    monkeypatch.setattr(product_media, "_ensure_public_remote_url", _allow_remote_url)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ProductMediaError, match="Используйте ссылку «Поделиться»"):
            await save_remote_product_image(
                source_url,
                media_root=str(tmp_path),
                client=client,
            )


async def test_google_drive_private_page_has_actionable_error(
    tmp_path,
    monkeypatch,
) -> None:
    source_url = "https://drive.google.com/open?id=private-file"

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"<!doctype html><title>Sign in</title>")

    monkeypatch.setattr(product_media, "_ensure_public_remote_url", _allow_remote_url)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ProductMediaError, match="Все, у кого есть ссылка"):
            await save_remote_product_image(
                source_url,
                media_root=str(tmp_path),
                client=client,
            )


async def test_remote_image_rejects_private_network_url() -> None:
    with pytest.raises(ProductMediaError, match="локальную сеть"):
        await product_media._ensure_public_remote_url("http://127.0.0.1/photo.jpg")
