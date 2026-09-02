from __future__ import annotations

import httpx
import pytest

import app.services.product_media as product_media
from app.services.product_media import ProductMediaError, save_remote_product_image


async def _allow_remote_url(_url: str) -> None:
    return None


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
        return httpx.Response(200, content=b"\xff\xd8\xffphoto")

    monkeypatch.setattr(product_media, "_ensure_public_remote_url", _allow_remote_url)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        saved = await save_remote_product_image(
            source_url,
            media_root=str(tmp_path),
            client=client,
        )

    assert saved.path.read_bytes() == b"\xff\xd8\xffphoto"
    assert saved.url_path.startswith("/media/products/")
    assert saved.url_path.endswith(".jpg")
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
        return httpx.Response(200, content=b"\x89PNG\r\n\x1a\npicture")

    monkeypatch.setattr(product_media, "_ensure_public_remote_url", _allow_remote_url)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        saved = await save_remote_product_image(
            source_url,
            media_root=str(tmp_path),
            client=client,
        )

    assert saved.path.read_bytes() == b"\x89PNG\r\n\x1a\npicture"
    assert saved.url_path.endswith(".png")


async def test_direct_image_link_is_downloaded_and_saved(
    tmp_path,
    monkeypatch,
) -> None:
    source_url = "https://cdn.example.org/catalog/photo.webp"

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == source_url
        return httpx.Response(200, content=b"RIFF\x08\x00\x00\x00WEBPphoto")

    monkeypatch.setattr(product_media, "_ensure_public_remote_url", _allow_remote_url)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        saved = await save_remote_product_image(
            source_url,
            media_root=str(tmp_path),
            client=client,
        )

    assert saved.url_path.endswith(".webp")


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
