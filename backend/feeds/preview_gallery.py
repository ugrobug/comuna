"""Prepare first-media galleries on write, never parse full bodies per feed card."""
from html import unescape
from html.parser import HTMLParser
from typing import Any


class LeadingGalleryParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.gallery_depth = None
        self.first_image_seen = False
        self.items = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "div":
            self.depth += 1
            if not self.first_image_seen and "post-gallery" in (attrs.get("class") or "").split():
                self.gallery_depth = self.depth
        if tag != "img" or not attrs.get("src"):
            return
        if self.gallery_depth is not None:
            self.items.append({"url": attrs["src"], "alt": attrs.get("alt") or ""})
        self.first_image_seen = True

    def handle_endtag(self, tag):
        if tag == "div":
            if self.depth == self.gallery_depth:
                self.gallery_depth = None
            self.depth = max(0, self.depth - 1)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag == "div":
            self.handle_endtag(tag)


class PostPreviewGallery:
    """Select only the gallery owning the leading image; explicit covers win."""

    def extract(self, content: str, payload: dict | None, preview_url: str) -> list[dict[str, str]]:
        if not preview_url:
            return []
        if payload is not None:
            additional = payload.get("additional") or {}
            if isinstance(additional, dict) and any(additional.get(key) for key in (
                "previewImage", "preview_image_url", "cover_image_url"
            )):
                return []
            items = self._editor_items(payload)
        else:
            parser = LeadingGalleryParser()
            parser.feed(content)
            items = parser.items
        normalized = []
        seen = set()
        for item in items:
            if isinstance(item, str):
                item = {"url": item}
            if not isinstance(item, dict):
                continue
            file = item.get("file") if isinstance(item.get("file"), dict) else {}
            url = str(item.get("url") or file.get("url") or "").strip()
            if not url or url in seen:
                continue
            seen.add(url)
            normalized.append({"url": url, "alt": str(item.get("alt") or "")[:500]})
        if len(normalized) < 2 or unescape(normalized[0]["url"]) != unescape(preview_url):
            return []
        return normalized

    def _editor_items(self, payload: dict[str, Any]) -> list:
        for block in payload.get("blocks", []):
            if not isinstance(block, dict):
                continue
            kind = str(block.get("type") or "").lower()
            data = block.get("data") or {}
            if not isinstance(data, dict):
                continue
            if kind == "gallery" and isinstance(data.get("images"), list) and data["images"]:
                return data["images"]
            if kind in {"image", "imagecompare", "compare"}:
                return []
        return []
