import io
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image

from explore.images import NodeImageService
from explore.models import Node
from users.service import _issue_token


class NodeImageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_user(username="image-staff", is_staff=True)
        cls.member = get_user_model().objects.create_user(username="image-member")
        cls.staff_token = _issue_token(cls.staff)
        cls.member_token = _issue_token(cls.member)
        cls.node = Node.objects.create(title="Фотография")

    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.settings = override_settings(MEDIA_ROOT=self.directory.name)
        self.settings.enable()
        self.addCleanup(self.settings.disable)
        self.path = f"/api/explore/nodes/{self.node.pk}/image/"

    def upload(self, size=(1600, 1000), *, mode="RGB", format="PNG", **kwargs):
        output = io.BytesIO()
        Image.new(mode, size, (200, 70, 20, 128) if mode == "RGBA" else (200, 70, 20)).save(output, format=format, **kwargs)
        return SimpleUploadedFile("original." + format.lower(), output.getvalue(), content_type="image/" + format.lower())

    def post(self, file=None, token=None):
        return self.client.post(self.path, {"image": file or self.upload()}, HTTP_AUTHORIZATION=f"Bearer {token or self.staff_token}")

    def files(self):
        return list(Path(self.directory.name).rglob("*.webp"))

    def test_upload_stores_only_small_webp_and_graph_returns_url(self):
        response = self.post()
        self.assertEqual(response.status_code, 200, response.content)
        self.node.refresh_from_db()
        self.assertTrue(self.node.image.name.startswith("explore/cards/"))
        self.assertEqual(len([p for p in Path(self.directory.name).rglob("*") if p.is_file()]), 1)
        with Image.open(self.node.image.path) as image:
            self.assertEqual(image.format, "WEBP")
            self.assertEqual(image.size, (640, 360))
            self.assertFalse(image.getexif())
        graph = self.client.get("/api/explore/").json()
        node = next(item for item in graph["nodes"] if item["id"] == self.node.pk)
        self.assertEqual(node["image_url"], response.json()["image_url"])

    def test_small_transparent_image_is_not_upscaled(self):
        self.assertEqual(self.post(self.upload((160, 90), mode="RGBA")).status_code, 200)
        with Image.open(self.files()[0]) as image:
            self.assertEqual(image.size, (160, 90))
            self.assertEqual(image.getpixel((0, 0))[3], 128)

    def test_rotation_is_applied_before_crop_and_metadata_removed(self):
        exif = Image.Exif()
        exif[274] = 6
        exif[270] = "Private image description"
        self.assertEqual(self.post(self.upload((600, 300), format="JPEG", exif=exif)).status_code, 200)
        with Image.open(self.files()[0]) as image:
            self.assertEqual(image.size, (300, 169))
            self.assertFalse(image.getexif())

    def test_animation_becomes_one_small_frame(self):
        output = io.BytesIO()
        Image.new("RGB", (100, 100), "red").save(output, format="GIF", save_all=True, append_images=[Image.new("RGB", (100, 100), "blue")], duration=100)
        self.assertEqual(self.post(SimpleUploadedFile("animation.gif", output.getvalue())).status_code, 200)
        with Image.open(self.files()[0]) as image:
            self.assertEqual(image.n_frames, 1)
            self.assertGreater(image.getpixel((10, 10))[0], 200)

    def test_only_staff_can_upload_or_remove(self):
        self.assertEqual(self.client.post(self.path, {"image": self.upload()}).status_code, 401)
        self.assertEqual(self.post(token=self.member_token).status_code, 403)
        self.assertEqual(self.client.delete(self.path).status_code, 401)
        self.assertEqual(self.client.delete(self.path, HTTP_AUTHORIZATION=f"Bearer {self.member_token}").status_code, 403)
        self.assertEqual(self.files(), [])

    def test_invalid_missing_and_oversized_images_are_rejected(self):
        self.assertEqual(self.post(SimpleUploadedFile("bad.png", b"not an image")).status_code, 400)
        self.assertEqual(self.client.post(self.path, {}, HTTP_AUTHORIZATION=f"Bearer {self.staff_token}").status_code, 400)
        with patch.object(NodeImageService, "MAX_BYTES", 20):
            self.assertEqual(self.post().status_code, 400)
        with patch.object(NodeImageService, "MAX_PIXELS", 100):
            self.assertEqual(self.post().status_code, 400)
        self.assertEqual(self.files(), [])

    def test_replacement_removes_previous_file_after_commit(self):
        self.post()
        previous = self.files()[0]
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.post().status_code, 200)
            self.assertTrue(previous.exists())
        self.assertFalse(previous.exists())
        self.assertEqual(len(self.files()), 1)

    def test_failed_upload_keeps_previous_image_and_cleans_new_file(self):
        self.post()
        previous = self.files()[0]
        with patch("explore.services.GraphNotifications.notify_changes", side_effect=RuntimeError("rollback")):
            with self.assertRaises(RuntimeError):
                self.post()
        self.node.refresh_from_db()
        self.assertEqual(Path(self.node.image.path), previous)
        self.assertEqual(self.files(), [previous])

    def test_image_delete_removes_file_without_deleting_node(self):
        self.post()
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.delete(self.path, HTTP_AUTHORIZATION=f"Bearer {self.staff_token}")
        self.assertEqual(response.status_code, 200)
        self.node.refresh_from_db()
        self.assertFalse(self.node.image)
        self.assertEqual(self.files(), [])

    def test_deleting_node_removes_its_image(self):
        self.post()
        self.node.refresh_from_db()
        with self.captureOnCommitCallbacks(execute=True):
            self.node.delete()
        self.assertEqual(self.files(), [])
