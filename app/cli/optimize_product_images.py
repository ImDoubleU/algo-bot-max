from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict, dataclass
from urllib.parse import urlsplit

from sqlalchemy import or_, select

import app.db.base  # noqa: F401
from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models.store import Product
from app.services.product_media import (
    ProductImageCrop,
    ProductMediaError,
    optimize_existing_product_image,
    remove_product_image,
    remove_product_image_urls,
)


@dataclass
class OptimizationResult:
    selected: int = 0
    optimized: int = 0
    skipped: int = 0
    failed: int = 0
    reclaimed_sources: int = 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate optimized master, detail and thumbnail variants for product photos",
    )
    parser.add_argument("--dry-run", action="store_true", help="Only count matching products")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate already optimized products",
    )
    parser.add_argument("--limit", type=int, default=None, help="Maximum products to process")
    return parser


def _media_origin(photo_url: str, fallback_miniapp_url: str | None) -> str:
    fallback = urlsplit(fallback_miniapp_url or "")
    if fallback.scheme and fallback.netloc:
        return f"{fallback.scheme}://{fallback.netloc}"
    parsed = urlsplit(photo_url)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return ""


def _stored_crop(product: Product) -> ProductImageCrop | None:
    values = (
        product.photo_crop_x,
        product.photo_crop_y,
        product.photo_crop_width,
        product.photo_crop_height,
    )
    if not all(value is not None for value in values):
        return None
    return ProductImageCrop(
        x=float(product.photo_crop_x),
        y=float(product.photo_crop_y),
        width=float(product.photo_crop_width),
        height=float(product.photo_crop_height),
    ).validate()


async def run(*, dry_run: bool, force: bool, limit: int | None) -> OptimizationResult:
    settings = get_settings()
    result = OptimizationResult()
    async with AsyncSessionLocal() as db:
        query = select(Product).where(Product.photo_url.is_not(None)).order_by(Product.id)
        if not force:
            query = query.where(
                or_(
                    Product.photo_thumbnail_url.is_(None),
                    Product.photo_master_url.is_(None),
                )
            )
        if limit is not None:
            query = query.limit(max(limit, 0))
        product_ids = list((await db.scalars(query.with_only_columns(Product.id))).all())
        result.selected = len(product_ids)
        if dry_run:
            return result

    for product_id in product_ids:
        async with AsyncSessionLocal() as db:
            product = await db.get(Product, product_id)
            if product is None:
                result.skipped += 1
                continue
            source_url = product.photo_master_url or product.photo_url
            if not source_url:
                result.skipped += 1
                continue
            product_id_text = str(product.id)
            product_name = product.name
            previous_urls = (
                product.photo_url,
                product.photo_thumbnail_url,
                product.photo_master_url,
            )
            saved = None
            try:
                saved = await optimize_existing_product_image(
                    source_url,
                    media_root=settings.product_media_root,
                    crop=_stored_crop(product),
                )
                origin = _media_origin(product.photo_url or source_url, settings.max_miniapp_url)
                product.photo_url = f"{origin}{saved.url_path}"
                product.photo_thumbnail_url = (
                    f"{origin}{saved.thumbnail_url_path}"
                    if saved.thumbnail_url_path
                    else product.photo_url
                )
                product.photo_master_url = (
                    f"{origin}{saved.master_url_path}"
                    if saved.master_url_path
                    else product.photo_url
                )
                await db.commit()
                current_urls = {
                    product.photo_url,
                    product.photo_thumbnail_url,
                    product.photo_master_url,
                }
                obsolete_urls = [url for url in previous_urls if url and url not in current_urls]
                await remove_product_image_urls(
                    obsolete_urls,
                    media_root=settings.product_media_root,
                )
                result.reclaimed_sources += len(set(obsolete_urls))
                result.optimized += 1
                print(
                    json.dumps(
                        {
                            "status": "optimized",
                            "product_id": product_id_text,
                            "name": product_name,
                        },
                        ensure_ascii=False,
                    )
                )
            except (ProductMediaError, OSError, ValueError) as exc:
                await db.rollback()
                await remove_product_image(saved)
                result.failed += 1
                print(
                    json.dumps(
                        {
                            "status": "failed",
                            "product_id": product_id_text,
                            "name": product_name,
                            "error": str(exc),
                        },
                        ensure_ascii=False,
                    )
                )
    return result


def main() -> None:
    args = build_parser().parse_args()
    if args.limit is not None and args.limit < 0:
        raise SystemExit("--limit must be zero or greater")
    result = asyncio.run(run(dry_run=args.dry_run, force=args.force, limit=args.limit))
    print(json.dumps({"summary": asdict(result)}, ensure_ascii=False))
    if result.failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
