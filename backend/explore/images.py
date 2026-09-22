import io
import uuid
import warnings

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.shortcuts import get_object_or_404
from PIL import Image, ImageOps, UnidentifiedImageError

from .models import Node
from .services import GraphEditor


class NodeImageService:
    """Keep only a small, metadata-free WebP cover, never the uploaded original."""

    MAX_BYTES = 10 * 1024 * 1024
    MAX_PIXELS = 25_000_000
    SIZE = (640, 360)
    QUALITY = 75

    @classmethod
    def encode(cls, upload):
        if not upload or not upload.size:
            raise ValidationError("Выберите изображение.")
        if upload.size > cls.MAX_BYTES:
            raise ValidationError("Изображение должно быть не больше 10 МБ.")
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(upload) as source:
                    if source.format not in {"JPEG", "PNG", "WEBP", "GIF"}:
                        raise ValidationError("Загрузите JPEG, PNG, WebP или GIF.")
                    if source.width * source.height > cls.MAX_PIXELS:
                        raise ValidationError("Изображение должно содержать не больше 25 мегапикселей.")
                    # Animated inputs intentionally become a static first-frame cover.
                    image = ImageOps.exif_transpose(source)
                    image = image.convert("RGBA" if "A" in image.getbands() or "transparency" in image.info else "RGB")
                    ratio = min(1, image.width / cls.SIZE[0], image.height / cls.SIZE[1])
                    size = tuple(max(1, round(side * ratio)) for side in cls.SIZE)
                    image = ImageOps.fit(image, size, method=Image.Resampling.LANCZOS)
                    image.info.clear()
                    output = io.BytesIO()
                    image.save(output, format="WEBP", quality=cls.QUALITY, method=4)
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
            raise ValidationError("Не удалось прочитать изображение. Выберите другой файл.") from None
        return ContentFile(output.getvalue(), name=f"{uuid.uuid4().hex}.webp")

    @staticmethod
    def delete_after_commit(storage, name):
        if name:
            transaction.on_commit(lambda: storage.delete(name), robust=True)

    @classmethod
    def replace(cls, node_id, upload):
        get_object_or_404(Node, pk=node_id)
        content = cls.encode(upload)
        saved = []

        def update():
            node = get_object_or_404(Node, pk=node_id)
            storage, previous = node.image.storage, node.image.name
            node.image.save(content.name, content, save=False)
            saved.append((storage, node.image.name))
            node.save(update_fields=["image", "updated_at"])
            cls.delete_after_commit(storage, previous)
            return node

        try:
            return GraphEditor.apply(update)
        except Exception:
            for storage, name in saved:
                storage.delete(name)
            raise

    @classmethod
    def remove(cls, node_id):
        def update():
            node = get_object_or_404(Node, pk=node_id)
            storage, previous = node.image.storage, node.image.name
            node.image = ""
            node.save(update_fields=["image", "updated_at"])
            cls.delete_after_commit(storage, previous)
        GraphEditor.apply(update)
