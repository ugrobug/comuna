import io
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.files.storage import FileSystemStorage
from django.test import SimpleTestCase
from PIL import Image

from rabotaem_backend.images import save_image_with_variants


class FastImageVariantsTests(SimpleTestCase):
    def test_fast_encoding_preserves_original_and_responsive_sizes(self):
        source = io.BytesIO()
        Image.new('RGB', (2000, 1000), '#527e94').save(source, format='PNG')
        with TemporaryDirectory() as directory:
            storage = FileSystemStorage(location=directory, base_url='/media/')
            with patch('rabotaem_backend.images.default_storage', storage):
                result = save_image_with_variants(data=source.getvalue(), original_path='photo.png', webp_method=4)
                self.assertEqual([item.width for item in result.variants], [320, 640, 960, 1280, 1920])
                self.assertEqual(result.default_url, '/media/photo-1920.webp')
                with storage.open(result.original_path, 'rb') as original:
                    self.assertEqual(original.read(), source.getvalue())
                for variant in result.variants:
                    with storage.open(variant.path, 'rb') as saved:
                        image = Image.open(saved)
                        self.assertEqual(image.format, 'WEBP')
                        self.assertEqual(image.size, (variant.width, variant.width // 2))

    def test_fast_encoding_preserves_transparency_and_does_not_upscale(self):
        source = io.BytesIO()
        Image.new('RGBA', (100, 50), (50, 120, 200, 128)).save(source, format='PNG')
        with TemporaryDirectory() as directory:
            with patch('rabotaem_backend.images.default_storage', FileSystemStorage(location=directory)):
                result = save_image_with_variants(data=source.getvalue(), original_path='small.png', webp_method=4)
                self.assertEqual(len(result.variants), 1)
                with Image.open(f'{directory}/{result.default_path}') as image:
                    self.assertEqual(image.size, (100, 50))
                    self.assertEqual(image.getpixel((0, 0))[3], 128)
