from __future__ import annotations

from io import BytesIO
import os

from django.core.files.base import ContentFile
from django.db import migrations, models
from PIL import Image, ImageOps


ICON_THUMB_SIZE = (64, 64)


def _build_thumb(image_field):
    if not image_field:
        return None
    try:
        image_field.open("rb")
        with Image.open(image_field) as img:
            img = ImageOps.exif_transpose(img)
            resample = getattr(Image, "Resampling", Image).LANCZOS
            img = ImageOps.fit(img, ICON_THUMB_SIZE, resample)
            has_alpha = img.mode in ("RGBA", "LA") or (
                img.mode == "P" and "transparency" in img.info
            )
            if has_alpha:
                img = img.convert("RGBA")
                fmt = "PNG"
                ext = "png"
                save_kwargs = {"optimize": True}
            else:
                img = img.convert("RGB")
                fmt = "JPEG"
                ext = "jpg"
                save_kwargs = {"quality": 85, "optimize": True}
            buffer = BytesIO()
            img.save(buffer, fmt, **save_kwargs)
            return ContentFile(buffer.getvalue()), ext
    except Exception:
        return None
    finally:
        try:
            image_field.close()
        except Exception:
            pass


def create_rubric_icon_thumbs(apps, schema_editor):
    Rubric = apps.get_model("feeds", "Rubric")
    for rubric in Rubric.objects.exclude(icon_url="").iterator():
        if getattr(rubric, "icon_thumb", None):
            if rubric.icon_thumb:
                continue
        if not rubric.icon_url:
            continue
        result = _build_thumb(rubric.icon_url)
        if not result:
            continue
        content, ext = result
        base = os.path.splitext(os.path.basename(rubric.icon_url.name or ""))[0]
        if not base:
            base = f"rubric_{rubric.pk}"
        filename = f"{base}_64x64.{ext}"
        rubric.icon_thumb.save(filename, content, save=True)


class Migration(migrations.Migration):
    dependencies = [
        ("feeds", "0025_author_publish_delay_and_post_publish_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="rubric",
            name="icon_thumb",
            field=models.ImageField(blank=True, upload_to="rubrics/icons/thumbs/"),
        ),
        migrations.RunPython(create_rubric_icon_thumbs, migrations.RunPython.noop),
    ]
