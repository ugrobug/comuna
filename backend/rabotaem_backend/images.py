from __future__ import annotations

import io
import os
from dataclasses import dataclass

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from PIL import Image, ImageOps, UnidentifiedImageError


IMAGE_VARIANT_WIDTHS = (320, 640, 960, 1280, 1920)


@dataclass(frozen=True)
class SavedImageVariant:
    width: int
    path: str
    url: str


@dataclass(frozen=True)
class SavedImageSet:
    original_path: str
    original_url: str
    default_path: str
    default_url: str
    variants: tuple[SavedImageVariant, ...]


def _storage_url(path: str) -> str:
    return default_storage.url(path)


def _save_webp_variant(image: Image.Image, path: str, width: int) -> SavedImageVariant | None:
    if image.width <= 0 or image.height <= 0:
        return None
    target_width = min(width, image.width)
    ratio = target_width / image.width
    target_height = max(1, round(image.height * ratio))
    variant_image = image
    if target_width != image.width:
        variant_image = image.resize((target_width, target_height), Image.Resampling.LANCZOS)
    if variant_image.mode not in {"RGB", "RGBA"}:
        variant_image = variant_image.convert("RGBA" if "A" in variant_image.getbands() else "RGB")

    output = io.BytesIO()
    variant_image.save(output, format="WEBP", quality=82, method=6)
    saved_path = default_storage.save(path, ContentFile(output.getvalue()))
    return SavedImageVariant(width=target_width, path=saved_path, url=_storage_url(saved_path))


def save_image_with_variants(
    *,
    data: bytes,
    original_path: str,
    variant_widths: tuple[int, ...] = IMAGE_VARIANT_WIDTHS,
    keep_original: bool = True,
) -> SavedImageSet:
    original_path = default_storage.save(original_path, ContentFile(data))
    original_url = _storage_url(original_path)
    root, ext = os.path.splitext(original_path)
    if ext.lower() == ".gif":
        return SavedImageSet(
            original_path=original_path,
            original_url=original_url,
            default_path=original_path,
            default_url=original_url,
            variants=(),
        )

    try:
        with Image.open(io.BytesIO(data)) as opened:
            image = ImageOps.exif_transpose(opened)
            image.load()
    except (UnidentifiedImageError, OSError, ValueError):
        return SavedImageSet(
            original_path=original_path,
            original_url=original_url,
            default_path=original_path,
            default_url=original_url,
            variants=(),
        )

    variants: list[SavedImageVariant] = []
    for width in variant_widths:
        if width > image.width and variants:
            continue
        variant_path = f"{root}-{width}.webp"
        variant = _save_webp_variant(image, variant_path, width)
        if variant is not None:
            variants.append(variant)

    if not variants:
        return SavedImageSet(
            original_path=original_path,
            original_url=original_url,
            default_path=original_path,
            default_url=original_url,
            variants=(),
        )

    default_variant = variants[-1]
    if not keep_original and original_path != default_variant.path:
        default_storage.delete(original_path)
        original_path = default_variant.path
        original_url = default_variant.url

    return SavedImageSet(
        original_path=original_path,
        original_url=original_url,
        default_path=default_variant.path,
        default_url=default_variant.url,
        variants=tuple(variants),
    )
